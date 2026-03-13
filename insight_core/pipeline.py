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

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from insight_core.consolidator import consolidate_async
from insight_core.discovery import discover_problems_async
from insight_core.evaluator import evaluate_candidates_async
from insight_core.extractor import extract_from_units_async
from insight_core.llm_client import LLMClient
from insight_core.request_normalizer import normalize_request
from insight_core.result_formatter import build_agent_result
from insight_core.response_builder import build_failure_response, build_response
from insight_core.router import generate_routing_plan_async, load_routing_config, create_fallback_routing_plan, create_all_personas_routing_plan
from insight_core.router.density_estimator import estimate_evidence_density
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    EvidenceRef,
    FailureItem,
    InsightItem,
    InsightRequest,
    InsightResponse,
    LimitationItem,
    NormalizedRequest,
    OpenQuestionItem,
    ProblemCandidateItem,
    RoutingConfig,
    RoutingPlan,
    RunStatus,
    SourceUnit,
)
from insight_core.summarizer import generate_japanese_summary_async
from insight_core.unitizer import unitize_sources


CHECKPOINT_VERSION = 2
STAGE_UNITIZATION = "unitization"
STAGE_EXTRACTION = "extraction"
STAGE_ROUTING = "routing"
STAGE_DISCOVERY = "discovery"
STAGE_EVALUATION = "evaluation"
STAGE_CONSOLIDATION = "consolidation"
STAGE_SEQUENCE = [
    STAGE_UNITIZATION,
    STAGE_EXTRACTION,
    STAGE_ROUTING,
    STAGE_DISCOVERY,
    STAGE_EVALUATION,
    STAGE_CONSOLIDATION,
]


def _log(message: str) -> None:
    """Print progress message."""
    print(f"[InsightAgent] {message}", file=sys.stderr, flush=True)


def _make_failure(
    failure_id: str,
    stage: str,
    reason: str,
    details: str | None = None,
    related_refs: list[str] | None = None,
    suggested_next_action: str | None = None,
) -> FailureItem:
    return FailureItem(
        failure_id=failure_id,
        stage=stage,
        reason=reason,
        details=details,
        related_refs=related_refs or [],
        suggested_next_action=suggested_next_action,
    )


def _without_stage_failures(failures: list[FailureItem], stage: str) -> list[FailureItem]:
    return [failure for failure in failures if failure.stage != stage]


