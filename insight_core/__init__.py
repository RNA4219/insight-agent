"""Insight Agent - A problem discovery core agent.

This package provides tools for analyzing documents and extracting
structured insights including claims, assumptions, limitations,
and problem candidates.
"""

from insight_core.pipeline import (
    run_insight,
    run_insight_result,
    run_pipeline,
    run_pipeline_async,
    run_pipeline_result,
    run_pipeline_result_async,
)
from insight_core.result_formatter import build_agent_result
from insight_core.runner import run, run_async
from insight_core.runtime_config import RuntimeConfig, load_runtime_config
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    Constraints,
    Decision,
    DerivationType,
    EpistemicMode,
    EvidenceRef,
    FailureItem,
    InsightItem,
    InsightRequest,
    InsightResponse,
    JapaneseSummary,
    LimitationItem,
    NormalizedRequest,
    OpenQuestionItem,
    PersonaDefinition,
    PersonaScore,
    ProblemCandidateItem,
    RunInfo,
    RunStatus,
    Source,
    SourceUnit,
    UpdateRule,
)

__all__ = [
    "run",
    "run_async",
    "run_pipeline",
    "run_pipeline_async",
    "run_pipeline_result",
    "run_pipeline_result_async",
    "run_insight",
    "run_insight_result",
    "build_agent_result",
    "RuntimeConfig",
    "load_runtime_config",
    "InsightRequest",
    "InsightResponse",
    "NormalizedRequest",
    "RunInfo",
    "Source",
    "SourceUnit",
    "Constraints",
    "ClaimItem",
    "AssumptionItem",
    "LimitationItem",
    "ProblemCandidateItem",
    "InsightItem",
    "OpenQuestionItem",
    "EvidenceRef",
    "FailureItem",
    "PersonaDefinition",
    "PersonaScore",
    "EpistemicMode",
    "DerivationType",
    "UpdateRule",
    "Decision",
    "RunStatus",
    "JapaneseSummary",
]
