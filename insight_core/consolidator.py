"""Consolidator module.

Responsible for:
- Generating insights from problem candidates
- Converting weak candidates to open questions
- Computing top-level confidence
- Determining run status
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    Decision,
    DerivationType,
    EpistemicMode,
    EvidenceRef,
    FailureItem,
    InsightItem,
    LimitationItem,
    OpenQuestionItem,
    OpenQuestionStatus,
    ProblemCandidateItem,
    RunStatus,
    UpdateRule,
)


def build_insight_prompt(
    accepted_candidates: list[ProblemCandidateItem],
    domain: str | None = None,
) -> tuple[str, str]:
    """Build prompt for insight generation.

    Args:
        accepted_candidates: Accepted problem candidates.
        domain: Optional domain context.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    domain_context = f"\n対象領域: {domain}" if domain else ""

    system_prompt = f"""あなたは課題を統合して上位の洞察（insight）を導き出す専門家です。

複数の課題候補を統合し、本質的な問題構造や解決の方向性を示す洞察を生成してください。

洞察は以下の特徴を持つべきです：
- 候補の羅列ではなく、上位構造の説明
- 個別の問題を貫く共通のパターンや根本原因
- 次のアクションにつながる示唆

JSONフォーマット：
```json
{{
  "insights": [
    {{
      "statement": "洞察の内容",
      "confidence": 0.0-1.0,
      "related_candidate_ids": ["関連する課題候補のID"]
    }}
  ]
}}
```{domain_context}"""

    candidates_text = "\n\n".join(
        [f"[{c.id}] {c.statement}\n  タイプ: {c.problem_type.value if c.problem_type else '不明'}\n  スコープ: {c.scope.value if c.scope else '不明'}"
         for c in accepted_candidates]
    )

    user_prompt = f"""以下の課題候補から洞察を生成してください。

[課題候補]
{candidates_text}

[出力]
JSON形式で洞察を出力してください。最大2件まで。"""

    return system_prompt, user_prompt


def generate_insights(
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
) -> list[InsightItem]:
    """Generate insights from accepted problem candidates.

    Args:
        candidates: Problem candidates (preferably accepted ones).
        llm: LLM client instance.
        domain: Optional domain context.
        max_insights: Maximum insights to generate.

    Returns:
        List of InsightItem objects.
    """
    # Filter to accepted/reserved candidates
    accepted = [c for c in candidates if c.decision in (Decision.ACCEPT, Decision.RESERVE)]

    if not accepted:
        return []

    system_prompt, user_prompt = build_insight_prompt(accepted, domain)

    try:
        response = llm.complete_json(system_prompt, user_prompt)
        insights: list[InsightItem] = []

        for i, insight_data in enumerate(response.get("insights", [])[:max_insights]):
            insight_id = f"in_{i+1:03d}"

            insights.append(
                InsightItem(
                    id=insight_id,
                    statement=insight_data["statement"],
                    epistemic_mode=EpistemicMode.INTERPRETATION,
                    derivation_type=DerivationType.CONTEXTUAL,
                    confidence=insight_data.get("confidence", 0.7),
                    evidence_refs=[],
                    parent_refs=insight_data.get("related_candidate_ids", []),
                    update_rule=UpdateRule.RETAIN,
                )
            )

        return insights
    except Exception:
        return []


def candidate_to_open_question(
    candidate: ProblemCandidateItem,
) -> OpenQuestionItem | None:
    """Convert a needs_more_evidence candidate to an open question.

    Args:
        candidate: Problem candidate with needs_more_evidence decision.

    Returns:
        OpenQuestionItem or None if not appropriate.
    """
    if candidate.decision != Decision.NEEDS_MORE_EVIDENCE:
        return None

    # Generate promotion and closure conditions
    promotion_condition = "追加の根拠や検証が得られること"
    closure_condition = f"課題「{candidate.statement[:50]}...」の実在性が確認または否定されること"

    review_after = datetime.now(timezone.utc) + timedelta(days=30)

    return OpenQuestionItem(
        question_id=f"oq_{candidate.problem_id}",
        statement=f"{candidate.statement} - 追加の検証が必要。",
        epistemic_mode=EpistemicMode.OPEN_QUESTION,
        derivation_type=DerivationType.INFERRED,
        confidence=candidate.confidence * 0.5,  # Lower confidence
        evidence_refs=candidate.evidence_refs,
        parent_refs=[candidate.problem_id],
        promotion_condition=promotion_condition,
        closure_condition=closure_condition,
        review_after=review_after,
        status=OpenQuestionStatus.OPEN,
        update_rule=UpdateRule.REVISE,
    )


def compute_run_confidence(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
) -> float:
    """Compute overall run confidence.

    Based on:
    - Number and quality of extracted items
    - Confidence of problem candidates
    - Presence of insights

    Args:
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        candidates: Problem candidates.
        insights: Generated insights.

    Returns:
        Overall confidence score (0.0-1.0).
    """
    scores = []

    # Extraction quality
    if claims:
        claim_avg = sum(c.confidence for c in claims) / len(claims)
        scores.append(claim_avg)

    if assumptions:
        assumption_avg = sum(a.confidence for a in assumptions) / len(assumptions)
        scores.append(assumption_avg * 0.8)  # Slightly lower weight

    if limitations:
        limitation_avg = sum(l.confidence for l in limitations) / len(limitations)
        scores.append(limitation_avg)

    # Problem candidate quality
    if candidates:
        accepted = [c for c in candidates if c.decision == Decision.ACCEPT]
        if accepted:
            scores.append(sum(c.confidence for c in accepted) / len(accepted))

    # Insight quality
    if insights:
        insight_avg = sum(i.confidence for i in insights) / len(insights)
        scores.append(insight_avg)

    if not scores:
        return 0.3  # Low default

    return sum(scores) / len(scores)


def determine_run_status(
    candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    failures: list[FailureItem],
    extraction_failed: bool = False,
) -> RunStatus:
    """Determine overall run status.

    Args:
        candidates: Problem candidates.
        insights: Generated insights.
        open_questions: Open questions.
        failures: Failures encountered.
        extraction_failed: Whether core extraction failed.

    Returns:
        RunStatus enum value.
    """
    if extraction_failed and not candidates and not insights:
        return RunStatus.FAILED

    accepted_count = sum(1 for c in candidates if c.decision == Decision.ACCEPT)

    if accepted_count >= 1 or len(insights) >= 1:
        if failures:
            return RunStatus.PARTIAL  # Completed but with issues
        return RunStatus.COMPLETED

    if open_questions:
        return RunStatus.PARTIAL

    if candidates:
        return RunStatus.PARTIAL

    return RunStatus.FAILED


def consolidate(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
) -> tuple[list[InsightItem], list[OpenQuestionItem], float, RunStatus]:
    """Consolidate results into final outputs.

    Args:
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        candidates: Evaluated problem candidates.
        llm: LLM client instance.
        domain: Optional domain context.
        max_insights: Maximum insights to generate.

    Returns:
        Tuple of (insights, open_questions, confidence, status).
    """
    # Generate insights from accepted candidates
    insights = generate_insights(candidates, llm, domain, max_insights)

    # Convert needs_more_evidence candidates to open questions
    open_questions: list[OpenQuestionItem] = []
    for candidate in candidates:
        oq = candidate_to_open_question(candidate)
        if oq:
            open_questions.append(oq)

    # Compute confidence
    confidence = compute_run_confidence(claims, assumptions, limitations, candidates, insights)

    # Determine status
    status = determine_run_status(candidates, insights, open_questions, [])

    return insights, open_questions, confidence, status