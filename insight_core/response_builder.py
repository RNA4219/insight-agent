"""Response builder module.

Responsible for:
- Constructing InsightResponse
- Handling include_source_units option
- Integrating failures into final response
"""

from __future__ import annotations

from datetime import datetime, timezone

from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    EvidenceRef,
    FailureItem,
    InsightItem,
    InsightResponse,
    LimitationItem,
    NormalizedRequest,
    OpenQuestionItem,
    PersonaSource,
    ProblemCandidateItem,
    RunInfo,
    RunStatus,
    SourceUnit,
)


def build_response(
    normalized_request: NormalizedRequest,
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    evidence_refs: list[EvidenceRef],
    failures: list[FailureItem],
    confidence: float,
    status: RunStatus,
    source_units: list[SourceUnit] | None = None,
    started_at: datetime | None = None,
) -> InsightResponse:
    """Build the final InsightResponse.

    Args:
        normalized_request: Normalized request with metadata.
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        problem_candidates: Evaluated problem candidates.
        insights: Generated insights.
        open_questions: Open questions.
        evidence_refs: Evidence references.
        failures: Failures encountered.
        confidence: Overall confidence score.
        status: Run status.
        source_units: Optional source units (if include_source_units).
        started_at: When processing started.

    Returns:
        Complete InsightResponse object.
    """
    now = datetime.now(timezone.utc)
    start_time = started_at or now

    # Build persona catalog version
    persona_catalog_version: str | None = None
    if normalized_request.persona_source == PersonaSource.DEFAULT:
        persona_catalog_version = normalized_request.persona_catalog_version
    elif normalized_request.persona_source == PersonaSource.REQUEST:
        persona_catalog_version = "request_inline"
    elif normalized_request.persona_source == PersonaSource.MERGED:
        persona_catalog_version = normalized_request.persona_catalog_version

    # Build run info
    run = RunInfo(
        run_id=normalized_request.run_id,
        request_id=normalized_request.request_id,
        mode="insight",
        status=status,
        started_at=start_time,
        finished_at=now,
        applied_personas=[p.persona_id for p in normalized_request.personas],
        persona_source=normalized_request.persona_source,
        persona_catalog_version=persona_catalog_version,
    )

    # Apply max constraints
    max_candidates = normalized_request.constraints.max_problem_candidates
    max_insights = normalized_request.constraints.max_insights

    final_candidates = problem_candidates[:max_candidates]
    final_insights = insights[:max_insights]

    # Include source units if requested
    final_source_units: list[SourceUnit] = []
    if normalized_request.options.include_source_units and source_units:
        final_source_units = source_units

    return InsightResponse(
        run=run,
        claims=claims,
        assumptions=assumptions,
        limitations=limitations,
        problem_candidates=final_candidates,
        insights=final_insights,
        open_questions=open_questions,
        evidence_refs=evidence_refs,
        failures=failures,
        confidence=confidence,
        source_units=final_source_units,
    )


def build_failure_response(
    normalized_request: NormalizedRequest,
    failures: list[FailureItem],
    started_at: datetime | None = None,
) -> InsightResponse:
    """Build a failure response when processing cannot continue.

    Args:
        normalized_request: Normalized request with metadata.
        failures: Failures that occurred.
        started_at: When processing started.

    Returns:
        InsightResponse with failed status.
    """
    now = datetime.now(timezone.utc)
    start_time = started_at or now

    run = RunInfo(
        run_id=normalized_request.run_id,
        request_id=normalized_request.request_id,
        mode="insight",
        status=RunStatus.FAILED,
        started_at=start_time,
        finished_at=now,
        applied_personas=[p.persona_id for p in normalized_request.personas],
        persona_source=normalized_request.persona_source,
        persona_catalog_version=normalized_request.persona_catalog_version,
    )

    return InsightResponse(
        run=run,
        claims=[],
        assumptions=[],
        limitations=[],
        problem_candidates=[],
        insights=[],
        open_questions=[],
        evidence_refs=[],
        failures=failures,
        confidence=0.0,
        source_units=[],
    )


def build_partial_response(
    normalized_request: NormalizedRequest,
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    evidence_refs: list[EvidenceRef],
    failures: list[FailureItem],
    confidence: float,
    source_units: list[SourceUnit] | None = None,
    started_at: datetime | None = None,
) -> InsightResponse:
    """Build a partial response when some processing failed.

    Args:
        normalized_request: Normalized request with metadata.
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        problem_candidates: Evaluated problem candidates.
        insights: Generated insights.
        open_questions: Open questions.
        evidence_refs: Evidence references.
        failures: Failures encountered.
        confidence: Overall confidence score.
        source_units: Optional source units.
        started_at: When processing started.

    Returns:
        InsightResponse with partial status.
    """
    return build_response(
        normalized_request=normalized_request,
        claims=claims,
        assumptions=assumptions,
        limitations=limitations,
        problem_candidates=problem_candidates,
        insights=insights,
        open_questions=open_questions,
        evidence_refs=evidence_refs,
        failures=failures,
        confidence=confidence,
        status=RunStatus.PARTIAL,
        source_units=source_units,
        started_at=started_at,
    )