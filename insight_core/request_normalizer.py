"""Request normalizer module.

Responsible for:
- Validating required fields in request
- Generating request_id / run_id if missing
- Normalizing source types
- Setting default values for options / constraints
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from insight_core.persona_registry import build_persona_registry
from insight_core.schemas import (
    Constraints,
    Context,
    InsightRequest,
    NormalizedRequest,
    Options,
    PersonaRegistry,
    PersonaSource,
    Source,
)


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID.

    Args:
        prefix: Optional prefix for the ID.

    Returns:
        Unique ID string.
    """
    unique = uuid.uuid4().hex[:12]
    return f"{prefix}_{unique}" if prefix else unique


def validate_sources(sources: list[Source]) -> list[str]:
    """Validate sources list.

    Args:
        sources: List of sources to validate.

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors = []

    if not sources:
        errors.append("sources array is empty")
        return errors

    for i, source in enumerate(sources):
        if not source.source_id:
            errors.append(f"source[{i}]: missing source_id")

        if not source.content or not source.content.strip():
            errors.append(f"source[{i}] ({source.source_id}): content is empty")

    return errors


def normalize_request(
    request: InsightRequest,
) -> tuple[NormalizedRequest, PersonaRegistry, list[str]]:
    """Normalize and validate an InsightRequest.

    Args:
        request: The insight request to normalize.

    Returns:
        Tuple of (NormalizedRequest, PersonaRegistry, validation_warnings).

    Raises:
        ValueError: If request is invalid and cannot be processed.
    """
    warnings: list[str] = []

    # Validate mode
    if request.mode != "insight":
        raise ValueError(f"Invalid mode: {request.mode}. Expected 'insight'")

    # Validate sources
    source_errors = validate_sources(request.sources)
    if source_errors:
        raise ValueError(f"Source validation failed: {'; '.join(source_errors)}")

    # Generate IDs if missing
    request_id = request.request_id or generate_id("req")
    run_id = generate_id("run")

    # Set defaults for constraints
    constraints = request.constraints or Constraints()
    if constraints.max_problem_candidates <= 0:
        warnings.append(
            f"max_problem_candidates={constraints.max_problem_candidates} "
            "adjusted to default 5"
        )
        constraints.max_problem_candidates = 5
    if constraints.max_insights <= 0:
        warnings.append(f"max_insights={constraints.max_insights} adjusted to default 3")
        constraints.max_insights = 3

    # Build persona registry
    try:
        persona_registry = build_persona_registry(
            request_personas=request.personas,
            constraints_primary_persona=constraints.primary_persona,
        )
    except ValueError as e:
        raise ValueError(f"Persona registry error: {e}") from e

    # Determine persona catalog version
    persona_source = persona_registry.persona_source
    if persona_source == PersonaSource.REQUEST:
        persona_catalog_version = "request_inline"
    else:
        persona_catalog_version = persona_registry.catalog_version

    # Set defaults for context and options
    context = request.context or Context()
    options = request.options or Options()

    normalized = NormalizedRequest(
        run_id=run_id,
        request_id=request_id,
        sources=request.sources,
        constraints=constraints,
        personas=persona_registry.personas,
        persona_source=persona_source,
        persona_catalog_version=persona_catalog_version,
        context=context,
        options=options,
    )

    return normalized, persona_registry, warnings