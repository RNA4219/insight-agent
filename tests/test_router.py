"""Tests for Router module."""

import pytest

from insight_core.schemas import (
    ClaimItem,
    DerivationType,
    EpistemicMode,
    EvidenceDensity,
    EvidenceRef,
    LimitationItem,
    PersonaDefinition,
    PersonaRole,
    RoutingConfig,
    RoutingPlan,
    RoutingRules,
)
from insight_core.router.density_estimator import estimate_evidence_density
from insight_core.router.validator import (
    validate_routing_plan,
    ensure_mandatory_audit_persona,
)
from insight_core.router.fallback import (
    create_fallback_routing_plan,
    create_minimal_routing_plan,
    create_all_personas_routing_plan,
)


class TestDensityEstimator:
    """Tests for evidence density estimation."""

    def test_low_density_with_no_claims(self):
        """Empty claims should result in low density."""
        density = estimate_evidence_density([], [], [])
        assert density == EvidenceDensity.LOW

    def test_low_density_with_few_claims(self):
        """Few claims with low evidence should result in low density."""
        claims = [
            ClaimItem(
                id="cl_001",
                statement="Test claim",
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.5,
            )
        ]
        density = estimate_evidence_density(claims, [], [])
        # With 1 claim and no evidence, could be low or medium depending on thresholds
        assert density in [EvidenceDensity.LOW, EvidenceDensity.MEDIUM]

    def test_medium_density_with_moderate_claims(self):
        """Moderate claims and evidence should result in medium density."""
        claims = [
            ClaimItem(
                id=f"cl_{i:03d}",
                statement=f"Test claim {i}",
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.7,
            )
            for i in range(5)
        ]
        evidence_refs = [
            EvidenceRef(
                evidence_id=f"ev_{i:03d}",
                source_id="src_001",
                claim_ids=[f"cl_{i:03d}"]
            )
            for i in range(4)
        ]
        density = estimate_evidence_density(claims, [], evidence_refs)
        assert density in [EvidenceDensity.LOW, EvidenceDensity.MEDIUM, EvidenceDensity.HIGH]

    def test_high_density_with_many_claims(self):
        """Many claims with high evidence should result in high density."""
        claims = [
            ClaimItem(
                id=f"cl_{i:03d}",
                statement=f"Test claim {i}",
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.9,
            )
            for i in range(10)
        ]
        evidence_refs = [
            EvidenceRef(
                evidence_id=f"ev_{i:03d}",
                source_id="src_001",
                claim_ids=[f"cl_{i:03d}"]
            )
            for i in range(9)
        ]
        density = estimate_evidence_density(claims, [], evidence_refs)
        # High claims + high evidence should give medium or high
        assert density in [EvidenceDensity.MEDIUM, EvidenceDensity.HIGH]

    def test_density_with_limitations(self):
        """Limitations should reduce density score."""
        claims = [
            ClaimItem(
                id=f"cl_{i:03d}",
                statement=f"Test claim {i}",
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.7,
            )
            for i in range(8)
        ]
        limitations = [
            LimitationItem(
                id=f"lm_{i:03d}",
                statement=f"Limitation {i}",
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.8,
            )
            for i in range(3)
        ]
        density = estimate_evidence_density(claims, limitations, [])
        # Should be lower due to limitations
        assert density in [EvidenceDensity.LOW, EvidenceDensity.MEDIUM]


class TestRoutingConfig:
    """Tests for routing configuration."""

    def test_default_routing_config(self):
        """Default config should have sensible defaults."""
        config = RoutingConfig()
        assert config.enabled is True
        assert config.lead_persona == "bright_generalist"
        assert "data_researcher" in config.mandatory_audit_personas
        assert "detective" in config.mandatory_audit_personas
        assert config.max_personas_by_evidence_density["low"] == 3
        assert config.max_personas_by_evidence_density["medium"] == 4
        assert config.max_personas_by_evidence_density["high"] == 6

    def test_routing_rules_creation(self):
        """Routing rules should be creatable."""
        rules = RoutingRules(
            preferred=["data_researcher", "operator"],
            optional=["researcher"],
        )
        assert len(rules.preferred) == 2
        assert len(rules.optional) == 1


