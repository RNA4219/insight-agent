"""Consolidator module.

Responsible for:
- Generating insights from problem candidates
- Converting weak candidates to open questions
- Computing top-level confidence
- Determining run status
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    Decision,
    DerivationType,
    FailureItem,
    InsightItem,
    LimitationItem,
    OpenQuestionItem,
    OpenQuestionStatus,
    ProblemCandidateItem,
    RunStatus,
    UpdateRule,
    EpistemicMode,
)


def build_insight_prompt(
    accepted_candidates: list[ProblemCandidateItem],
    domain: str | None = None,
) -> tuple[str, str]:
    """Build prompt for insight generation."""
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


async def generate_insights_async(
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
) -> list[InsightItem]:
    """Generate insights from accepted problem candidates."""
    accepted = [c for c in candidates if c.decision in (Decision.ACCEPT, Decision.RESERVE)]
    if not accepted:
        return []

    system_prompt, user_prompt = build_insight_prompt(accepted, domain)

    try:
        response = await llm.complete_json_async(system_prompt, user_prompt)
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


def generate_insights(
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
) -> list[InsightItem]:
    """Sync wrapper for insight generation."""
    return asyncio.run(generate_insights_async(candidates, llm, domain, max_insights))


def candidate_to_open_question(candidate: ProblemCandidateItem) -> OpenQuestionItem | None:
    """Convert a needs_more_evidence candidate to an open question."""
    if candidate.decision != Decision.NEEDS_MORE_EVIDENCE:
        return None

    promotion_condition = "追加の根拠や検証が得られること"
    closure_condition = f"課題「{candidate.statement[:50]}...」の実在性が確認または否定されること"
    review_after = datetime.now(timezone.utc) + timedelta(days=30)

    return OpenQuestionItem(
        question_id=f"oq_{candidate.problem_id}",
        statement=f"{candidate.statement} - 追加の検証が必要。",
        epistemic_mode=EpistemicMode.OPEN_QUESTION,
        derivation_type=DerivationType.INFERRED,
        confidence=candidate.confidence * 0.5,
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
    """Compute overall run confidence."""
    scores = []
    if claims:
        scores.append(sum(c.confidence for c in claims) / len(claims))
    if assumptions:
        scores.append((sum(a.confidence for a in assumptions) / len(assumptions)) * 0.8)
    if limitations:
        scores.append(sum(l.confidence for l in limitations) / len(limitations))
    if candidates:
        accepted = [c for c in candidates if c.decision == Decision.ACCEPT]
        if accepted:
            scores.append(sum(c.confidence for c in accepted) / len(accepted))
    if insights:
        scores.append(sum(i.confidence for i in insights) / len(insights))
    if not scores:
        return 0.3
    return sum(scores) / len(scores)


def determine_run_status(
    candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    failures: list[FailureItem],
    extraction_failed: bool = False,
) -> RunStatus:
    """Determine overall run status."""
    if extraction_failed and not candidates and not insights:
        return RunStatus.FAILED

    accepted_count = sum(1 for c in candidates if c.decision == Decision.ACCEPT)
    if accepted_count >= 1 or len(insights) >= 1:
        return RunStatus.PARTIAL if failures else RunStatus.COMPLETED
    if open_questions or candidates:
        return RunStatus.PARTIAL
    return RunStatus.FAILED


async def consolidate_async(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
    failures: list[FailureItem] | None = None,
) -> tuple[list[InsightItem], list[OpenQuestionItem], float, RunStatus]:
    """Consolidate results into final outputs."""
    insights = await generate_insights_async(candidates, llm, domain, max_insights)

    open_questions: list[OpenQuestionItem] = []
    for candidate in candidates:
        oq = candidate_to_open_question(candidate)
        if oq:
            open_questions.append(oq)

    confidence = compute_run_confidence(claims, assumptions, limitations, candidates, insights)
    status = determine_run_status(candidates, insights, open_questions, failures or [])
    return insights, open_questions, confidence, status


def consolidate(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    candidates: list[ProblemCandidateItem],
    llm: LLMClient,
    domain: str | None = None,
    max_insights: int = 2,
    failures: list[FailureItem] | None = None,
) -> tuple[list[InsightItem], list[OpenQuestionItem], float, RunStatus]:
    """Sync wrapper for consolidation."""
    return asyncio.run(
        consolidate_async(claims, assumptions, limitations, candidates, llm, domain, max_insights, failures)
    )
