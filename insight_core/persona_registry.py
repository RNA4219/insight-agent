"""Persona registry module.

Responsible for:
- Loading default persona catalog from JSON
- Validating request personas
- Building runtime persona registry
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from insight_core.schemas import (
    PersonaDefinition,
    PersonaRegistry,
    PersonaSource,
)

# Default personas file path
DEFAULT_PERSONAS_PATH = Path(__file__).parent.parent / "config" / "personas" / "default_personas.json"


def load_default_personas(path: Path | None = None) -> dict[str, Any]:
    """Load default personas from JSON file.

    Args:
        path: Optional custom path to personas file.

    Returns:
        Parsed JSON dict with persona_catalog_version and personas array.
    """
    file_path = path or DEFAULT_PERSONAS_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Default personas file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def validate_personas(personas: list[PersonaDefinition]) -> list[str]:
    """Validate persona definitions.

    Args:
        personas: List of persona definitions to validate.

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors = []

    # Check for duplicate persona_id
    seen_ids: set[str] = set()
    for persona in personas:
        if persona.persona_id in seen_ids:
            errors.append(f"Duplicate persona_id: {persona.persona_id}")
        seen_ids.add(persona.persona_id)

        # Validate weight
        if persona.weight < 0:
            errors.append(f"Invalid weight for {persona.persona_id}: {persona.weight}")

        # Validate required fields
        if not persona.objective:
            errors.append(f"Missing objective for persona: {persona.persona_id}")
        if not persona.acceptance_rule:
            errors.append(f"Missing acceptance_rule for persona: {persona.persona_id}")

    return errors


def build_persona_registry(
    request_personas: list[PersonaDefinition] | None,
    constraints_primary_persona: str | None = None,
    default_path: Path | None = None,
) -> PersonaRegistry:
    """Build runtime persona registry.

    Args:
        request_personas: Optional personas from request.
        constraints_primary_persona: Optional primary persona ID from constraints.
        default_path: Optional custom path to default personas file.

    Returns:
        PersonaRegistry with resolved personas and metadata.

    Raises:
        ValueError: If validation fails or primary_persona is invalid.
    """
    persona_source: PersonaSource
    catalog_version: str | None = None
    personas: list[PersonaDefinition]

    if request_personas is not None and len(request_personas) > 0:
        # Use request personas
        personas = request_personas
        persona_source = PersonaSource.REQUEST
        # Check if we need to merge with defaults (future feature)
        # For MVP-1, we use request personas as-is
    else:
        # Load default personas
        default_data = load_default_personas(default_path)
        catalog_version = default_data.get("persona_catalog_version")
        personas_data = default_data.get("personas", [])
        personas = [PersonaDefinition(**p) for p in personas_data]
        persona_source = PersonaSource.DEFAULT

    # Validate personas
    errors = validate_personas(personas)
    if errors:
        raise ValueError(f"Persona validation failed: {'; '.join(errors)}")

    # Validate primary_persona if specified
    persona_ids = {p.persona_id for p in personas}
    primary_persona_id = constraints_primary_persona
    if primary_persona_id and primary_persona_id not in persona_ids:
        raise ValueError(
            f"primary_persona '{primary_persona_id}' not found in persona registry. "
            f"Available: {sorted(persona_ids)}"
        )

    return PersonaRegistry(
        personas=personas,
        persona_source=persona_source,
        catalog_version=catalog_version,
        primary_persona_id=primary_persona_id,
    )


def get_default_persona_ids() -> list[str]:
    """Get list of default persona IDs.

    Returns:
        List of persona_id strings from default catalog.
    """
    default_data = load_default_personas()
    return [p["persona_id"] for p in default_data.get("personas", [])]