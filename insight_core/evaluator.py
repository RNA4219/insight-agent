"""Evaluator module.

Responsible for:
- Scoring problem candidates by persona
- Normalizing persona weights
- Computing weighted scores
- Making persona-level decisions
"""

from __future__ import annotations

from typing import Any

from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    Decision,
    PersonaDefinition,
    PersonaScore,
    ProblemCandidateItem,
)


# Default axis names for scoring
DEFAULT_AXES = [
    "evidence_grounding",
    "novelty",
    "explanatory_power",
    "feasibility",
    "maintainability",
    "testability",
    "leverage",
    "robustness",
]


def build_evaluation_prompt(
    candidate: ProblemCandidateItem,
    persona: PersonaDefinition,
) -> tuple[str, str]:
    """Build prompt for persona-based evaluation.

    Args:
        candidate: Problem candidate to evaluate.
        persona: Persona definition for evaluation.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    system_prompt = f"""あなたは「{persona.name}」という視点で課題候補を評価する専門家です。

## あなたの役割
{persona.role or '専門的な観点から評価を行う'}

## あなたの特徴
{persona.description or '専門的な評価を行う'}

## 目標
{persona.objective}

## 重視する観点（優先軸）
{', '.join(persona.priorities) if persona.priorities else '特に指定なし'}

## 減点対象
{', '.join(persona.penalties) if persona.penalties else '特に指定なし'}

## 時間軸
{persona.time_horizon or '特に指定なし'}

## リスク許容度
{persona.risk_tolerance or '特に指定なし'}

## 根拠選好
{persona.evidence_preference or '特に指定なし'}

## 受け入れ判断基準
{persona.acceptance_rule}

---

以下の8軸で0.0-1.0のスコアを付けてください：
- evidence_grounding: 根拠の確かさ
- novelty: 新規性
- explanatory_power: 説明力
- feasibility: 実現可能性
- maintainability: 保守性
- testability: 検証可能性
- leverage: 波及効果
- robustness: 堅牢性

最後にdecision（accept/reserve/reject/needs_more_evidence）と、簡潔な理由を記載してください。

JSONフォーマット：
```json
{{
  "axis_scores": {{
    "evidence_grounding": 0.0-1.0,
    "novelty": 0.0-1.0,
    "explanatory_power": 0.0-1.0,
    "feasibility": 0.0-1.0,
    "maintainability": 0.0-1.0,
    "testability": 0.0-1.0,
    "leverage": 0.0-1.0,
    "robustness": 0.0-1.0
  }},
  "decision": "accept|reserve|reject|needs_more_evidence",
  "reason_summary": "判断理由の簡潔な説明"
}}
```"""

    user_prompt = f"""以下の課題候補を評価してください。

## 課題候補
{candidate.statement}

## タイプ
{candidate.problem_type.value if candidate.problem_type else '不明'}

## スコープ
{candidate.scope.value if candidate.scope else '不明'}

## 支持信号
{chr(10).join(['- ' + s for s in candidate.support_signals]) if candidate.support_signals else '（なし）'}

## 失敗信号
{chr(10).join(['- ' + s for s in candidate.failure_signals]) if candidate.failure_signals else '（なし）'}

## 致命的リスク
{chr(10).join(['- ' + r for r in candidate.fatal_risks]) if candidate.fatal_risks else '（なし）'}

---

