"""Insight Agent - A problem discovery core agent.

This package provides tools for analyzing documents and extracting
structured insights including claims, assumptions, limitations,
and problem candidates.
"""

from insight_core.pipeline import run_insight, run_pipeline
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
    # Main API
    "run_pipeline",
    "run_insight",
    # Request/Response
    "InsightRequest",
    "InsightResponse",
    "NormalizedRequest",
    "RunInfo",
    "Source",
    "SourceUnit",
    "Constraints",
    # Items
    "ClaimItem",
    "AssumptionItem",
    "LimitationItem",
    "ProblemCandidateItem",
    "InsightItem",
    "OpenQuestionItem",
    "EvidenceRef",
    "FailureItem",
    # Persona
    "PersonaDefinition",
    "PersonaScore",
    # Enums
    "EpistemicMode",
    "DerivationType",
    "UpdateRule",
    "Decision",
    "RunStatus",
]