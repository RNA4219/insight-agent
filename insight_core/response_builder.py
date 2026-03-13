"""Response builder module.

Responsible for:
- Constructing InsightResponse
- Handling include_source_units option
- Integrating failures into final response
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeVar

from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    EvidenceRef,
    FailureItem,
    InsightItem,
    InsightResponse,
    JapaneseSummary,
    LimitationItem,
    NormalizedRequest,
    OpenQuestionItem,
    PersonaScore,
    PersonaSource,
    ProblemCandidateItem,
    ReasoningSummary,
    RoutingPlan,
    RunInfo,
    RunStatus,
    SourceUnit,
)


TItem = TypeVar("TItem", ClaimItem, AssumptionItem, LimitationItem)
COMPACT_FALLBACK_ITEM_LIMIT = 5
COMPACT_EVIDENCE_QUOTE_LIMIT = 180
REASONING_STATEMENT_LIMIT = 84
REASONING_NOISE_PATTERNS = (
    " - 追加の検証が必要",
    " - 再検証が必要",
    "追加の検証が必要",
    "再検証が必要",
)
REASONING_TOPIC_TRANSLATION = str.maketrans("", "", " 　、。,.・:：;；()（）[]［］{}｛｝-ー_!?！？")


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _collect_referenced_item_ids(
    problem_candidates: list[ProblemCandidateItem],
) -> tuple[set[str], set[str], set[str]]:
    claim_ids: set[str] = set()
    assumption_ids: set[str] = set()
    limitation_ids: set[str] = set()

    for candidate in problem_candidates:
        claim_ids.update(candidate.parent_refs)
        assumption_ids.update(candidate.assumption_refs)
        limitation_ids.update(candidate.limitation_refs)

    return claim_ids, assumption_ids, limitation_ids


def _select_items_for_compact_output(items: list[TItem], referenced_ids: set[str]) -> list[TItem]:
    if referenced_ids:
        selected = [item for item in items if item.id in referenced_ids]
        if selected:
            return selected
    return items[:COMPACT_FALLBACK_ITEM_LIMIT]


def _compact_persona_scores(scores: list[PersonaScore]) -> list[PersonaScore]:
    compacted: list[PersonaScore] = []
    for score in scores:
        compacted.append(score.model_copy(update={"axis_scores": {}}))
    return compacted


def _compact_problem_candidates(candidates: list[ProblemCandidateItem]) -> list[ProblemCandidateItem]:
    compacted: list[ProblemCandidateItem] = []
    for candidate in candidates:
        compacted.append(
            candidate.model_copy(
                update={
                    "persona_scores": _compact_persona_scores(candidate.persona_scores),
                }
            )
        )
    return compacted


def _trim_evidence_refs(evidence_refs: list[EvidenceRef], allowed_ids: set[str]) -> list[EvidenceRef]:
    compacted: list[EvidenceRef] = []
    for evidence in evidence_refs:
        if evidence.evidence_id not in allowed_ids:
            continue
        quote = evidence.quote
        if quote and len(quote) > COMPACT_EVIDENCE_QUOTE_LIMIT:
            quote = quote[: COMPACT_EVIDENCE_QUOTE_LIMIT - 1] + "..."
        compacted.append(evidence.model_copy(update={"quote": quote}))
    return compacted


def _normalize_reasoning_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split())
    for pattern in REASONING_NOISE_PATTERNS:
        normalized = normalized.replace(pattern, "")
    normalized = normalized.strip(" 。.-")
    if len(normalized) > REASONING_STATEMENT_LIMIT:
        normalized = normalized[: REASONING_STATEMENT_LIMIT - 3].rstrip() + "..."
    return normalized


def _reasoning_topic_key(text: str) -> str:
    return text.translate(REASONING_TOPIC_TRANSLATION)



def _is_same_reasoning_topic(primary: str, secondary: str) -> bool:
    if not primary or not secondary:
        return False
    primary_key = _reasoning_topic_key(primary)
    secondary_key = _reasoning_topic_key(secondary)
    if not primary_key or not secondary_key:
        return False
    return (
        primary_key == secondary_key
        or primary_key in secondary_key
        or secondary_key in primary_key
    )


def _build_reasoning_summary(
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    problem_candidates: list[ProblemCandidateItem],
    failures: list[FailureItem],
) -> ReasoningSummary:
    top_insight = _normalize_reasoning_text(insights[0].statement) if insights else ""
    second_insight = _normalize_reasoning_text(insights[1].statement) if len(insights) > 1 else ""
    top_question = _normalize_reasoning_text(open_questions[0].statement) if open_questions else ""
    top_candidate = _normalize_reasoning_text(problem_candidates[0].statement) if problem_candidates else ""

    if top_insight:
        if second_insight and not _is_same_reasoning_topic(top_insight, second_insight):
            short_text = f"見立て: {top_insight}。補足: {second_insight}。"
        elif top_question and not _is_same_reasoning_topic(top_insight, top_question):
            short_text = f"見立て: {top_insight}。残る論点: {top_question}。"
        else:
            short_text = f"見立て: {top_insight}。"
    elif top_candidate:
        if top_question and not _is_same_reasoning_topic(top_candidate, top_question):
            short_text = f"有力な仮説: {top_candidate}。残る論点: {top_question}。"
        else:
            short_text = f"有力な仮説: {top_candidate}。"
    elif top_question:
        short_text = f"残る論点: {top_question}。"
    elif failures:
        short_text = "有力な仮説は未確定。再試行が必要です。"
    else:
        short_text = "有力な仮説は未確定。追加の観測が必要です。"

    return ReasoningSummary(short_text=short_text)


def _collect_evidence_ids(*item_groups: list[object]) -> set[str]:
    evidence_ids: set[str] = set()
    for group in item_groups:
        for item in group:
            refs = getattr(item, "evidence_refs", []) or []
            evidence_ids.update(refs)
    return evidence_ids


def _compact_output_payload(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    evidence_refs: list[EvidenceRef],
) -> tuple[
    list[ClaimItem],
    list[AssumptionItem],
    list[LimitationItem],
    list[ProblemCandidateItem],
    list[InsightItem],
    list[OpenQuestionItem],
    list[EvidenceRef],
]:
    referenced_claim_ids, referenced_assumption_ids, referenced_limitation_ids = _collect_referenced_item_ids(problem_candidates)

    compact_claims = _select_items_for_compact_output(claims, referenced_claim_ids)
    compact_assumptions = _select_items_for_compact_output(assumptions, referenced_assumption_ids)
    compact_limitations = _select_items_for_compact_output(limitations, referenced_limitation_ids)
    compact_candidates = _compact_problem_candidates(problem_candidates)

    allowed_evidence_ids = _collect_evidence_ids(
        compact_claims,
        compact_assumptions,
        compact_limitations,
        compact_candidates,
        insights,
        open_questions,
    )
    compact_evidence_refs = _trim_evidence_refs(evidence_refs, allowed_evidence_ids)

    return (
        compact_claims,
        compact_assumptions,
        compact_limitations,
        compact_candidates,
        insights,
        open_questions,
        compact_evidence_refs,
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
    routing_plan: RoutingPlan | None = None,
    started_at: datetime | None = None,
    japanese_summary: JapaneseSummary | None = None,
) -> InsightResponse:
    """Build the final InsightResponse."""
    now = datetime.now(timezone.utc)
    start_time = started_at or now

    persona_catalog_version: str | None = None
    if normalized_request.persona_source == PersonaSource.DEFAULT:
        persona_catalog_version = normalized_request.persona_catalog_version
    elif normalized_request.persona_source == PersonaSource.REQUEST:
        persona_catalog_version = "request_inline"
    elif normalized_request.persona_source == PersonaSource.MERGED:
        persona_catalog_version = normalized_request.persona_catalog_version

    if routing_plan:
        applied_personas = _dedupe_preserving_order([routing_plan.lead_persona] + routing_plan.selected_personas)
    else:
        applied_personas = _dedupe_preserving_order([p.persona_id for p in normalized_request.personas])

    run = RunInfo(
        run_id=normalized_request.run_id,
        request_id=normalized_request.request_id,
        mode="insight",
        status=status,
        started_at=start_time,
        finished_at=now,
        applied_personas=applied_personas,
        persona_source=normalized_request.persona_source,
        persona_catalog_version=persona_catalog_version,
    )

    max_candidates = normalized_request.constraints.max_problem_candidates
    max_insights = normalized_request.constraints.max_insights

    final_candidates = problem_candidates[:max_candidates]
    final_insights = insights[:max_insights]
    final_open_questions = open_questions[:max_candidates]

    final_claims = claims
    final_assumptions = assumptions
    final_limitations = limitations
    final_evidence_refs = evidence_refs

    if not normalized_request.options.include_intermediate_items:
        (
            final_claims,
            final_assumptions,
            final_limitations,
            final_candidates,
            final_insights,
            final_open_questions,
            final_evidence_refs,
        ) = _compact_output_payload(
            claims,
            assumptions,
            limitations,
            final_candidates,
            final_insights,
            final_open_questions,
            evidence_refs,
        )

    final_source_units: list[SourceUnit] = []
    if normalized_request.options.include_source_units and source_units:
        final_source_units = source_units

    reasoning_summary = _build_reasoning_summary(
        insights=final_insights,
        open_questions=final_open_questions,
        problem_candidates=final_candidates,
        failures=failures,
    )

    return InsightResponse(
        run=run,
        claims=final_claims,
        assumptions=final_assumptions,
        limitations=final_limitations,
        problem_candidates=final_candidates,
        insights=final_insights,
        open_questions=final_open_questions,
        evidence_refs=final_evidence_refs,
        failures=failures,
        confidence=confidence,
        source_units=final_source_units,
        routing_plan=routing_plan,
        japanese_summary=japanese_summary,
        reasoning_summary=reasoning_summary,
    )


def build_failure_response(
    normalized_request: NormalizedRequest,
    failures: list[FailureItem],
    started_at: datetime | None = None,
) -> InsightResponse:
    """Build a failure response when processing cannot continue."""
    now = datetime.now(timezone.utc)
    start_time = started_at or now

    run = RunInfo(
        run_id=normalized_request.run_id,
        request_id=normalized_request.request_id,
        mode="insight",
        status=RunStatus.FAILED,
        started_at=start_time,
        finished_at=now,
        applied_personas=_dedupe_preserving_order([p.persona_id for p in normalized_request.personas]),
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
        routing_plan=None,
        reasoning_summary=_build_reasoning_summary([], [], [], failures),
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
    routing_plan: RoutingPlan | None = None,
    started_at: datetime | None = None,
) -> InsightResponse:
    """Build a partial response when some processing failed."""
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
        routing_plan=routing_plan,
        started_at=started_at,
    )
