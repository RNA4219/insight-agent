"""Extractor module.

Responsible for:
- Extracting claims, assumptions, limitations from source units
- Linking evidence candidates to items
- Distinguishing direct extraction vs inference
"""

from __future__ import annotations

import asyncio
from typing import Any

from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    DerivationType,
    EpistemicMode,
    EvidenceRef,
    LimitationItem,
    SourceUnit,
    UpdateRule,
)


def build_extraction_prompt(unit: SourceUnit, domain: str | None = None) -> tuple[str, str]:
    """Build prompt for extraction."""
    domain_context = f"\n対象領域: {domain}" if domain else ""

    system_prompt = f"""あなたは学術・技術資料の分析専門家です。
与えられたテキストから以下を抽出してください：

1. **claims（主張）**: 著者が明示的に主張していること
   - 観察事実、測定結果、結論など
   - epistemic_mode: observation または interpretation
   - derivation_type: direct

2. **assumptions（前提）**: 明示的または暗黙的に仮定されていること
   - 前提条件、仮定、制約条件など
   - epistemic_mode: interpretation
   - derivation_type: direct または inferred

3. **limitations（制約・限界）**: 明示的な限界、評価不足、一般化の問題
   - 著者が認めている限界
   - 評価されていない側面
   - 適用範囲の制約
   - epistemic_mode: interpretation
   - derivation_type: direct または inferred
{domain_context}

JSONフォーマットで出力してください：
```json
{{
  "claims": [
    {{
      "statement": "主張の内容",
      "epistemic_mode": "observation|interpretation",
      "confidence": 0.0-1.0,
      "quote": "根拠となる引用文（可能な限り原文から抽出）"
    }}
  ],
  "assumptions": [
    {{
      "statement": "前提の内容",
      "is_explicit": true|false,
      "confidence": 0.0-1.0,
      "quote": "根拠となる引用文"
    }}
  ],
  "limitations": [
    {{
      "statement": "制約・限界の内容",
      "limitation_type": "explicit|evaluation_gap|generalization_gap|operational",
      "confidence": 0.0-1.0,
      "quote": "根拠となる引用文"
    }}
  ]
}}
```"""

    user_prompt = f"""以下のテキストから主張、前提、制約を抽出してください。

[テキスト]
{unit.content}

[出力]
JSON形式で出力してください。該当する項目がない場合は空配列にしてください。"""

    return system_prompt, user_prompt


def parse_extraction_response(
    response: dict[str, Any],
    unit: SourceUnit,
    evidence_counter: int,
) -> tuple[list[ClaimItem], list[AssumptionItem], list[LimitationItem], list[EvidenceRef], int]:
    """Parse LLM extraction response into items."""
    claims: list[ClaimItem] = []
    assumptions: list[AssumptionItem] = []
    limitations: list[LimitationItem] = []
    evidence_refs: list[EvidenceRef] = []

    item_counter = 0

    for claim_data in response.get("claims", []):
        item_counter += 1
        evidence_counter += 1
        claim_id = f"cl_{unit.unit_id}_{item_counter}"
        evidence_id = f"ev_{evidence_counter}"
        evidence_refs.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_id=unit.parent_source_id,
                unit_id=unit.unit_id,
                quote=claim_data.get("quote"),
            )
        )
        claims.append(
            ClaimItem(
                id=claim_id,
                statement=claim_data["statement"],
                epistemic_mode=EpistemicMode(claim_data.get("epistemic_mode", "interpretation")),
                derivation_type=DerivationType.DIRECT,
                confidence=claim_data.get("confidence", 0.7),
                evidence_refs=[evidence_id],
                update_rule=UpdateRule.RETAIN,
            )
        )

    for assumption_data in response.get("assumptions", []):
        item_counter += 1
        evidence_counter += 1
        assumption_id = f"as_{unit.unit_id}_{item_counter}"
        evidence_id = f"ev_{evidence_counter}"
        evidence_refs.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_id=unit.parent_source_id,
                unit_id=unit.unit_id,
                quote=assumption_data.get("quote"),
            )
        )
        assumptions.append(
            AssumptionItem(
                id=assumption_id,
                statement=assumption_data["statement"],
                epistemic_mode=EpistemicMode.INTERPRETATION,
                derivation_type=DerivationType.DIRECT if assumption_data.get("is_explicit") else DerivationType.INFERRED,
                confidence=assumption_data.get("confidence", 0.6),
                evidence_refs=[evidence_id],
                update_rule=UpdateRule.RETAIN,
            )
        )

    for limitation_data in response.get("limitations", []):
        item_counter += 1
        evidence_counter += 1
        limitation_id = f"lm_{unit.unit_id}_{item_counter}"
        evidence_id = f"ev_{evidence_counter}"
        evidence_refs.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_id=unit.parent_source_id,
                unit_id=unit.unit_id,
                quote=limitation_data.get("quote"),
            )
        )
        limitations.append(
            LimitationItem(
                id=limitation_id,
                statement=limitation_data["statement"],
                epistemic_mode=EpistemicMode.INTERPRETATION,
                derivation_type=DerivationType.DIRECT if limitation_data.get("limitation_type") == "explicit" else DerivationType.INFERRED,
                confidence=limitation_data.get("confidence", 0.7),
                evidence_refs=[evidence_id],
                update_rule=UpdateRule.RETAIN,
            )
        )

    return claims, assumptions, limitations, evidence_refs, evidence_counter


