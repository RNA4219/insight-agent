"""Main pipeline module.

Orchestrates the complete insight agent pipeline:
1. Normalize request
2. Unitize sources
3. Extract claims/assumptions/limitations
4. Discover problem candidates
5. Evaluate with personas
6. Consolidate into insights/open questions
7. Build response
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from insight_core.consolidator import consolidate
from insight_core.discovery import discover_problems
from insight_core.evaluator import evaluate_candidates
from insight_core.extractor import extract_from_units
from insight_core.llm_client import LLMClient
from insight_core.request_normalizer import normalize_request
from insight_core.response_builder import build_failure_response, build_response
from insight_core.schemas import (
    FailureItem,
    InsightRequest,
    InsightResponse,
    RunStatus,
)
from insight_core.unitizer import unitize_sources


def _log(message: str) -> None:
    """Print progress message."""
    print(f"[InsightAgent] {message}", file=sys.stderr, flush=True)


def run_pipeline(
    request: InsightRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> InsightResponse:
    """Run the complete insight agent pipeline.

    Args:
        request: The insight request to process.
        llm: Optional LLM client instance. If None, creates a new one.
        verbose: Print progress messages.

    Returns:
        InsightResponse with results.
    """
    started_at = datetime.now(timezone.utc)
    failures: list[FailureItem] = []

    if verbose:
        _log("Starting pipeline...")

    # Initialize LLM client if not provided
    if llm is None:
        llm = LLMClient()

    if verbose:
        _log(f"Using LLM: {llm.provider} / {llm.model}")

    # Step 1: Normalize request
    if verbose:
        _log("Step 1: Normalizing request...")
    try:
        normalized, persona_registry, warnings = normalize_request(request)
        if verbose:
            _log(f"  - Request ID: {normalized.request_id}")
            _log(f"  - Sources: {len(normalized.sources)}")
            _log(f"  - Personas: {len(normalized.personas)}")
    except ValueError as e:
        _log(f"  - FAILED: {e}")
        failure = FailureItem(
            failure_id="fl_001",
            stage="normalization",
            reason=str(e),
            suggested_next_action="Request formatを確認してください",
        )
        from insight_core.schemas import NormalizedRequest, PersonaSource

        fake_normalized = NormalizedRequest(
            run_id="run_failed",
            request_id=request.request_id or "req_failed",
            sources=request.sources,
            constraints=request.constraints or {},
            personas=[],
            persona_source=PersonaSource.DEFAULT,
            persona_catalog_version=None,
            context=request.context or {},
            options=request.options or {},
        )
        return build_failure_response(fake_normalized, [failure], started_at)

    domain = normalized.constraints.domain

    # Step 2: Unitize sources
    if verbose:
        _log("Step 2: Unitizing sources...")
    try:
        source_units = unitize_sources(normalized.sources)
        if verbose:
            _log(f"  - Created {len(source_units)} units")
    except Exception as e:
        _log(f"  - FAILED: {e}")
        failures.append(
            FailureItem(
                failure_id=f"fl_{len(failures)+1:03d}",
                stage="unitization",
                reason=f"Source unitization failed: {e}",
                suggested_next_action="Source contentを確認してください",
            )
        )
        source_units = []

    if not source_units:
        failures.append(
            FailureItem(
                failure_id=f"fl_{len(failures)+1:03d}",
                stage="unitization",
                reason="No valid source units generated",
                suggested_next_action="有効なコンテンツを含むsourceを提供してください",
            )
        )
        return build_failure_response(normalized, failures, started_at)

    # Step 3: Extract claims/assumptions/limitations
    if verbose:
        _log("Step 3: Extracting claims/assumptions/limitations...")
    try:
        claims, assumptions, limitations, evidence_refs, failed_unit_ids = extract_from_units(
            source_units, llm, domain
        )
        if verbose:
            _log(f"  - Claims: {len(claims)}")
            _log(f"  - Assumptions: {len(assumptions)}")
            _log(f"  - Limitations: {len(limitations)}")

        if failed_unit_ids:
            failures.append(
                FailureItem(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage="extraction",
                    reason=f"Extraction failed for {len(failed_unit_ids)} units",
                    details=f"Failed units: {', '.join(failed_unit_ids[:5])}",
                    related_refs=failed_unit_ids[:5],
                    suggested_next_action="該当unitの内容を確認してください",
                )
            )
    except Exception as e:
        _log(f"  - FAILED: {e}")
        failures.append(
            FailureItem(
                failure_id=f"fl_{len(failures)+1:03d}",
                stage="extraction",
                reason=f"Extraction pipeline failed: {e}",
                suggested_next_action="抽出処理を再試行してください",
            )
        )
        claims, assumptions, limitations, evidence_refs = [], [], [], []

    # Step 4: Discover problem candidates
    if verbose:
        _log("Step 4: Discovering problem candidates...")
    try:
        candidates = discover_problems(
            claims, assumptions, limitations, llm, domain, normalized.constraints.max_problem_candidates
        )
        if verbose:
            _log(f"  - Found {len(candidates)} candidates")
            for c in candidates:
                _log(f"    - [{c.problem_type.value}] {c.statement[:50]}...")
    except Exception as e:
        _log(f"  - FAILED: {e}")
        failures.append(
            FailureItem(
                failure_id=f"fl_{len(failures)+1:03d}",
                stage="discovery",
                reason=f"Discovery failed: {e}",
                suggested_next_action="課題発見処理を再試行してください",
            )
        )
        candidates = []

    # Step 5: Evaluate with personas
    if verbose:
        _log("Step 5: Evaluating with personas...")
    if candidates:
        try:
            candidates = evaluate_candidates(
                candidates,
                normalized.personas,
                llm,
                normalized.constraints.primary_persona,
            )
            if verbose:
                for c in candidates:
                    _log(f"  - [{c.decision.value}] {c.statement[:50]}...")
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                FailureItem(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage="evaluation",
                    reason=f"Evaluation failed: {e}",
                    suggested_next_action="評価処理を再試行してください",
                )
            )
            # Keep candidates with default decisions

    # Step 6: Consolidate into insights/open questions
    if verbose:
        _log("Step 6: Consolidating results...")
    try:
        insights, open_questions, confidence, status = consolidate(
            claims,
            assumptions,
            limitations,
            candidates,
            llm,
            domain,
            normalized.constraints.max_insights,
        )
        if verbose:
            _log(f"  - Insights: {len(insights)}")
            _log(f"  - Open Questions: {len(open_questions)}")
            _log(f"  - Confidence: {confidence:.2f}")
            _log(f"  - Status: {status.value}")
    except Exception as e:
        _log(f"  - FAILED: {e}")
        failures.append(
            FailureItem(
                failure_id=f"fl_{len(failures)+1:03d}",
                stage="consolidation",
                reason=f"Consolidation failed: {e}",
                suggested_next_action="統合処理を再試行してください",
            )
        )
        insights, open_questions = [], []
        confidence = 0.3
        status = RunStatus.PARTIAL if candidates else RunStatus.FAILED

    # Step 7: Build response
    if verbose:
        _log("Step 7: Building response...")
        _log(f"DONE! Status: {status.value}")

    return build_response(
        normalized_request=normalized,
        claims=claims,
        assumptions=assumptions,
        limitations=limitations,
        problem_candidates=candidates,
        insights=insights,
        open_questions=open_questions,
        evidence_refs=evidence_refs,
        failures=failures,
        confidence=confidence,
        status=status,
        source_units=source_units if normalized.options.include_source_units else None,
        started_at=started_at,
    )


# Convenience function
def run_insight(
    sources: list[dict],
    domain: str | None = None,
    personas: list[dict] | None = None,
    constraints: dict | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> InsightResponse:
    """Convenience function to run insight analysis.

    Args:
        sources: List of source dicts with 'source_id', 'content', and optionally 'title'.
        domain: Optional domain context.
        personas: Optional list of persona dicts.
        constraints: Optional constraints dict.
        llm: Optional LLM client.
        verbose: Print progress messages.

    Returns:
        InsightResponse with results.
    """
    from insight_core.schemas import (
        Constraints,
        InsightRequest,
        PersonaDefinition,
        Source,
    )

    # Build sources
    source_objs = []
    for s in sources:
        source_objs.append(
            Source(
                source_id=s.get("source_id", f"src_{len(source_objs)+1}"),
                source_type=s.get("source_type", "text"),
                title=s.get("title"),
                content=s["content"],
            )
        )

    # Build personas if provided
    persona_objs = None
    if personas:
        persona_objs = [PersonaDefinition(**p) for p in personas]

    # Build constraints
    constraints_obj = Constraints(domain=domain)
    if constraints:
        constraints_obj = Constraints(**constraints)

    request = InsightRequest(
        mode="insight",
        sources=source_objs,
        constraints=constraints_obj,
        personas=persona_objs,
    )

    return run_pipeline(request, llm, verbose)