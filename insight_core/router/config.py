"""Routing configuration loader.

Loads routing configuration from YAML/JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from insight_core.schemas import RoutingConfig, RoutingRules


# Default configuration
DEFAULT_ROUTING_CONFIG = RoutingConfig(
    enabled=True,
    lead_persona="bright_generalist",
    lead_persona_mutable=True,
    fallback_personas=["data_researcher", "operator"],
    mandatory_audit_personas=["data_researcher"],
    max_personas_by_evidence_density={
        "low": 3,
        "medium": 4,
        "high": 6,
    },
    routing_rules={
        "evaluation_gap": RoutingRules(
            preferred=["data_researcher", "operator", "researcher"],
            optional=["strategist"],
        ),
        "generalization_gap": RoutingRules(
            preferred=["researcher", "strategist", "data_researcher"],
            optional=[],
        ),
        "operational_risk": RoutingRules(
            preferred=["operator", "strategist", "researcher"],
            optional=[],
        ),
        "data_gap": RoutingRules(
            preferred=["data_researcher", "researcher"],
            optional=["operator"],
        ),
        "novelty_opportunity": RoutingRules(
            preferred=["curiosity_entertainer", "bright_generalist"],
            optional=["researcher"],
        ),
    },
)


def load_routing_config(
    config_path: str | Path | None = None,
) -> RoutingConfig:
    """Load routing configuration from file.

    Args:
        config_path: Path to configuration file (YAML or JSON).
                    If None, returns default configuration.

    Returns:
        RoutingConfig instance.
    """
    if config_path is None:
        return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)

    path = Path(config_path)
    if not path.exists():
        return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)

    # Read file content
    content = path.read_text(encoding="utf-8")

    # Parse based on extension
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            # Fall back to JSON parsing if YAML not available
            data = json.loads(content)
    else:
        data = json.loads(content)

    # Extract persona_routing section if present
    if "persona_routing" in data:
        data = data["persona_routing"]

    # Build RoutingConfig
    return _build_routing_config(data)


def _build_routing_config(data: dict[str, Any]) -> RoutingConfig:
    """Build RoutingConfig from parsed data.

    Args:
        data: Parsed configuration data.

    Returns:
        RoutingConfig instance.
    """
    # Build routing rules
    routing_rules: dict[str, RoutingRules] = {}
    for problem_type, rules in data.get("routing_rules", {}).items():
        routing_rules[problem_type] = RoutingRules(
            preferred=rules.get("preferred", []),
            optional=rules.get("optional", []),
        )

    return RoutingConfig(
        enabled=data.get("enabled", True),
        lead_persona=data.get("lead_persona", "bright_generalist"),
        lead_persona_mutable=data.get("lead_persona_mutable", True),
        fallback_personas=data.get("fallback_personas", ["data_researcher", "operator"]),
        mandatory_audit_personas=data.get("mandatory_audit_personas", ["data_researcher"]),
        max_personas_by_evidence_density=data.get(
            "max_personas_by_evidence_density",
            {"low": 3, "medium": 4, "high": 6},
        ),
        routing_rules=routing_rules,
    )


def get_default_routing_config() -> RoutingConfig:
    """Get the default routing configuration.

    Returns:
        Default RoutingConfig instance.
    """
    return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)