JSON形式で評価結果を出力してください。"""

    return system_prompt, user_prompt


def parse_evaluation_response(
    response: dict[str, Any],
    persona: PersonaDefinition,
    normalized_weight: float,
) -> PersonaScore:
    """Parse LLM evaluation response into PersonaScore.

    Args:
        response: Parsed JSON response from LLM.
        persona: Persona that performed evaluation.
        normalized_weight: Normalized weight for this persona.

    Returns:
        PersonaScore object.
    """
    axis_scores = response.get("axis_scores", {})
    reason_summary = response.get("reason_summary")

    # Parse decision
    try:
        decision = Decision(response.get("decision", "reserve"))
    except ValueError:
        decision = Decision.RESERVE

    # Calculate weighted score
    # Prioritize axes that match persona's priorities
    if axis_scores:
        total_score = sum(axis_scores.values())
        avg_score = total_score / len(axis_scores) if axis_scores else 0.5

        # Boost score for priority axes
        priority_boost = 0.0
        if persona.priorities:
            priority_scores = [axis_scores.get(p, 0.5) for p in persona.priorities if p in axis_scores]
            if priority_scores:
                priority_avg = sum(priority_scores) / len(priority_scores)
                # Weighted average: 70% priority axes, 30% overall
                avg_score = (priority_avg * 0.7) + (avg_score * 0.3)

        weighted_score = min(1.0, max(0.0, avg_score))
    else:
        weighted_score = 0.5

    return PersonaScore(
        persona_id=persona.persona_id,
        axis_scores=axis_scores,
        weighted_score=weighted_score,
        applied_weight=normalized_weight,
        decision=decision,
        reason_summary=reason_summary,
    )


def evaluate_candidate(
    candidate: ProblemCandidateItem,
    personas: list[PersonaDefinition],
    llm: LLMClient,
) -> list[PersonaScore]:
    """Evaluate a problem candidate with all personas.

    Args:
        candidate: Problem candidate to evaluate.
        personas: List of personas to evaluate with.
        llm: LLM client instance.

    Returns:
        List of PersonaScore objects.
    """
    # Normalize weights
    total_weight = sum(p.weight for p in personas)
    normalized_weights = {p.persona_id: p.weight / total_weight for p in personas}

    scores: list[PersonaScore] = []

    for persona in personas:
        try:
            system_prompt, user_prompt = build_evaluation_prompt(candidate, persona)
            response = llm.complete_json(system_prompt, user_prompt)
            score = parse_evaluation_response(
                response, persona, normalized_weights[persona.persona_id]
            )
            scores.append(score)
        except Exception:
            # On failure, add a default reserved score
            scores.append(
                PersonaScore(
                    persona_id=persona.persona_id,
                    axis_scores={},
                    weighted_score=0.5,
                    applied_weight=normalized_weights[persona.persona_id],
                    decision=Decision.RESERVE,
                    reason_summary="評価エラーのため保留",
                )
            )

    return scores


def compute_integrated_decision(
    scores: list[PersonaScore],
    primary_persona_id: str | None = None,
) -> Decision:
    """Compute integrated decision from persona scores.

    Rules:
    - If data_researcher or operator rejects on feasibility/evidence/maintainability, overall reject
    - If primary_persona is set, prioritize their decision
    - Otherwise, use weighted voting

    Args:
        scores: List of persona scores.
        primary_persona_id: Optional primary persona ID.

    Returns:
        Integrated decision.
    """
    if not scores:
        return Decision.RESERVE

    # Check for critical rejectors
    critical_personas = {"data_researcher", "operator"}
    for score in scores:
        if score.persona_id in critical_personas and score.decision == Decision.REJECT:
            # Check if rejection is on critical axes
            axis_scores = score.axis_scores
            if axis_scores:
                critical_axes = ["evidence_grounding", "feasibility", "maintainability"]
                if any(axis_scores.get(ax, 1.0) < 0.4 for ax in critical_axes):
                    return Decision.REJECT

    # Check primary persona decision
    if primary_persona_id:
        for score in scores:
            if score.persona_id == primary_persona_id:
                if score.decision == Decision.REJECT:
                    return Decision.REJECT
                elif score.decision == Decision.ACCEPT:
                    # Primary accepts, but still check others
                    pass

    # Weighted voting
    accept_weight = sum(s.applied_weight for s in scores if s.decision == Decision.ACCEPT)
    reject_weight = sum(s.applied_weight for s in scores if s.decision == Decision.REJECT)

    if accept_weight > 0.5:
        return Decision.ACCEPT
    elif reject_weight > 0.5:
        return Decision.REJECT
    elif any(s.decision == Decision.NEEDS_MORE_EVIDENCE for s in scores):
        return Decision.NEEDS_MORE_EVIDENCE
    else:
        return Decision.RESERVE


def evaluate_candidates(
    candidates: list[ProblemCandidateItem],
    personas: list[PersonaDefinition],
    llm: LLMClient,
    primary_persona_id: str | None = None,
) -> list[ProblemCandidateItem]:
    """Evaluate all problem candidates with personas.

    Args:
        candidates: List of problem candidates to evaluate.
        personas: List of personas to evaluate with.
        llm: LLM client instance.
        primary_persona_id: Optional primary persona ID for tie-breaking.

    Returns:
        Updated problem candidates with persona_scores and decision.
    """
    if not candidates or not personas:
        return candidates

    for candidate in candidates:
        scores = evaluate_candidate(candidate, personas, llm)
        candidate.persona_scores = scores
        candidate.decision = compute_integrated_decision(scores, primary_persona_id)

    return candidates