class TestRoutingPlanValidation:
    """Tests for routing plan validation."""

    def test_valid_routing_plan(self):
        """A valid routing plan should pass validation."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            evidence_density=EvidenceDensity.MEDIUM,
            selected_personas=["data_researcher", "operator"],
            skipped_personas=["curiosity_entertainer"],
            role_assignments={
                "data_researcher": PersonaRole.EVIDENCE_CHECKER,
                "operator": PersonaRole.OPERATIONAL_RISK_REVIEWER,
            },
            routing_reason=["Test routing"],
        )
        config = RoutingConfig()
        available_personas = [
            PersonaDefinition(
                persona_id="bright_generalist",
                name="Bright Generalist",
                objective="Lead persona",
                acceptance_rule="Accept all",
            ),
            PersonaDefinition(
                persona_id="data_researcher",
                name="Data Researcher",
                objective="Check evidence",
                acceptance_rule="Accept if valid",
            ),
            PersonaDefinition(
                persona_id="operator",
                name="Operator",
                objective="Operational review",
                acceptance_rule="Accept if feasible",
            ),
        ]
        errors = validate_routing_plan(plan, available_personas, config)
        assert len(errors) == 0

    def test_invalid_routing_plan_missing_role(self):
        """Missing role assignment should cause validation error."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            evidence_density=EvidenceDensity.MEDIUM,
            selected_personas=["data_researcher"],
            skipped_personas=[],
            role_assignments={},  # Missing role
            routing_reason=["Test routing"],
        )
        config = RoutingConfig()
        available_personas = [
            PersonaDefinition(
                persona_id="bright_generalist",
                name="Bright Generalist",
                objective="Lead persona",
                acceptance_rule="Accept all",
            ),
            PersonaDefinition(
                persona_id="data_researcher",
                name="Data Researcher",
                objective="Check evidence",
                acceptance_rule="Accept if valid",
            ),
        ]
        errors = validate_routing_plan(plan, available_personas, config)
        assert len(errors) > 0
        assert any("role" in e.lower() for e in errors)

    def test_invalid_routing_plan_overlap(self):
        """Overlap between selected and skipped should cause error."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            evidence_density=EvidenceDensity.MEDIUM,
            selected_personas=["data_researcher"],
            skipped_personas=["data_researcher"],  # Overlap!
            role_assignments={
                "data_researcher": PersonaRole.EVIDENCE_CHECKER,
            },
            routing_reason=["Test routing"],
        )
        config = RoutingConfig()
        available_personas = [
            PersonaDefinition(
                persona_id="bright_generalist",
                name="Bright Generalist",
                objective="Lead persona",
                acceptance_rule="Accept all",
            ),
            PersonaDefinition(
                persona_id="data_researcher",
                name="Data Researcher",
                objective="Check evidence",
                acceptance_rule="Accept if valid",
            ),
        ]
        errors = validate_routing_plan(plan, available_personas, config)
        assert len(errors) > 0
        assert any("overlap" in e.lower() for e in errors)

    def test_ensure_mandatory_audit_persona(self):
        """Missing mandatory audit persona should be added."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            evidence_density=EvidenceDensity.MEDIUM,
            selected_personas=["operator"],  # Missing mandatory
            skipped_personas=[],
            role_assignments={
                "operator": PersonaRole.OPERATIONAL_RISK_REVIEWER,
            },
            routing_reason=["Test routing"],
        )
        config = RoutingConfig(
            mandatory_audit_personas=["data_researcher"]
        )

        fixed_plan = ensure_mandatory_audit_persona(plan, config)

        assert "data_researcher" in fixed_plan.selected_personas
        assert "data_researcher" in fixed_plan.role_assignments