async def _extract_response_for_unit(
    unit: SourceUnit,
    llm: LLMClient,
    domain: str | None = None,
) -> dict[str, Any]:
    system_prompt, user_prompt = build_extraction_prompt(unit, domain)
    return await llm.complete_json_async(system_prompt, user_prompt)


async def extract_from_unit_async(
    unit: SourceUnit,
    llm: LLMClient,
    domain: str | None = None,
    evidence_counter: int = 0,
) -> tuple[list[ClaimItem], list[AssumptionItem], list[LimitationItem], list[EvidenceRef], int]:
    """Extract items from a single source unit."""
    try:
        response = await _extract_response_for_unit(unit, llm, domain)
        return parse_extraction_response(response, unit, evidence_counter)
    except Exception as e:
        raise RuntimeError(f"Extraction failed for unit {unit.unit_id}: {e}") from e


def extract_from_unit(
    unit: SourceUnit,
    llm: LLMClient,
    domain: str | None = None,
    evidence_counter: int = 0,
) -> tuple[list[ClaimItem], list[AssumptionItem], list[LimitationItem], list[EvidenceRef], int]:
    """Sync wrapper for single-unit extraction."""
    return asyncio.run(extract_from_unit_async(unit, llm, domain, evidence_counter))


async def extract_from_units_async(
    units: list[SourceUnit],
    llm: LLMClient,
    domain: str | None = None,
    max_concurrency: int = 4,
) -> tuple[list[ClaimItem], list[AssumptionItem], list[LimitationItem], list[EvidenceRef], list[str]]:
    """Extract items from multiple source units in parallel."""
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run_one(index: int, unit: SourceUnit):
        async with semaphore:
            try:
                response = await _extract_response_for_unit(unit, llm, domain)
                return index, unit, response, None
            except Exception as exc:
                return index, unit, None, exc

    tasks = [asyncio.create_task(run_one(index, unit)) for index, unit in enumerate(units)]
    raw_results = await asyncio.gather(*tasks)
    raw_results.sort(key=lambda item: item[0])

    all_claims: list[ClaimItem] = []
    all_assumptions: list[AssumptionItem] = []
    all_limitations: list[LimitationItem] = []
    all_evidence: list[EvidenceRef] = []
    failed_unit_ids: list[str] = []
    evidence_counter = 0

    for _, unit, response, error in raw_results:
        if error is not None or response is None:
            failed_unit_ids.append(unit.unit_id)
            continue

        claims, assumptions, limitations, evidence_refs, evidence_counter = parse_extraction_response(
            response,
            unit,
            evidence_counter,
        )
        all_claims.extend(claims)
        all_assumptions.extend(assumptions)
        all_limitations.extend(limitations)
        all_evidence.extend(evidence_refs)

    return all_claims, all_assumptions, all_limitations, all_evidence, failed_unit_ids


def extract_from_units(
    units: list[SourceUnit],
    llm: LLMClient,
    domain: str | None = None,
    max_concurrency: int = 4,
) -> tuple[list[ClaimItem], list[AssumptionItem], list[LimitationItem], list[EvidenceRef], list[str]]:
    """Sync wrapper for multi-unit extraction."""
    return asyncio.run(extract_from_units_async(units, llm, domain, max_concurrency))
