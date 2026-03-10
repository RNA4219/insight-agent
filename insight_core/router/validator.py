"""Routing plan validator.

Validates routing plans for consistency and correctness.
"""

from __future__ import annotations

from insight_core.schemas import (
    PersonaDefinition,
    PersonaRole,
    RoutingConfig,
    RoutingPlan,
)


class RoutingValidationError(Exception):
    """Exception raised when routing validation fails."""

    pass


def validate_routing_plan(
    routing_plan: RoutingPlan,
    available_personas: list[PersonaDefinition],
    config: RoutingConfig,
) -> list[str]:
    """Validate a routing plan.

    Args:
        routing_plan: The routing plan to validate.
        available_personas: List of available persona definitions.
        config: Routing configuration.

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors: list[str] = []

    available_ids = {p.persona_id for p in available_personas}

    # Check that lead_persona exists
    if routing_plan.lead_persona not in available_ids:
        errors.append(
            f"lead_persona '{routing_plan.lead_persona}' not found in available personas"
        )

    # Check that all selected_personas exist
    for persona_id in routing_plan.selected_personas:
        if persona_id not in available_ids:
            errors.append(
                f"selected_persona '{persona_id}' not found in available personas"
            )

    # Check that all selected_personas have role assignments
    for persona_id in routing_plan.selected_personas:
        if persona_id not in routing_plan.role_assignments:
            errors.append(
                f"Missing role assignment for selected persona: {persona_id}"
            )

    # Check that role_assignments only contain valid roles
    valid_roles = {role.value for role in PersonaRole}
    for persona_id, role in routing_plan.role_assignments.items():
        if isinstance(role, str):
            if role not in valid_roles:
                errors.append(
                    f"Invalid role '{role}' for persona '{persona_id}'"
                )

    # Check that selected and skipped don't overlap
    selected_set = set(routing_plan.selected_personas)
    skipped_set = set(routing_plan.skipped_personas)
    overlap = selected_set & skipped_set
    if overlap:
        errors.append(
            f"selected_personas and skipped_personas overlap: {overlap}"
        )

    # Check that mandatory audit personas are included (unless disabled)
    if config.mandatory_audit_personas:
        mandatory_in_selected = any(
            p in selected_set for p in config.mandatory_audit_personas
        )
        if not mandatory_in_selected:
            # Check if any mandatory persona is available
            mandatory_available = any(
                p in available_ids for p in config.mandatory_audit_personas
            )
            if mandatory_available:
                errors.append(
                    f"No mandatory audit persona included. "
                    f"Expected one of: {config.mandatory_audit_personas}"
                )

    return errors


def validate_routing_plan_strict(
    routing_plan: RoutingPlan,
    available_personas: list[PersonaDefinition],
    config: RoutingConfig,
) -> None:
    """Validate a routing plan and raise exception if invalid.

    Args:
        routing_plan: The routing plan to validate.
        available_personas: List of available persona definitions.
        config: Routing configuration.

    Raises:
        RoutingValidationError: If validation fails.
    """
    errors = validate_routing_plan(routing_plan, available_personas, config)
    if errors:
        raise RoutingValidationError(
            f"Routing validation failed: {'; '.join(errors)}"
        )


def ensure_mandatory_audit_persona(
    routing_plan: RoutingPlan,
    config: RoutingConfig,
) -> RoutingPlan:
    """Ensure at least one mandatory audit persona is included.

    If no mandatory audit persona is in selected_personas, add the first
    available one from the mandatory list.

    Args:
        routing_plan: The routing plan to modify.
        config: Routing configuration.

    Returns:
        Modified routing plan with mandatory audit persona included.
    """
    selected_set = set(routing_plan.selected_personas)

    # Check if already included
    for persona_id in config.mandatory_audit_personas:
        if persona_id in selected_set:
            return routing_plan

    # Add first mandatory audit persona
    if config.mandatory_audit_personas:
        mandatory_id = config.mandatory_audit_personas[0]
        if mandatory_id not in selected_set:
            routing_plan.selected_personas.append(mandatory_id)
            routing_plan.role_assignments[mandatory_id] = PersonaRole.EVIDENCE_CHECKER
            if mandatory_id in routing_plan.skipped_personas:
                routing_plan.skipped_personas.remove(mandatory_id)
            routing_plan.routing_reason.append(
                f"Mandatory audit persona '{mandatory_id}' added by system"
            )

    return routing_plan