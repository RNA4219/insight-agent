"""Tests for Insight Agent."""

import json

import pytest

from insight_core.pipeline import run_pipeline
from insight_core.schemas import (
    ClaimItem,
    Constraints,
    Decision,
    DerivationType,
    EpistemicMode,
    InsightRequest,
    LimitationItem,
    Options,
    PersonaDefinition,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
    RunStatus,
    Source,
    UpdateRule,
)


class TestSchemas:
    """Tests for schema models."""

    def test_source_creation(self):
        source = Source(
            source_id="src_001",
            source_type="text",
            title="Test Document",
            content="This is a test document.",
        )
        assert source.source_id == "src_001"
        assert source.content == "This is a test document."

    def test_claim_item_creation(self):
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
        request = InsightRequest(
            mode="insight",
            request_id="req_001",
            sources=[Source(source_id="src_001", content="Test content")],
            constraints=Constraints(domain="machine_learning", max_problem_candidates=5),
        )
        assert request.mode == "insight"
        assert len(request.sources) == 1
        assert request.constraints.domain == "machine_learning"


class TestPersonaRegistry:
    def test_load_default_personas(self):
        from insight_core.persona_registry import load_default_personas

        data = load_default_personas()
        assert "personas" in data
        assert len(data["personas"]) == 8
        assert data["persona_catalog_version"] == "default_personas.v4"
        first = data["personas"][0]
        assert len(first["key_questions"]) >= 2
        assert len(first["red_flags"]) >= 1
        assert first["obsession"]
        celesta = next(p for p in data["personas"] if p["persona_id"] == "moon_gazer")
        detective = next(p for p in data["personas"] if p["persona_id"] == "detective")
        assert len(celesta["optional_notes"]) >= 5
        assert detective["blind_spot"]

    def test_validate_personas(self):
        from insight_core.persona_registry import validate_personas

        personas = [
            PersonaDefinition(
                persona_id="test_1",
                name="Test 1",
                objective="Test objective",
                key_questions=["What should we verify first?"],
                acceptance_rule="Test rule",
                weight=1.0,
            ),
            PersonaDefinition(
                persona_id="test_2",
                name="Test 2",
                objective="Test objective",
                red_flags=["Unsupported leap"],
                acceptance_rule="Test rule",
                weight=0.5,
            ),
        ]
        errors = validate_personas(personas)
        assert len(errors) == 0

    def test_validate_personas_duplicate_id(self):
        from insight_core.persona_registry import validate_personas

        personas = [
            PersonaDefinition(
                persona_id="duplicate",
                name="Test 1",
                objective="Test objective",
                evidence_requirements=["Need benchmark evidence"],
                acceptance_rule="Test rule",
            ),
            PersonaDefinition(
                persona_id="duplicate",
                name="Test 2",
                objective="Test objective",
                optional_notes=["Keep it anonymous"],
                synthesis_style="Summarize risks first",
                acceptance_rule="Test rule",
            ),
        ]
        errors = validate_personas(personas)
        assert len(errors) > 0
        assert "Duplicate" in errors[0]


class TestRequestNormalizer:
    def test_normalize_valid_request(self):
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(
            mode="insight",
            sources=[Source(source_id="src_001", content="This is test content for analysis.")],
        )

        normalized, _, _ = normalize_request(request)

        assert normalized.run_id.startswith("run_")
        assert normalized.request_id.startswith("req_")
        assert len(normalized.personas) == 8

    def test_normalize_invalid_mode(self):
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(mode="invalid", sources=[Source(source_id="src_001", content="Test")])

        with pytest.raises(ValueError, match="Invalid mode"):
            normalize_request(request)

    def test_normalize_empty_sources(self):
        from insight_core.request_normalizer import normalize_request

        request = InsightRequest(mode="insight", sources=[])

        with pytest.raises(ValueError, match="sources array is empty"):
            normalize_request(request)


class TestUnitizer:
    def test_unitize_simple_content(self):
        from insight_core.unitizer import unitize_source

        source = Source(
            source_id="src_001",
            content="This is paragraph one.\n\nThis is paragraph two.",
        )

        units = unitize_source(source)

        assert len(units) >= 1
        assert all(u.parent_source_id == "src_001" for u in units)

    def test_unitize_with_headers(self):
        from insight_core.unitizer import unitize_source

        source = Source(
            source_id="src_001",
            content="# Section 1\n\nContent for section 1.\n\n# Section 2\n\nContent for section 2.",
        )

        units = unitize_source(source)
        assert len(units) >= 2


class TestResponseBuilder:
    def test_build_response(self):
        from insight_core.response_builder import build_response
        from insight_core.schemas import NormalizedRequest, PersonaSource

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


