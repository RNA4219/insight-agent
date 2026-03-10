"""Fallback routing plan generator.

Creates fallback routing plans when normal routing fails.
"""

from __future__ import annotations

from insight_core.schemas import (
    EvidenceDensity,
    PersonaRole,
    RoutingConfig,
    RoutingPlan,
)


def create_fallback_routing_plan(
    config: RoutingConfig | None = None,
    reason: str = "Routing plan generation failed",
) -> RoutingPlan:
    """Create a fallback routing plan.

    Args:
        config: Routing configuration (uses defaults if None).
        reason: Reason for using fallback.

    Returns:
        Fallback RoutingPlan instance.
    """
    if config is None:
        config = RoutingConfig()

    selected = list(config.fallback_personas)

    # Ensure at least one mandatory audit persona
    for persona_id in config.mandatory_audit_personas:
        if persona_id not in selected:
            selected.append(persona_id)

    # Build role assignments
    role_assignments: dict[str, PersonaRole] = {}
    for persona_id in selected:
        if persona_id == "data_researcher":
            role_assignments[persona_id] = PersonaRole.EVIDENCE_CHECKER
        elif persona_id == "operator":
            role_assignments[persona_id] = PersonaRole.OPERATIONAL_RISK_REVIEWER
        elif persona_id == "researcher":
            role_assignments[persona_id] = PersonaRole.HYPOTHESIS_REFINER
        else:
            role_assignments[persona_id] = PersonaRole.EVIDENCE_CHECKER

    return RoutingPlan(
        lead_persona=config.lead_persona,
        evidence_density=EvidenceDensity.LOW,  # Conservative default
        selected_personas=selected,
        skipped_personas=[],
        role_assignments=role_assignments,
        routing_reason=[
            reason,
            "Using fallback routing configuration",
        ],
        skip_reasons={},
        routing_confidence=0.5,  # Lower confidence for fallback
    )


def create_minimal_routing_plan() -> RoutingPlan:
    """Create a minimal fallback routing plan.

    Uses the absolute minimum: data_researcher and operator.

    Returns:
        Minimal RoutingPlan instance.
    """
    return RoutingPlan(
        lead_persona="bright_generalist",
        evidence_density=EvidenceDensity.LOW,
        selected_personas=["data_researcher", "operator"],
        skipped_personas=[],
        role_assignments={
            "data_researcher": PersonaRole.EVIDENCE_CHECKER,
            "operator": PersonaRole.OPERATIONAL_RISK_REVIEWER,
        },
        routing_reason=[
            "Minimal fallback routing applied",
            "data_researcher for evidence checking",
            "operator for operational risk review",
        ],
        skip_reasons={},
        routing_confidence=0.4,
    )


def create_all_personas_routing_plan(
    available_persona_ids: list[str],
    lead_persona: str = "bright_generalist",
) -> RoutingPlan:
    """Create a routing plan that includes all available personas.

    Used when routing is disabled but we still need a routing_plan structure.

    Args:
        available_persona_ids: List of all available persona IDs.
        lead_persona: Lead persona ID.

    Returns:
        RoutingPlan that includes all personas.
    """
    # Assign roles based on persona type
    role_assignments: dict[str, PersonaRole] = {}
    for persona_id in available_persona_ids:
        if "data_researcher" in persona_id:
            role_assignments[persona_id] = PersonaRole.EVIDENCE_CHECKER
        elif "operator" in persona_id:
            role_assignments[persona_id] = PersonaRole.OPERATIONAL_RISK_REVIEWER
        elif "researcher" in persona_id and "data" not in persona_id:
            role_assignments[persona_id] = PersonaRole.HYPOTHESIS_REFINER
        elif "strategist" in persona_id:
            role_assignments[persona_id] = PersonaRole.STRUCTURAL_ABSTRACTION
        elif "curiosity" in persona_id or "entertainer" in persona_id:
            role_assignments[persona_id] = PersonaRole.NOVELTY_PROBE
        else:
            role_assignments[persona_id] = PersonaRole.EVIDENCE_CHECKER

    return RoutingPlan(
        lead_persona=lead_persona,
        evidence_density=EvidenceDensity.MEDIUM,
        selected_personas=list(available_persona_ids),
        skipped_personas=[],
        role_assignments=role_assignments,
        routing_reason=[
            "All personas selected (routing disabled)",
        ],
        skip_reasons={},
        routing_confidence=0.6,
    )