def _request_fingerprint(normalized: NormalizedRequest) -> str:
    payload = normalized.model_dump(mode="json")
    payload.pop("run_id", None)
    payload.pop("request_id", None)
    options = payload.get("options", {})
    options.pop("checkpoint_path", None)
    options.pop("resume", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _checkpoint_path(normalized: NormalizedRequest) -> Path | None:
    if not normalized.options.checkpoint_path:
        return None
    return Path(normalized.options.checkpoint_path)


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_checkpoint(
    path: Path,
    normalized: NormalizedRequest,
    started_at: datetime,
    completed_stages: set[str],
    failures: list[FailureItem],
    source_units: list[SourceUnit],
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
    routing_plan: RoutingPlan | None,
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    confidence: float,
    status: RunStatus | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CHECKPOINT_VERSION,
        "request_fingerprint": _request_fingerprint(normalized),
        "normalized_request": normalized.model_dump(mode="json"),
        "started_at": started_at.isoformat(),
        "completed_stages": sorted(completed_stages),
        "failures": [item.model_dump(mode="json") for item in failures],
        "source_units": [item.model_dump(mode="json") for item in source_units],
        "claims": [item.model_dump(mode="json") for item in claims],
        "assumptions": [item.model_dump(mode="json") for item in assumptions],
        "limitations": [item.model_dump(mode="json") for item in limitations],
        "evidence_refs": [item.model_dump(mode="json") for item in evidence_refs],
        "routing_plan": routing_plan.model_dump(mode="json") if routing_plan else None,
        "problem_candidates": [item.model_dump(mode="json", by_alias=True) for item in problem_candidates],
        "insights": [item.model_dump(mode="json") for item in insights],
        "open_questions": [item.model_dump(mode="json") for item in open_questions],
        "confidence": confidence,
        "status": status.value if status else None,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _restore_from_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "started_at": datetime.fromisoformat(checkpoint["started_at"]),
        "completed_stages": set(checkpoint.get("completed_stages", [])),
        "failures": [FailureItem.model_validate(item) for item in checkpoint.get("failures", [])],
        "source_units": [SourceUnit.model_validate(item) for item in checkpoint.get("source_units", [])],
        "claims": [ClaimItem.model_validate(item) for item in checkpoint.get("claims", [])],
        "assumptions": [AssumptionItem.model_validate(item) for item in checkpoint.get("assumptions", [])],
        "limitations": [LimitationItem.model_validate(item) for item in checkpoint.get("limitations", [])],
        "evidence_refs": [EvidenceRef.model_validate(item) for item in checkpoint.get("evidence_refs", [])],
        "routing_plan": RoutingPlan.model_validate(item) if (item := checkpoint.get("routing_plan")) else None,
        "problem_candidates": [ProblemCandidateItem.model_validate(item) for item in checkpoint.get("problem_candidates", [])],
        "insights": [InsightItem.model_validate(item) for item in checkpoint.get("insights", [])],
        "open_questions": [OpenQuestionItem.model_validate(item) for item in checkpoint.get("open_questions", [])],
        "confidence": checkpoint.get("confidence", 0.0),
        "status": RunStatus(checkpoint["status"]) if checkpoint.get("status") else None,
    }


def _contiguous_completed_stages(completed_stages: set[str]) -> set[str]:
    contiguous: set[str] = set()
    for stage in STAGE_SEQUENCE:
        if stage in completed_stages:
            contiguous.add(stage)
        else:
            break
    return contiguous


async def run_pipeline_async(
    request: InsightRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> InsightResponse:
    """Run the complete insight agent pipeline asynchronously."""
    started_at = datetime.now(timezone.utc)
    failures: list[FailureItem] = []

    if verbose:
        _log("Starting pipeline...")

    if llm is None:
        llm = LLMClient()

    if verbose:
        _log(f"Using LLM: {llm.provider} / {llm.model}")

    if verbose:
        _log("Step 1: Normalizing request...")
    try:
        normalized, _, _ = normalize_request(request)
        if verbose:
            _log(f"  - Request ID: {normalized.request_id}")
            _log(f"  - Sources: {len(normalized.sources)}")
            _log(f"  - Personas: {len(normalized.personas)}")
    except ValueError as e:
        _log(f"  - FAILED: {e}")
        failure = _make_failure(
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

    checkpoint_path = _checkpoint_path(normalized)
    completed_stages: set[str] = set()
    source_units: list[SourceUnit] = []
    claims: list[ClaimItem] = []
    assumptions: list[AssumptionItem] = []
    limitations: list[LimitationItem] = []
    evidence_refs: list[EvidenceRef] = []
    routing_plan: RoutingPlan | None = None
    candidates: list[ProblemCandidateItem] = []
    insights: list[InsightItem] = []
    open_questions: list[OpenQuestionItem] = []
    confidence = 0.0
    status: RunStatus | None = None

    # Load routing config
    routing_config = load_routing_config()

    if checkpoint_path and normalized.options.resume:
        checkpoint = _load_checkpoint(checkpoint_path)
        if checkpoint and checkpoint.get("request_fingerprint") == _request_fingerprint(normalized):
            restored = _restore_from_checkpoint(checkpoint)
            started_at = restored["started_at"]
            completed_stages = _contiguous_completed_stages(restored["completed_stages"])
            failures = restored["failures"]
            source_units = restored["source_units"] if STAGE_UNITIZATION in completed_stages else []
            if STAGE_EXTRACTION in completed_stages:
                claims = restored["claims"]
                assumptions = restored["assumptions"]
                limitations = restored["limitations"]
                evidence_refs = restored["evidence_refs"]
            if STAGE_ROUTING in completed_stages:
                routing_plan = restored["routing_plan"]
            if STAGE_DISCOVERY in completed_stages:
                candidates = restored["problem_candidates"]
            if STAGE_CONSOLIDATION in completed_stages:
                insights = restored["insights"]
                open_questions = restored["open_questions"]
                confidence = restored["confidence"]
                status = restored["status"]
            if verbose:
                _log(f"Resuming from checkpoint: {checkpoint_path}")

    async def persist_checkpoint() -> None:
        if checkpoint_path is None:
            return
        await asyncio.to_thread(
            _save_checkpoint,
            checkpoint_path,
            normalized,
            started_at,
            completed_stages,
            failures,
            source_units,
            claims,
            assumptions,
            limitations,
            evidence_refs,
            routing_plan,
            candidates,
            insights,
            open_questions,
            confidence,
            status,
        )

    domain = normalized.constraints.domain
    max_concurrency = normalized.options.max_concurrency

    if STAGE_UNITIZATION not in completed_stages:
        if verbose:
            _log("Step 2: Unitizing sources...")
        failures = _without_stage_failures(failures, STAGE_UNITIZATION)
        try:
            source_units = unitize_sources(normalized.sources)
            if verbose:
                _log(f"  - Created {len(source_units)} units")
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage=STAGE_UNITIZATION,
                    reason=f"Source unitization failed: {e}",
                    suggested_next_action="Source contentを確認してください",
                )
            )
            await persist_checkpoint()
            return build_failure_response(normalized, failures, started_at)

        if not source_units:
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage=STAGE_UNITIZATION,
                    reason="No valid source units generated",
                    suggested_next_action="有効なコンテンツを含むsourceを提供してください",
                )
            )
            await persist_checkpoint()
            return build_failure_response(normalized, failures, started_at)

        completed_stages.add(STAGE_UNITIZATION)
        await persist_checkpoint()
    elif verbose:
        _log(f"Step 2: Unitizing sources... skipped ({len(source_units)} units restored)")

    if STAGE_EXTRACTION not in completed_stages:
        if verbose:
            _log("Step 3: Extracting claims/assumptions/limitations...")
        failures = _without_stage_failures(failures, STAGE_EXTRACTION)
        try:
            claims, assumptions, limitations, evidence_refs, failed_unit_ids = await extract_from_units_async(
                source_units,
                llm,
                domain,
                max_concurrency,
            )
            if verbose:
                _log(f"  - Claims: {len(claims)}")
                _log(f"  - Assumptions: {len(assumptions)}")
                _log(f"  - Limitations: {len(limitations)}")
            if failed_unit_ids:
                failures.append(
                    _make_failure(
                        failure_id=f"fl_{len(failures)+1:03d}",
                        stage=STAGE_EXTRACTION,
                        reason=f"Extraction failed for {len(failed_unit_ids)} units",
                        details=f"Failed units: {', '.join(failed_unit_ids[:5])}",
                        related_refs=failed_unit_ids[:5],
                        suggested_next_action="該当unitの内容を確認してください",
                    )
                )
            completed_stages.add(STAGE_EXTRACTION)
            await persist_checkpoint()
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage=STAGE_EXTRACTION,
                    reason=f"Extraction pipeline failed: {e}",
                    suggested_next_action="抽出処理を再試行してください",
                )
            )
            claims, assumptions, limitations, evidence_refs = [], [], [], []
            status = RunStatus.FAILED
            await persist_checkpoint()
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
    elif verbose:
        _log("Step 3: Extracting claims/assumptions/limitations... skipped (restored)")

    # Step 4: Routing (determine which personas to invoke)
    if STAGE_ROUTING not in completed_stages:
        if verbose:
            _log("Step 4: Routing personas...")
        failures = _without_stage_failures(failures, STAGE_ROUTING)
        if routing_config.enabled:
            try:
                # Estimate evidence density
                evidence_density = estimate_evidence_density(claims, limitations, evidence_refs)
                if verbose:
                    _log(f"  - Evidence density: {evidence_density.value}")

                # Generate routing plan
                routing_plan = await generate_routing_plan_async(
                    claims,
                    assumptions,
                    limitations,
                    evidence_refs,
                    None,  # problem_type will be determined later
                    normalized.personas,
                    llm,
                    routing_config,
                )
                if verbose:
                    _log(f"  - Lead persona: {routing_plan.lead_persona}")
                    _log(f"  - Selected personas: {routing_plan.selected_personas}")
                    _log(f"  - Skipped personas: {routing_plan.skipped_personas}")
            except Exception as e:
                _log(f"  - FAILED: {e}")
                failures.append(
                    _make_failure(
                        failure_id=f"fl_{len(failures)+1:03d}",
                        stage=STAGE_ROUTING,
                        reason=f"Routing failed: {e}",
                        suggested_next_action="ルーティング処理を再試行してください",
                    )
                )
                routing_plan = create_fallback_routing_plan(routing_config, str(e))
                if verbose:
                    _log(f"  - Using fallback routing: {routing_plan.selected_personas}")
        else:
            # Routing disabled - use all personas
            routing_plan = create_all_personas_routing_plan(
                [p.persona_id for p in normalized.personas],
                routing_config.lead_persona,
            )
            if verbose:
                _log("  - Routing disabled, using all personas")

        completed_stages.add(STAGE_ROUTING)
        await persist_checkpoint()
    elif verbose:
        if routing_plan:
            _log(f"Step 4: Routing personas... skipped ({routing_plan.lead_persona} -> {len(routing_plan.selected_personas)} personas)")

    # Determine which personas to use for evaluation
    selected_persona_ids = set(routing_plan.selected_personas) if routing_plan else set(p.persona_id for p in normalized.personas)
    selected_personas = [p for p in normalized.personas if p.persona_id in selected_persona_ids]

    if STAGE_DISCOVERY not in completed_stages:
        if verbose:
            _log("Step 5: Discovering problem candidates...")
        failures = _without_stage_failures(failures, STAGE_DISCOVERY)
        try:
            candidates = await discover_problems_async(
                claims,
                assumptions,
                limitations,
                llm,
                domain,
                normalized.constraints.max_problem_candidates,
                personas=normalized.personas,
            )
            if verbose:
                _log(f"  - Found {len(candidates)} candidates")
            completed_stages.add(STAGE_DISCOVERY)
            await persist_checkpoint()
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage=STAGE_DISCOVERY,
                    reason=f"Discovery failed: {e}",
                    suggested_next_action="課題発見処理を再試行してください",
                )
            )
            status = RunStatus.FAILED
            await persist_checkpoint()
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
                routing_plan=routing_plan,
                started_at=started_at,
            )
    elif verbose:
        _log(f"Step 5: Discovering problem candidates... skipped ({len(candidates)} restored)")

    if STAGE_EVALUATION not in completed_stages:
        if verbose:
            _log("Step 6: Evaluating with personas...")
        failures = _without_stage_failures(failures, STAGE_EVALUATION)
        if candidates:
            try:
                candidates = await evaluate_candidates_async(
                    candidates,
                    selected_personas,  # Use only selected personas
                    llm,
                    normalized.constraints.primary_persona,
                    max_concurrency,
                )
                if verbose:
                    for c in candidates:
                        _log(f"  - [{c.decision.value}] {c.statement[:50]}...")
            except Exception as e:
                _log(f"  - FAILED: {e}")
                failures.append(
                    _make_failure(
                        failure_id=f"fl_{len(failures)+1:03d}",
                        stage=STAGE_EVALUATION,
                        reason=f"Evaluation failed: {e}",
                        suggested_next_action="評価処理を再試行してください",
                    )
                )
                status = RunStatus.PARTIAL
                await persist_checkpoint()
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
                    routing_plan=routing_plan,
                    started_at=started_at,
                )

        completed_stages.add(STAGE_EVALUATION)
        await persist_checkpoint()
    elif verbose:
        _log("Step 6: Evaluating with personas... skipped (restored)")

    if STAGE_CONSOLIDATION not in completed_stages:
        if verbose:
            _log("Step 7: Consolidating results...")
        failures = _without_stage_failures(failures, STAGE_CONSOLIDATION)
        try:
            insights, open_questions, confidence, status = await consolidate_async(
                claims,
                assumptions,
                limitations,
                candidates,
                llm,
                domain,
                normalized.constraints.max_insights,
                failures,
            )
            if verbose:
                _log(f"  - Insights: {len(insights)}")
                _log(f"  - Open Questions: {len(open_questions)}")
                _log(f"  - Confidence: {confidence:.2f}")
                _log(f"  - Status: {status.value}")
            completed_stages.add(STAGE_CONSOLIDATION)
            await persist_checkpoint()
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage=STAGE_CONSOLIDATION,
                    reason=f"Consolidation failed: {e}",
                    suggested_next_action="統合処理を再試行してください",
                )
            )
            insights, open_questions = [], []
            confidence = 0.3
            status = RunStatus.PARTIAL if candidates else RunStatus.FAILED
            await persist_checkpoint()
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
                routing_plan=routing_plan,
                started_at=started_at,
            )
    elif verbose and status is not None:
        _log(f"Step 7: Consolidating results... skipped ({status.value} restored)")

    # Step 8: Japanese Summary (optional)
    japanese_summary = None
    if normalized.options.include_japanese_summary and status is not None:
        if verbose:
            _log("Step 8: Generating Japanese summary...")
        try:
            japanese_summary = await generate_japanese_summary_async(
                claims=claims,
                assumptions=assumptions,
                limitations=limitations,
                problem_candidates=candidates,
                insights=insights,
                open_questions=open_questions,
                confidence=confidence,
                llm=llm,
            )
            if verbose:
                _log(f"  - Overview: {japanese_summary.overview[:50]}...")
        except Exception as e:
            _log(f"  - FAILED: {e}")
            failures.append(
                _make_failure(
                    failure_id=f"fl_{len(failures)+1:03d}",
                    stage="summarization",
                    reason=f"Japanese summary generation failed: {e}",
                    suggested_next_action="要約処理を再試行してください",
                )
            )

    if verbose and status is not None:
        step_num = 9 if normalized.options.include_japanese_summary else 8
        _log(f"Step {step_num}: Building response...")
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
        status=status or RunStatus.FAILED,
        source_units=source_units if normalized.options.include_source_units else None,
        routing_plan=routing_plan,
        started_at=started_at,
        japanese_summary=japanese_summary,
    )