class RetryStubLLM:
    def __init__(self):
        self.max_retries = 3
        self.retry_backoff_seconds = 0
        self.attempts = 0

    def _request_completion(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        self.attempts += 1
        if self.attempts < 3:
            raise RuntimeError("transient")
        return '{"ok": true}'

    def _complete_with_retry(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        from insight_core.llm_client import LLMClient

        return LLMClient._complete_with_retry(self, system_prompt, user_prompt, temperature)

    def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        from insight_core.llm_client import LLMClient

        response = self._complete_with_retry(system_prompt, user_prompt, temperature)
        return LLMClient._parse_json_response(self, response)


class PipelineStubLLM:
    def __init__(self, fail_discovery_once: bool = False):
        self.fail_discovery_once = fail_discovery_once
        self.discovery_attempts = 0

    async def complete_json_async(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        # Routing stage
        if "Lead Persona" in system_prompt or "routing_plan" in system_prompt:
            return {
                "lead_persona": "bright_generalist",
                "evidence_density": "medium",
                "selected_personas": ["data_researcher", "operator"],
                "skipped_personas": [],
                "role_assignments": {
                    "data_researcher": "evidence_checker",
                    "operator": "operational_risk_reviewer"
                },
                "routing_reason": ["Test routing"],
                "routing_confidence": 0.8
            }

        if "学術・技術資料の分析専門家" in system_prompt:
            return {
                "claims": [
                    {
                        "statement": "92% accuracy was observed",
                        "epistemic_mode": "observation",
                        "confidence": 0.9,
                        "quote": "92% accuracy",
                    }
                ],
                "assumptions": [],
                "limitations": [
                    {
                        "statement": "Only English was tested",
                        "limitation_type": "explicit",
                        "confidence": 0.8,
                        "quote": "only tested on English text",
                    }
                ],
            }

        if "課題発見の専門家" in system_prompt:
            self.discovery_attempts += 1
            if self.fail_discovery_once and self.discovery_attempts == 1:
                raise RuntimeError("discovery temporary failure")
            return {
                "problem_candidates": [
                    {
                        "statement": "Evaluation coverage is narrow",
                        "problem_type": "evaluation_gap",
                        "scope": "system",
                        "epistemic_mode": "hypothesis",
                        "confidence": 0.7,
                        "support_signals": ["English only"],
                        "failure_signals": [],
                        "fatal_risks": [],
                        "related_claim_ids": ["cl_unit_src_001_1_1"],
                        "related_assumption_ids": [],
                        "related_limitation_ids": ["lm_unit_src_001_1_2"],
                    }
                ]
            }

        if "という視点で課題候補を評価する専門家" in system_prompt:
            return {
                "axis_scores": {
                    "evidence_grounding": 0.8,
                    "novelty": 0.5,
                    "explanatory_power": 0.7,
                    "feasibility": 0.7,
                    "maintainability": 0.7,
                    "testability": 0.8,
                    "leverage": 0.6,
                    "robustness": 0.7,
                },
                "decision": "accept",
                "reason_summary": "sufficient evidence",
            }

        if "上位の洞察（insight）" in system_prompt:
            return {
                "insights": [
                    {
                        "statement": "Single-language evaluation creates a structural blind spot",
                        "confidence": 0.75,
                        "related_candidate_ids": ["pb_001"],
                    }
                ]
            }

        raise AssertionError(f"Unexpected prompt: {system_prompt[:80]}")


class TestAsyncRetryAndResume:
    def test_llm_client_retries_up_to_three_times(self):
        llm = RetryStubLLM()
        result = llm.complete_json("system", "user")

        assert result == {"ok": True}
        assert llm.attempts == 3

    def test_pipeline_resume_reuses_checkpoint_and_retries_failed_stage(self, tmp_path):
        checkpoint_path = tmp_path / "resume-checkpoint.json"
        request = InsightRequest(
            sources=[
                Source(
                    source_id="src_001",
                    content="The model achieved 92% accuracy on the benchmark dataset. However, it was only tested on English text.",
                )
            ],
            constraints=Constraints(domain="machine_learning", max_problem_candidates=3, max_insights=1),
            options=Options(checkpoint_path=str(checkpoint_path), resume=False, max_concurrency=4),
        )

        first_llm = PipelineStubLLM(fail_discovery_once=True)
        first_response = run_pipeline(request, llm=first_llm, verbose=False)

        assert first_response.run.status == RunStatus.FAILED
        assert any(f.stage == "discovery" for f in first_response.failures)
        assert checkpoint_path.exists()

        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint["completed_stages"] == ["extraction", "routing", "unitization"]

        resumed_request = request.model_copy(update={"options": Options(checkpoint_path=str(checkpoint_path), resume=True, max_concurrency=4)})
        second_llm = PipelineStubLLM(fail_discovery_once=False)
        resumed_response = run_pipeline(resumed_request, llm=second_llm, verbose=False)

        assert resumed_response.run.status == RunStatus.COMPLETED
        assert len(resumed_response.problem_candidates) == 1
        assert len(resumed_response.insights) == 1
        assert not any(f.stage == "discovery" for f in resumed_response.failures)

