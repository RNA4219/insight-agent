"""Discovery module.

Responsible for:
- Detecting gaps, omissions, contradictions
- Generating problem candidates
- Attaching support_signals, failure_signals, fatal_risks
"""

from __future__ import annotations

import asyncio
from typing import Any

NETWORK_ERROR_NAMES = {"APIConnectionError", "APITimeoutError", "ConnectError", "ReadTimeout", "TimeoutException"}


def _should_use_fallback(exc: Exception) -> bool:
    if exc.__class__.__name__ in NETWORK_ERROR_NAMES:
        return True
    message = str(exc).lower()
    return "connection error" in message or "timed out" in message or "forbidden" in message


from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    Decision,
    DerivationType,
    EpistemicMode,
    LimitationItem,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
    UpdateRule,
)


def build_discovery_prompt(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    domain: str | None = None,
) -> tuple[str, str]:
    domain_context = f"\n対象領域: {domain}" if domain else ""

    system_prompt = f"""あなたは課題発見の専門家です。
与えられた主張、前提、制約から、構造的な問題や課題候補を発見してください。

**重要**: 課題候補は本文の言い換えではなく、破綻可能性または構造的欠落を表現してください。

課題タイプ（problem_type）:
- evaluation_gap: 評価が不足している
- data_gap: データが不足している
- assumption_weakness: 前提が弱い
- contradiction: 矛盾がある
- omitted_factor: 重要な要素が考慮されていない
- operational_risk: 運用上のリスクがある
- scalability_limit: スケーラビリティの限界
- generalization_gap: 一般化に問題がある

スコープ（scope）:
- local: 特定の主張や項目に関連
- system: 全体的な設計や手法に関連
- global: 領域全体や根本的な問題

JSONフォーマットで出力してください：
```json
{{
  "problem_candidates": [
    {{
      "statement": "課題の記述（疑問形ではなく、問題状況を示す文で）",
      "problem_type": "evaluation_gap|data_gap|...",
      "scope": "local|system|global",
      "epistemic_mode": "hypothesis|interpretation",
      "confidence": 0.0-1.0,
      "support_signals": ["この課題を支持する信号"],
      "failure_signals": ["この課題が成立しない可能性を示す信号"],
      "fatal_risks": ["致命的な反証条件"],
      "related_claim_ids": ["関連するclaimのID"],
      "related_assumption_ids": ["関連するassumptionのID"],
      "related_limitation_ids": ["関連するlimitationのID"]
    }}
  ]
}}
```{domain_context}"""

    claims_text = "\n".join([f"- [{c.id}] {c.statement}" for c in claims]) if claims else "（なし）"
    assumptions_text = "\n".join([f"- [{a.id}] {a.statement}" for a in assumptions]) if assumptions else "（なし）"
    limitations_text = "\n".join([f"- [{l.id}] {l.statement}" for l in limitations]) if limitations else "（なし）"

    user_prompt = f"""以下の抽出結果から課題候補を発見してください。

[主張（Claims）]
{claims_text}

[前提（Assumptions）]
{assumptions_text}

[制約（Limitations）]
{limitations_text}

[出力]
JSON形式で課題候補を出力してください。最大5件まで。
本当に重要な構造的問題のみを抽出してください。"""

    return system_prompt, user_prompt


def _fallback_discovery_response(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    if limitations:
        top_limitations = limitations[:2]
        candidates.append(
            {
                "statement": "Documented limitations indicate that the evaluation boundary and operational robustness remain under-specified.",
                "problem_type": "evaluation_gap",
                "scope": "system",
                "epistemic_mode": "hypothesis",
                "confidence": 0.45,
                "support_signals": [item.statement[:120] for item in top_limitations],
                "failure_signals": [],
                "fatal_risks": [],
                "related_claim_ids": [claim.id for claim in claims[:2]],
                "related_assumption_ids": [assumption.id for assumption in assumptions[:1]],
                "related_limitation_ids": [item.id for item in top_limitations],
            }
        )

    if claims:
        candidates.append(
            {
                "statement": "The paper makes broad capability claims, but the evidence package does not clearly show how failure modes and transfer limits are validated.",
                "problem_type": "generalization_gap",
                "scope": "system",
                "epistemic_mode": "hypothesis",
                "confidence": 0.4,
                "support_signals": [claim.statement[:120] for claim in claims[:3]],
                "failure_signals": [],
                "fatal_risks": [],
                "related_claim_ids": [claim.id for claim in claims[:3]],
                "related_assumption_ids": [assumption.id for assumption in assumptions[:1]],
                "related_limitation_ids": [item.id for item in limitations[:1]],
            }
        )

    return {"problem_candidates": candidates[:5]}


def parse_discovery_response(
    response: dict[str, Any],
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
) -> list[ProblemCandidateItem]:
    candidates: list[ProblemCandidateItem] = []
    claim_ids = {c.id for c in claims}
    assumption_ids = {a.id for a in assumptions}
    limitation_ids = {l.id for l in limitations}

    for i, pb_data in enumerate(response.get("problem_candidates", [])):
        pb_id = f"pb_{i+1:03d}"
        related_claims = [cid for cid in pb_data.get("related_claim_ids", []) if cid in claim_ids]
        related_assumptions = [aid for aid in pb_data.get("related_assumption_ids", []) if aid in assumption_ids]
        related_limitations = [lid for lid in pb_data.get("related_limitation_ids", []) if lid in limitation_ids]

        try:
            problem_type = ProblemType(pb_data.get("problem_type", "evaluation_gap"))
        except ValueError:
            problem_type = ProblemType.EVALUATION_GAP

        try:
            scope = ProblemScope(pb_data.get("scope", "system"))
        except ValueError:
            scope = ProblemScope.SYSTEM

        try:
            epistemic_mode = EpistemicMode(pb_data.get("epistemic_mode", "hypothesis"))
        except ValueError:
            epistemic_mode = EpistemicMode.HYPOTHESIS

        candidates.append(
            ProblemCandidateItem(
                id=pb_id,
                problem_id=pb_id,
                statement=pb_data["statement"],
                problem_type=problem_type,
                scope=scope,
                epistemic_mode=epistemic_mode,
                derivation_type=DerivationType.INFERRED,
                confidence=pb_data.get("confidence", 0.6),
                evidence_refs=[],
                parent_refs=related_claims,
                assumption_refs=related_assumptions,
                limitation_refs=related_limitations,
                support_signals=pb_data.get("support_signals", []),
                failure_signals=pb_data.get("failure_signals", []),
                fatal_risks=pb_data.get("fatal_risks", []),
                decision=Decision.RESERVE,
                update_rule=UpdateRule.RETAIN,
            )
        )

    return candidates


async def discover_problems_async(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    llm: LLMClient,
    domain: str | None = None,
    max_candidates: int = 5,
) -> list[ProblemCandidateItem]:
    if not claims and not assumptions and not limitations:
        return []

    system_prompt, user_prompt = build_discovery_prompt(claims, assumptions, limitations, domain)

    try:
        response = await llm.complete_json_async(system_prompt, user_prompt)
    except Exception as exc:
        if not _should_use_fallback(exc):
            raise RuntimeError(f"Discovery failed: {exc}") from exc
        response = _fallback_discovery_response(claims, assumptions, limitations)

    candidates = parse_discovery_response(response, claims, assumptions, limitations)
    return candidates[:max_candidates]


def discover_problems(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    llm: LLMClient,
    domain: str | None = None,
    max_candidates: int = 5,
) -> list[ProblemCandidateItem]:
    return asyncio.run(discover_problems_async(claims, assumptions, limitations, llm, domain, max_candidates))