def run_pipeline(
    request: InsightRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> InsightResponse:
    """Run the complete insight agent pipeline."""
    return asyncio.run(run_pipeline_async(request, llm, verbose))


async def run_pipeline_result_async(
    request: InsightRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the pipeline and return the compact API/CLI result contract."""
    response = await run_pipeline_async(request, llm, verbose)
    return build_agent_result(request, response)


def run_pipeline_result(
    request: InsightRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the pipeline and return the compact API/CLI result contract."""
    return asyncio.run(run_pipeline_result_async(request, llm, verbose))


def run_insight(
    sources: list[dict],
    domain: str | None = None,
    personas: list[dict] | None = None,
    constraints: dict | None = None,
    options: dict | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> InsightResponse:
    """Convenience function to run insight analysis and return the raw internal response."""
    from insight_core.schemas import Constraints, InsightRequest, Options, PersonaDefinition, Source

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

    persona_objs = None
    if personas:
        persona_objs = [PersonaDefinition(**p) for p in personas]

    constraints_obj = Constraints(domain=domain)
    if constraints:
        constraints_obj = Constraints(**constraints)

    options_obj = Options()
    if options:
        options_obj = Options(**options)

    request = InsightRequest(
        mode="insight",
        sources=source_objs,
        constraints=constraints_obj,
        personas=persona_objs,
        options=options_obj,
    )

    return run_pipeline(request, llm, verbose)



def run_insight_result(
    sources: list[dict],
    domain: str | None = None,
    personas: list[dict] | None = None,
    constraints: dict | None = None,
    options: dict | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Convenience function to run insight analysis and return the compact API/CLI result contract."""
    from insight_core.schemas import Constraints, InsightRequest, Options, PersonaDefinition, Source

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

    persona_objs = None
    if personas:
        persona_objs = [PersonaDefinition(**p) for p in personas]

    constraints_obj = Constraints(domain=domain)
    if constraints:
        constraints_obj = Constraints(**constraints)

    options_obj = Options()
    if options:
        options_obj = Options(**options)

    request = InsightRequest(
        mode="insight",
        sources=source_objs,
        constraints=constraints_obj,
        personas=persona_objs,
        options=options_obj,
    )

    return run_pipeline_result(request, llm, verbose)
