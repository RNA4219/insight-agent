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


def _default_role_for_persona(persona_id: str) -> PersonaRole:
    if persona_id == 'data_researcher':
        return PersonaRole.EVIDENCE_CHECKER
    if persona_id == 'operator':
        return PersonaRole.OPERATIONAL_RISK_REVIEWER
    if persona_id in {'researcher', 'detective'}:
        return PersonaRole.HYPOTHESIS_REFINER
    if persona_id == 'strategist':
        return PersonaRole.STRUCTURAL_ABSTRACTION
    if 'curiosity' in persona_id or 'entertainer' in persona_id:
        return PersonaRole.NOVELTY_PROBE
    return PersonaRole.EVIDENCE_CHECKER


def create_fallback_routing_plan(
    config: RoutingConfig | None = None,
    reason: str = 'Routing plan generation failed',
) -> RoutingPlan:
    """Create a fallback routing plan."""
    if config is None:
        config = RoutingConfig()

    selected = list(config.fallback_personas)

    for persona_id in config.mandatory_audit_personas:
        if persona_id not in selected:
            selected.append(persona_id)

    role_assignments = {persona_id: _default_role_for_persona(persona_id) for persona_id in selected}

    return RoutingPlan(
        lead_persona=config.lead_persona,
        evidence_density=EvidenceDensity.LOW,
        selected_personas=selected,
        skipped_personas=[],
        role_assignments=role_assignments,
        routing_reason=[
            reason,
            'Using fallback routing configuration',
        ],
        skip_reasons={},
        routing_confidence=0.5,
    )


def create_minimal_routing_plan() -> RoutingPlan:
    """Create a minimal fallback routing plan."""
    return RoutingPlan(
        lead_persona='bright_generalist',
        evidence_density=EvidenceDensity.LOW,
        selected_personas=['data_researcher', 'operator'],
        skipped_personas=[],
        role_assignments={
            'data_researcher': PersonaRole.EVIDENCE_CHECKER,
            'operator': PersonaRole.OPERATIONAL_RISK_REVIEWER,
        },
        routing_reason=[
            'Minimal fallback routing applied',
            'data_researcher for evidence checking',
            'operator for operational risk review',
        ],
        skip_reasons={},
        routing_confidence=0.4,
    )


def create_all_personas_routing_plan(
    available_persona_ids: list[str],
    lead_persona: str = 'bright_generalist',
) -> RoutingPlan:
    """Create a routing plan that includes all available personas."""
    role_assignments = {
        persona_id: _default_role_for_persona(persona_id)
        for persona_id in available_persona_ids
    }

    return RoutingPlan(
        lead_persona=lead_persona,
        evidence_density=EvidenceDensity.MEDIUM,
        selected_personas=list(available_persona_ids),
        skipped_personas=[],
        role_assignments=role_assignments,
        routing_reason=[
            'All personas selected (routing disabled)',
        ],
        skip_reasons={},
        routing_confidence=0.6,
    )
