"""Lead persona routing plan generator.

Invokes the lead persona to generate a routing plan.
"""

from __future__ import annotations

import json
from typing import Any

from insight_core.llm_client import LLMClient
from insight_core.router.config import RoutingConfig
from insight_core.router.density_estimator import estimate_evidence_density
from insight_core.router.fallback import create_fallback_routing_plan
from insight_core.router.validator import (
    ensure_mandatory_audit_persona,
    validate_routing_plan,
)
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    EvidenceDensity,
    EvidenceRef,
    LimitationItem,
    PersonaDefinition,
    PersonaRole,
    ProblemType,
    RoutingPlan,
)


def build_routing_prompt(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
    problem_type: str | None,
    evidence_density: EvidenceDensity,
    available_personas: list[PersonaDefinition],
    config: RoutingConfig,
) -> tuple[str, str]:
    """Build prompt for lead persona routing.

    Args:
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        evidence_refs: Evidence references.
        problem_type: Optional problem type.
        evidence_density: Estimated evidence density.
        available_personas: List of available personas.
        config: Routing configuration.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    # Build persona list
    persona_list = "\n".join([
        f"- {p.persona_id}: {p.name} - {p.description or p.role or 'No description'}"
        for p in available_personas
    ])

    # Build claims summary
    claims_text = "\n".join([f"- {c.statement[:100]}" for c in claims[:5]]) if claims else "（なし）"

    # Build limitations summary
    limitations_text = "\n".join([f"- {l.statement[:100]}" for l in limitations[:5]]) if limitations else "（なし）"

    system_prompt = f"""あなたは「{config.lead_persona}」として、以下の分析結果から最適な評価者Personaを選定してください。

## あなたの役割
Lead Personaとして、どの下流Personaを呼び出すべきかを決定するルーティングを行います。

## 選択ルール
1. 証拠密度が「low」の場合、呼び出すPersona数を2-3に制限
2. 監査役Persona（data_researcher, operator等）を最低1名含める
3. novelty系Persona（curiosity_entertainer）は明確なメリットがある場合のみ選択
4. 各選択Personaに役割を割り当てる

## 利用可能な役割
- evidence_checker: 証拠確認
- hypothesis_refiner: 仮説精緻化
- operational_risk_reviewer: 運用リスクレビュー
- structural_abstraction: 構造的抽象化
- novelty_probe: 新規性探索

## 利用可能なPersona
{persona_list}

## 出力形式
以下のJSON形式でrouting_planを出力してください：
```json
{{
  "lead_persona": "{config.lead_persona}",
  "problem_type": "問題タイプ（省略可）",
  "evidence_density": "{evidence_density.value}",
  "selected_personas": ["persona_id1", "persona_id2"],
  "skipped_personas": ["persona_id3"],
  "role_assignments": {{
    "persona_id1": "evidence_checker",
    "persona_id2": "operational_risk_reviewer"
  }},
  "routing_reason": ["選択理由1", "選択理由2"],
  "skip_reasons": {{
    "persona_id3": "スキップ理由"
  }},
  "routing_confidence": 0.8
}}
```"""

    user_prompt = f"""以下の分析結果から評価者Personaを選定してください。

## 証拠密度
{evidence_density.value}

## 推定問題タイプ
{problem_type or "不明"}

## 主張（Claims）
{claims_text}

## 制約（Limitations）
{limitations_text}

## 選択要件
- 選択するPersona数: {config.max_personas_by_evidence_density.get(evidence_density.value, 4)}以下
- 必須監査Persona: {config.mandatory_audit_personas}

JSON形式でrouting_planを出力してください。"""

    return system_prompt, user_prompt


def parse_routing_response(
    response: dict[str, Any],
    config: RoutingConfig,
) -> RoutingPlan:
    """Parse LLM response into RoutingPlan.

    Args:
        response: Parsed JSON response from LLM.
        config: Routing configuration.

    Returns:
        RoutingPlan instance.
    """
    # Parse evidence density
    try:
        evidence_density = EvidenceDensity(
            response.get("evidence_density", "medium")
        )
    except ValueError:
        evidence_density = EvidenceDensity.MEDIUM

    # Parse role assignments
    role_assignments: dict[str, PersonaRole] = {}
    for persona_id, role_str in response.get("role_assignments", {}).items():
        try:
            role_assignments[persona_id] = PersonaRole(role_str)
        except ValueError:
            role_assignments[persona_id] = PersonaRole.EVIDENCE_CHECKER

    return RoutingPlan(
        lead_persona=response.get("lead_persona", config.lead_persona),
        problem_type=response.get("problem_type"),
        evidence_density=evidence_density,
        selected_personas=response.get("selected_personas", []),
        skipped_personas=response.get("skipped_personas", []),
        role_assignments=role_assignments,
        routing_reason=response.get("routing_reason", []),
        skip_reasons=response.get("skip_reasons", {}),
        routing_confidence=response.get("routing_confidence", 0.5),
    )


async def generate_routing_plan_async(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
    problem_type: str | None,
    available_personas: list[PersonaDefinition],
    llm: LLMClient,
    config: RoutingConfig,
) -> RoutingPlan:
    """Generate routing plan using lead persona (async).

    Args:
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        evidence_refs: Evidence references.
        problem_type: Optional problem type.
        available_personas: List of available personas.
        llm: LLM client instance.
        config: Routing configuration.

    Returns:
        RoutingPlan instance.
    """
    # Estimate evidence density
    evidence_density = estimate_evidence_density(claims, limitations, evidence_refs)

    # Build prompt
    system_prompt, user_prompt = build_routing_prompt(
        claims,
        assumptions,
        limitations,
        evidence_refs,
        problem_type,
        evidence_density,
        available_personas,
        config,
    )

    try:
        # Call LLM
        response = await llm.complete_json_async(system_prompt, user_prompt)

        # Parse response
        routing_plan = parse_routing_response(response, config)

        # Validate
        errors = validate_routing_plan(routing_plan, available_personas, config)
        if errors:
            # Try to fix common issues
            routing_plan = ensure_mandatory_audit_persona(routing_plan, config)

        return routing_plan

    except Exception as e:
        # Return fallback on failure
        return create_fallback_routing_plan(
            config,
            reason=f"Lead persona routing failed: {e}",
        )


def generate_routing_plan(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
    problem_type: str | None,
    available_personas: list[PersonaDefinition],
    llm: LLMClient,
    config: RoutingConfig,
) -> RoutingPlan:
    """Generate routing plan using lead persona (sync wrapper).

    Args:
        claims: Extracted claims.
        assumptions: Extracted assumptions.
        limitations: Extracted limitations.
        evidence_refs: Evidence references.
        problem_type: Optional problem type.
        available_personas: List of available personas.
        llm: LLM client instance.
        config: Routing configuration.

    Returns:
        RoutingPlan instance.
    """
    import asyncio
    return asyncio.run(
        generate_routing_plan_async(
            claims,
            assumptions,
            limitations,
            evidence_refs,
            problem_type,
            available_personas,
            llm,
            config,
        )
    )