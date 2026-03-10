"""Tests for Insight Agent."""

import pytest

from insight_core.schemas import (
    ClaimItem,
    Constraints,
    Decision,
    DerivationType,
    EpistemicMode,
    InsightRequest,
    InsightResponse,
    LimitationItem,
    PersonaDefinition,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
    RunInfo,
    RunStatus,
    Source,
    UpdateRule,
)


class TestSchemas:
    """Tests for schema models."""

    def test_source_creation(self):
        """Test creating a Source."""
        source = Source(
            source_id="src_001",
            source_type="text",
            title="Test Document",
            content="This is a test document.",
        )
        assert source.source_id == "src_001"
        assert source.content == "This is a test document."

    def test_claim_item_creation(self):
        """Test creating a ClaimItem."""
        claim = ClaimItem(
            id="cl_001",
            statement="Test claim",
            epistemic_mode=EpistemicMode.OBSERVATION,
            derivation_type=DerivationType.DIRECT,
            confidence=0.9,
            evidence_refs=["ev_001"],
        )
        assert claim.id == "cl_001"
        assert claim.confidence == 0.9
        assert claim.update_rule == UpdateRule.RETAIN

    def test_problem_candidate_creation(self):
        """Test creating a ProblemCandidateItem."""
        candidate = ProblemCandidateItem(
            id="pb_001",
            statement="Test problem",
            problem_type=ProblemType.EVALUATION_GAP,
            scope=ProblemScope.SYSTEM,
            epistemic_mode=EpistemicMode.HYPOTHESIS,
            derivation_type=DerivationType.INFERRED,
            confidence=0.7,
            decision=Decision.ACCEPT,
        )
        assert candidate.problem_id == "pb_001"
        assert candidate.decision == Decision.ACCEPT

    def test_insight_request_creation(self):
        """Test creating an InsightRequest."""
        request = InsightRequest(
            mode="insight",
            request_id="req_001",
            sources=[
                Source(
                    source_id="src_001",
                    content="Test content",
                )
            ],
            constraints=Constraints(
                domain="machine_learning",
                max_problem_candidates=5,
            ),
        )
        assert request.mode == "insight"
        assert len(request.sources) == 1
        assert request.constraints.domain == "machine_learning"


class TestPersonaRegistry:
    """Tests for persona registry."""

    def test_load_default_personas(self):
        """Test loading default personas."""
        from insight_core.persona_registry import load_default_personas

        data = load_default_personas()
        assert "personas" in data
        assert len(data["personas"]) == 6
        assert data["persona_catalog_version"] == "default_personas.v1"

    def test_validate_personas(self):
        """Test persona validation."""
        from insight_core.persona_registry import validate_personas

        # Valid personas
        personas = [
            PersonaDefinition(
                persona_id="test_1",
                name="Test 1",
                objective="Test objective",
                acceptance_rule="Test rule",
                weight=1.0,
            ),
            PersonaDefinition(
                persona_id="test_2",
                name="Test 2",
                objective="Test objective",
                acceptance_rule="Test rule",
                weight=0.5,
            ),
        ]
        errors = validate_personas(personas)
        assert len(errors) == 0

    def test_validate_personas_duplicate_id(self):
        """Test that duplicate persona IDs are caught."""
        from insight_core.persona_registry import validate_personas

        personas = [
            PersonaDefinition(
                persona_id="duplicate",
                name="Test 1",
                objective="Test objective",
                acceptance_rule="Test rule",
            ),
            PersonaDefinition(
                persona_id="duplicate",
                name="Test 2",
                objective="Test objective",
                acceptance_rule="Test rule",
            ),
        ]
        errors = validate_personas(personas)
        assert len(errors) > 0
        assert "Duplicate" in errors[0]


class TestRequestNormalizer:
    """Tests for request normalization."""

    def test_normalize_valid_request(self):
        """Test normalizing a valid request."""
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(
            mode="insight",
            sources=[
                Source(
                    source_id="src_001",
                    content="This is test content for analysis.",
                )
            ],
        )

        normalized, registry, warnings = normalize_request(request)

        assert normalized.run_id.startswith("run_")
        assert normalized.request_id.startswith("req_")
        assert len(normalized.personas) == 6  # Default personas

    def test_normalize_invalid_mode(self):
        """Test that invalid mode raises error."""
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(
            mode="invalid",
            sources=[Source(source_id="src_001", content="Test")],
        )

        with pytest.raises(ValueError, match="Invalid mode"):
            normalize_request(request)

    def test_normalize_empty_sources(self):
        """Test that empty sources raises error."""
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(
            mode="insight",
            sources=[],
        )

        with pytest.raises(ValueError, match="sources array is empty"):
            normalize_request(request)


class TestUnitizer:
    """Tests for source unitization."""

    def test_unitize_simple_content(self):
        """Test unitizing simple content."""
        from insight_core.unitizer import unitize_source

        source = Source(
            source_id="src_001",
            content="This is paragraph one.\n\nThis is paragraph two.",
        )

        units = unitize_source(source)

        assert len(units) >= 1
        assert all(u.parent_source_id == "src_001" for u in units)

    def test_unitize_with_headers(self):
        """Test unitizing content with headers."""
        from insight_core.unitizer import unitize_source

        source = Source(
            source_id="src_001",
            content="# Section 1\n\nContent for section 1.\n\n# Section 2\n\nContent for section 2.",
        )

        units = unitize_source(source)

        assert len(units) >= 2
        # Headers should create separate units


class TestResponseBuilder:
    """Tests for response building."""

    def test_build_response(self):
        """Test building a response."""
        from insight_core.response_builder import build_response
        from insight_core.schemas import PersonaSource

        from insight_core.schemas import NormalizedRequest

        normalized = NormalizedRequest(
            run_id="run_001",
            request_id="req_001",
            sources=[Source(source_id="src_001", content="Test")],
            constraints=Constraints(),
            personas=[],
            persona_source=PersonaSource.DEFAULT,
            persona_catalog_version="test.v1",
            context={},
            options={},
        )

        response = build_response(
            normalized_request=normalized,
            claims=[
                ClaimItem(
                    id="cl_001",
                    statement="Test claim",
                    epistemic_mode=EpistemicMode.OBSERVATION,
                    derivation_type=DerivationType.DIRECT,
                    confidence=0.9,
                )
            ],
            assumptions=[],
            limitations=[],
            problem_candidates=[],
            insights=[],
            open_questions=[],
            evidence_refs=[],
            failures=[],
            confidence=0.9,
            status=RunStatus.COMPLETED,
        )

        assert response.run.run_id == "run_001"
        assert response.run.status == RunStatus.COMPLETED
        assert len(response.claims) == 1