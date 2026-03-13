"""Japanese summary generator module.

Generates a structured Japanese summary of the insight analysis results.
"""

from __future__ import annotations

import asyncio
import json

from insight_core.llm_client import LLMClient, complete_async_compat, get_stage_max_tokens
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    InsightItem,
    JapaneseSummary,
    LimitationItem,
    OpenQuestionItem,
    ProblemCandidateItem,
)


SUMMARY_MAX_TOKENS = get_stage_max_tokens("summary")


SUMMARY_PROMPT = """あなたは分析結果を日本語で分かりやすくまとめる専門家です。
以下の分析結果を読み取り、日本語の構造化された要約を作成してください。

## 入力データ
- Claims (主張): {claims_count}件
- Assumptions (前提): {assumptions_count}件
- Limitations (制約): {limitations_count}件
- Problem Candidates (課題候補): {problems_count}件
- Insights (洞察): {insights_count}件
- Open Questions (未解決問い): {questions_count}件
- Overall Confidence: {confidence}

## 詳細データ
```json
{data_json}
```

## 出力形式
以下のJSON形式で回答してください：
```json
{{
  "overview": "分析結果の全体概要を2-3文でまとめたもの",
  "key_claims": ["主要な主張1", "主要な主張2", ...],
  "problem_summary": [
    {{"statement": "課題の要約", "decision": "accept/reserve/reject/needs_more_evidence", "reason": "判断理由"}},
    ...
  ],
  "recommendations": ["推奨アクション1", "推奨アクション2", ...],
  "confidence_note": "信頼度{confidence}についての注記（データの質、網羅性などに基づく）"
}}
```

## 注意点
- 日本語で自然な表現を使用してください
- 専門用語は適切に説明を加えてください
- 課題候補は重要度の高い順に最大5件まで含めてください
- 推奨アクションは具体的で実行可能なものにしてください
"""


async def generate_japanese_summary_async(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    confidence: float,
    llm: LLMClient,
) -> JapaneseSummary:
    """Generate a Japanese summary of the analysis results.

    Args:
        claims: List of extracted claims
        assumptions: List of extracted assumptions
        limitations: List of extracted limitations
        problem_candidates: List of discovered problem candidates
        insights: List of generated insights
        open_questions: List of open questions
        confidence: Overall confidence score
        llm: LLM client for generating summary

    Returns:
        JapaneseSummary object
    """
    # Prepare data for the LLM
    data = {
        "claims": [
            {"id": c.id, "statement": c.statement, "confidence": c.confidence}
            for c in claims[:10]  # Limit to top 10
        ],
        "assumptions": [
            {"id": a.id, "statement": a.statement}
            for a in assumptions[:5]
        ],
        "limitations": [
            {"id": l.id, "statement": l.statement}
            for l in limitations[:5]
        ],
        "problem_candidates": [
            {
                "id": p.problem_id,
                "statement": p.statement,
                "problem_type": p.problem_type.value if p.problem_type else None,
                "decision": p.decision.value,
                "confidence": p.confidence,
                "persona_decisions": [
                    {"persona": s.persona_id, "decision": s.decision.value}
                    for s in p.persona_scores
                ],
            }
            for p in problem_candidates
        ],
        "insights": [
            {"id": i.id, "statement": i.statement}
            for i in insights[:3]
        ],
        "open_questions": [
            {"id": q.question_id, "statement": q.statement}
            for q in open_questions[:5]
        ],
    }

    prompt = SUMMARY_PROMPT.format(
        claims_count=len(claims),
        assumptions_count=len(assumptions),
        limitations_count=len(limitations),
        problems_count=len(problem_candidates),
        insights_count=len(insights),
        questions_count=len(open_questions),
        confidence=f"{confidence:.2f}",
        data_json=json.dumps(data, ensure_ascii=False, indent=2),
    )

    # Call LLM
    response = await complete_async_compat(
        llm,
        system_prompt="あなたは分析結果を日本語で分かりやすくまとめる専門家です。",
        user_prompt=prompt,
        temperature=0.7,
        max_tokens=SUMMARY_MAX_TOKENS,
    )

    # Parse response
    try:
        # Extract JSON from response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            return JapaneseSummary(
                overview=result.get("overview", ""),
                key_claims=result.get("key_claims", []),
                problem_summary=result.get("problem_summary", []),
                recommendations=result.get("recommendations", []),
                confidence_note=result.get("confidence_note", ""),
            )
    except (json.JSONDecodeError, KeyError) as e:
        pass

    # Fallback: Create a basic summary
    return JapaneseSummary(
        overview=f"分析が完了しました。{len(problem_candidates)}件の課題候補が見つかりました。",
        key_claims=[c.statement for c in claims[:3]],
        problem_summary=[
            {"statement": p.statement[:100], "decision": p.decision.value, "reason": ""}
            for p in problem_candidates[:3]
        ],
        recommendations=["詳細な分析結果を確認してください。"],
        confidence_note=f"総合信頼度: {confidence:.2f}",
    )


def generate_japanese_summary(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    problem_candidates: list[ProblemCandidateItem],
    insights: list[InsightItem],
    open_questions: list[OpenQuestionItem],
    confidence: float,
    llm: LLMClient,
) -> JapaneseSummary:
    """Synchronous wrapper for generate_japanese_summary_async."""
    return asyncio.run(
        generate_japanese_summary_async(
            claims,
            assumptions,
            limitations,
            problem_candidates,
            insights,
            open_questions,
            confidence,
            llm,
        )
    )