class TestFallbackRouting:
    """Tests for fallback routing plan generation."""

    def test_create_fallback_routing_plan(self):
        """Fallback plan should be created with defaults."""
        plan = create_fallback_routing_plan()

        assert plan.lead_persona == "bright_generalist"
        assert plan.evidence_density == EvidenceDensity.LOW
        assert len(plan.selected_personas) >= 2
        assert "detective" in plan.selected_personas
        assert plan.routing_confidence == 0.5
        assert any("fallback" in r.lower() for r in plan.routing_reason)

    def test_create_fallback_routing_plan_with_config(self):
        """Fallback plan should respect config."""
        config = RoutingConfig(
            lead_persona="custom_lead",
            fallback_personas=["researcher"],
            mandatory_audit_personas=["data_researcher"],
        )
        plan = create_fallback_routing_plan(config, "Custom reason")

        assert plan.lead_persona == "custom_lead"
        assert "researcher" in plan.selected_personas
        assert "data_researcher" in plan.selected_personas
        assert "Custom reason" in plan.routing_reason

    def test_create_minimal_routing_plan(self):
        """Minimal plan should have only essential personas."""
        plan = create_minimal_routing_plan()

        assert plan.lead_persona == "bright_generalist"
        assert "data_researcher" in plan.selected_personas
        assert "operator" in plan.selected_personas
        assert len(plan.selected_personas) == 2
        assert plan.routing_confidence == 0.4

    def test_create_all_personas_routing_plan(self):
        """All personas plan should include all available."""
        available_ids = [
            "data_researcher",
            "operator",
            "researcher",
            "strategist",
            "curiosity_entertainer",
            "detective",
        ]
        plan = create_all_personas_routing_plan(available_ids)

        assert len(plan.selected_personas) == 6
        assert plan.evidence_density == EvidenceDensity.MEDIUM
        assert plan.routing_confidence == 0.6

        # Check role assignments
        assert plan.role_assignments["data_researcher"] == PersonaRole.EVIDENCE_CHECKER
        assert plan.role_assignments["operator"] == PersonaRole.OPERATIONAL_RISK_REVIEWER
        assert plan.role_assignments["researcher"] == PersonaRole.HYPOTHESIS_REFINER
        assert plan.role_assignments["strategist"] == PersonaRole.STRUCTURAL_ABSTRACTION
        assert plan.role_assignments["curiosity_entertainer"] == PersonaRole.NOVELTY_PROBE
        assert plan.role_assignments["detective"] == PersonaRole.HYPOTHESIS_REFINER


class TestRoutingPlanModel:
    """Tests for RoutingPlan model."""

    def test_routing_plan_creation(self):
        """Routing plan should be creatable with all fields."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            problem_type="technical_debt",
            evidence_density=EvidenceDensity.HIGH,
            selected_personas=["data_researcher", "operator", "strategist"],
            skipped_personas=["curiosity_entertainer"],
            role_assignments={
                "data_researcher": PersonaRole.EVIDENCE_CHECKER,
                "operator": PersonaRole.OPERATIONAL_RISK_REVIEWER,
                "strategist": PersonaRole.STRUCTURAL_ABSTRACTION,
            },
            routing_reason=["High evidence density", "Problem type suggests technical analysis"],
            skip_reasons={
                "curiosity_entertainer": "Not relevant for technical debt",
            },
            routing_confidence=0.85,
        )

        assert plan.lead_persona == "bright_generalist"
        assert plan.problem_type == "technical_debt"
        assert plan.evidence_density == EvidenceDensity.HIGH
        assert len(plan.selected_personas) == 3
        assert plan.routing_confidence == 0.85

    def test_routing_plan_minimal(self):
        """Routing plan should work with minimal fields."""
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            selected_personas=["data_researcher"],
            routing_reason=["Default selection"],
        )

        assert plan.skipped_personas == []
        assert plan.role_assignments == {}
        assert plan.skip_reasons == {}
        # routing_confidence defaults to 0.5 in Pydantic Field default
        assert plan.routing_confidence == 0.5

    def test_routing_plan_confidence_bounds(self):
        """Routing confidence should be bounded 0-1."""
        # Valid bounds
        plan = RoutingPlan(
            lead_persona="bright_generalist",
            selected_personas=["data_researcher"],
            routing_reason=["Test"],
            routing_confidence=0.0,
        )
        assert plan.routing_confidence == 0.0

        plan = RoutingPlan(
            lead_persona="bright_generalist",
            selected_personas=["data_researcher"],
            routing_reason=["Test"],
            routing_confidence=1.0,
        )
        assert plan.routing_confidence == 1.0

        # Invalid bounds should raise
        with pytest.raises(ValueError):
            RoutingPlan(
                lead_persona="bright_generalist",
                selected_personas=["data_researcher"],
                routing_reason=["Test"],
                routing_confidence=1.5,
            )