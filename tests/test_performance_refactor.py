import asyncio

import pytest

from insight_core.evaluator import evaluate_candidates_async
from insight_core.llm_client import LLMClient
from insight_core.schemas import (
    Decision,
    DerivationType,
    EpistemicMode,
    PersonaDefinition,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
)


class AsyncRetryStubLLM:
    def __init__(self):
        self.attempts = 0
        self.max_retries = 3
        self.retry_backoff_seconds = 0

    async def _request_completion_async(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        self.attempts += 1
        if self.attempts < 3:
            raise RuntimeError("transient")
        return '{"ok": true}'

    async def complete_json_async(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        response = await LLMClient._complete_with_retry_async(self, system_prompt, user_prompt, temperature)
        return LLMClient._parse_json_response(self, response)


class ConcurrencyProbeLLM:
    def __init__(self, delay: float = 0.01):
        self.delay = delay
        self.in_flight = 0
        self.max_in_flight = 0

    async def complete_json_async(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
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
        finally:
            self.in_flight -= 1


def _build_persona(persona_id: str) -> PersonaDefinition:
    return PersonaDefinition(
        persona_id=persona_id,
        name=persona_id,
        objective="Test objective",
        acceptance_rule="Test rule",
        weight=1.0,
    )


def _build_candidate(index: int) -> ProblemCandidateItem:
    return ProblemCandidateItem(
        id=f"pb_{index:03d}",
        statement=f"Candidate {index}",
        problem_type=ProblemType.EVALUATION_GAP,
        scope=ProblemScope.SYSTEM,
        epistemic_mode=EpistemicMode.HYPOTHESIS,
        derivation_type=DerivationType.INFERRED,
        confidence=0.7,
        decision=Decision.RESERVE,
        support_signals=["signal"],
        failure_signals=[],
        fatal_risks=[],
    )


@pytest.mark.asyncio
async def test_llm_client_async_retries_up_to_three_times():
    llm = AsyncRetryStubLLM()

    result = await llm.complete_json_async("system", "user")

    assert result == {"ok": True}
    assert llm.attempts == 3


@pytest.mark.asyncio
async def test_evaluate_candidates_shares_concurrency_across_candidates():
    personas = [_build_persona("data_researcher"), _build_persona("operator")]
    candidates = [_build_candidate(1), _build_candidate(2), _build_candidate(3)]
    llm = ConcurrencyProbeLLM()

    evaluated = await evaluate_candidates_async(candidates, personas, llm, max_concurrency=3)

    assert len(evaluated) == 3
    assert llm.max_in_flight == 3
    assert all(candidate.decision == Decision.ACCEPT for candidate in evaluated)
