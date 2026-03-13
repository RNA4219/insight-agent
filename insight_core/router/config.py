"""Routing configuration loader.

Loads routing configuration from YAML/JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from insight_core.schemas import RoutingConfig, RoutingRules


DEFAULT_ROUTING_CONFIG = RoutingConfig(
    enabled=True,
    lead_persona='bright_generalist',
    lead_persona_mutable=True,
    fallback_personas=['data_researcher', 'detective', 'operator'],
    mandatory_audit_personas=['data_researcher', 'detective'],
    max_personas_by_evidence_density={
        'low': 3,
        'medium': 4,
        'high': 6,
    },
    routing_rules={
        'evaluation_gap': RoutingRules(
            preferred=['data_researcher', 'detective', 'operator'],
            optional=['researcher'],
        ),
        'assumption_weakness': RoutingRules(
            preferred=['detective', 'researcher', 'data_researcher'],
            optional=['strategist'],
        ),
        'contradiction': RoutingRules(
            preferred=['detective', 'data_researcher', 'researcher'],
            optional=['operator'],
        ),
        'omitted_factor': RoutingRules(
            preferred=['detective', 'strategist', 'bright_generalist'],
            optional=['operator'],
        ),
        'generalization_gap': RoutingRules(
            preferred=['researcher', 'strategist', 'detective'],
            optional=['data_researcher'],
        ),
        'operational_risk': RoutingRules(
            preferred=['operator', 'detective', 'strategist'],
            optional=['researcher'],
        ),
        'scalability_limit': RoutingRules(
            preferred=['operator', 'strategist', 'detective'],
            optional=['researcher'],
        ),
        'data_gap': RoutingRules(
            preferred=['data_researcher', 'researcher', 'detective'],
            optional=['operator'],
        ),
        'novelty_opportunity': RoutingRules(
            preferred=['curiosity_entertainer', 'bright_generalist'],
            optional=['researcher'],
        ),
    },
)


def load_routing_config(
    config_path: str | Path | None = None,
) -> RoutingConfig:
    """Load routing configuration from file."""
    if config_path is None:
        return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)

    path = Path(config_path)
    if not path.exists():
        return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)

    content = path.read_text(encoding='utf-8')

    if path.suffix in ('.yaml', '.yml'):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            data = json.loads(content)
    else:
        data = json.loads(content)

    if 'persona_routing' in data:
        data = data['persona_routing']

    return _build_routing_config(data)


def _build_routing_config(data: dict[str, Any]) -> RoutingConfig:
    """Build RoutingConfig from parsed data."""
    routing_rules: dict[str, RoutingRules] = {}
    for problem_type, rules in data.get('routing_rules', {}).items():
        routing_rules[problem_type] = RoutingRules(
            preferred=rules.get('preferred', []),
            optional=rules.get('optional', []),
        )

    return RoutingConfig(
        enabled=data.get('enabled', True),
        lead_persona=data.get('lead_persona', 'bright_generalist'),
        lead_persona_mutable=data.get('lead_persona_mutable', True),
        fallback_personas=data.get('fallback_personas', ['data_researcher', 'detective', 'operator']),
        mandatory_audit_personas=data.get('mandatory_audit_personas', ['data_researcher', 'detective']),
        max_personas_by_evidence_density=data.get(
            'max_personas_by_evidence_density',
            {'low': 3, 'medium': 4, 'high': 6},
        ),
        routing_rules=routing_rules,
    )


def get_default_routing_config() -> RoutingConfig:
    """Get the default routing configuration."""
    return DEFAULT_ROUTING_CONFIG.model_copy(deep=True)
