"""Schema definitions for Insight Agent interfaces.

This module defines all Pydantic models based on interfaces.md specification.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class EpistemicMode(str, Enum):
    """認識論的モード."""

    OBSERVATION = "observation"
    INTERPRETATION = "interpretation"
    HYPOTHESIS = "hypothesis"
    SCENARIO = "scenario"
    VISION = "vision"
    OPEN_QUESTION = "open_question"


class DerivationType(str, Enum):
    """導出タイプ."""

    DIRECT = "direct"
    INFERRED = "inferred"
    CONTRASTIVE = "contrastive"
    CONTEXTUAL = "contextual"


class UpdateRule(str, Enum):
    """更新ルール."""

    RETAIN = "retain"
    REVISE = "revise"
    DISCARD = "discard"
    BRANCH = "branch"


class Decision(str, Enum):
    """判断."""

    ACCEPT = "accept"
    RESERVE = "reserve"
    REJECT = "reject"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class RunStatus(str, Enum):
    """実行ステータス."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class PersonaSource(str, Enum):
    """Persona取得元."""

    DEFAULT = "default"
    REQUEST = "request"
    MERGED = "merged"


class OpenQuestionStatus(str, Enum):
    """Open Question ステータス."""

    OPEN = "open"
    PROMOTED = "promoted"
    CLOSED = "closed"
    STALE = "stale"


class ProblemType(str, Enum):
    """課題タイプ."""

    EVALUATION_GAP = "evaluation_gap"
    DATA_GAP = "data_gap"
    ASSUMPTION_WEAKNESS = "assumption_weakness"
    CONTRADICTION = "contradiction"
    OMITTED_FACTOR = "omitted_factor"
    OPERATIONAL_RISK = "operational_risk"
    SCALABILITY_LIMIT = "scalability_limit"
    GENERALIZATION_GAP = "generalization_gap"


class ProblemScope(str, Enum):
    """課題スコープ."""

    LOCAL = "local"
    SYSTEM = "system"
    GLOBAL = "global"


class EvidenceDensity(str, Enum):
    """証拠密度."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PersonaRole(str, Enum):
    """Persona役割."""

    EVIDENCE_CHECKER = "evidence_checker"
    HYPOTHESIS_REFINER = "hypothesis_refiner"
    OPERATIONAL_RISK_REVIEWER = "operational_risk_reviewer"
    STRUCTURAL_ABSTRACTION = "structural_abstraction"
    NOVELTY_PROBE = "novelty_probe"


# ============================================================================
# Source Interfaces
# ============================================================================


class SourceMetadata(BaseModel):
    """Source メタデータ."""

    author: str | None = None
    url: str | None = None
    published_at: str | None = None
    language: str | None = None


class Source(BaseModel):
    """入力ソース."""

    source_id: str
    source_type: str = "text"
    title: str | None = None
    content: str
    metadata: SourceMetadata | None = None


class SourceUnit(BaseModel):
    """ソース分割単位."""

    unit_id: str
    parent_source_id: str
    section_path: list[str] = Field(default_factory=list)
    order_index: int
    content: str
    char_count: int


# ============================================================================
# Evidence Interface
# ============================================================================


class Span(BaseModel):
    """テキスト範囲."""

    start: int
    end: int


class EvidenceRef(BaseModel):
    """根拠参照."""

    evidence_id: str
    source_id: str
    unit_id: str | None = None
    quote: str | None = None
    span: Span | None = None
    note: str | None = None


# ============================================================================
# Base Item Interface
# ============================================================================


class BaseItem(BaseModel):
    """Item基底クラス."""

    id: str
    statement: str
    epistemic_mode: EpistemicMode
    derivation_type: DerivationType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    parent_refs: list[str] = Field(default_factory=list)
    update_rule: UpdateRule = UpdateRule.RETAIN


# ============================================================================
# Item Interfaces
# ============================================================================


class ClaimItem(BaseItem):
    """主張アイテム."""

    ...


class AssumptionItem(BaseItem):
    """前提アイテム."""

    ...


class LimitationItem(BaseItem):
    """制約アイテム."""

    ...


class InsightItem(BaseItem):
    """インサイトアイテム."""

    ...


# ============================================================================
# Persona Interfaces
# ============================================================================


class PersonaDefinition(BaseModel):
    """Persona定義."""

    persona_id: str
    name: str
    role: str | None = None
    description: str | None = None
    objective: str
    priorities: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    risk_tolerance: str | None = None
    evidence_preference: str | None = None
    acceptance_rule: str
    weight: float = Field(default=1.0, ge=0.0)


class PersonaScore(BaseModel):
    """Persona別スコア."""

    persona_id: str
    axis_scores: dict[str, float] = Field(default_factory=dict)
    weighted_score: float = Field(ge=0.0, le=1.0)
    applied_weight: float = Field(ge=0.0)
    decision: Decision
    reason_summary: str | None = None


# ============================================================================
# Problem Candidate Interface
# ============================================================================


class ProblemCandidateItem(BaseItem):
    """課題候補アイテム."""

    problem_id: str = Field(..., alias="id")
    problem_type: ProblemType | None = None
    scope: ProblemScope | None = None
    assumption_refs: list[str] = Field(default_factory=list)
    limitation_refs: list[str] = Field(default_factory=list)
    support_signals: list[str] = Field(default_factory=list)
    failure_signals: list[str] = Field(default_factory=list)
    fatal_risks: list[str] = Field(default_factory=list)
    persona_scores: list[PersonaScore] = Field(default_factory=list)
    decision: Decision = Decision.RESERVE

    model_config = {"populate_by_name": True}


# ============================================================================
# Open Question Interface
# ============================================================================


class OpenQuestionItem(BaseModel):
    """未解決問いアイテム."""

    question_id: str
    statement: str
    epistemic_mode: EpistemicMode = EpistemicMode.OPEN_QUESTION
    derivation_type: DerivationType = DerivationType.INFERRED
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    parent_refs: list[str] = Field(default_factory=list)
    promotion_condition: str | None = None
    closure_condition: str | None = None
    review_after: datetime | None = None
    status: OpenQuestionStatus = OpenQuestionStatus.OPEN
    update_rule: UpdateRule = UpdateRule.REVISE


# ============================================================================
# Failure Interface
# ============================================================================


class FailureItem(BaseModel):
    """失敗情報."""

    failure_id: str
    stage: str
    reason: str
    details: str | None = None
    related_refs: list[str] = Field(default_factory=list)
    suggested_next_action: str | None = None


# ============================================================================
# Constraints Interface
# ============================================================================


class Constraints(BaseModel):
    """制約条件."""

    domain: str | None = None
    max_problem_candidates: int = 5
    max_insights: int = 3
    primary_persona: str | None = None


# ============================================================================
# Options Interface
# ============================================================================


class Options(BaseModel):
    """オプション."""

    include_source_units: bool = False
    include_intermediate_items: bool = False
    checkpoint_path: str | None = None
    resume: bool = False
    max_concurrency: int = 4


# ============================================================================
# Context Interface
# ============================================================================


class Context(BaseModel):
    """コンテキスト."""

    notes: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Request Interface
# ============================================================================


class InsightRequest(BaseModel):
    """Insight Agent リクエスト."""

    mode: str = "insight"
    request_id: str | None = None
    sources: list[Source]
    constraints: Constraints | None = None
    personas: list[PersonaDefinition] | None = None
    context: Context | None = None
    options: Options | None = None


# ============================================================================
# Run Info Interface
# ============================================================================


class RunInfo(BaseModel):
    """実行情報."""

    run_id: str
    request_id: str | None = None
    mode: str = "insight"
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    applied_personas: list[str] = Field(default_factory=list)
    persona_source: PersonaSource = PersonaSource.DEFAULT
    persona_catalog_version: str | None = None


# ============================================================================
# Routing Interfaces
# ============================================================================


class RoutingPlan(BaseModel):
    """Personaルーティング計画."""

    lead_persona: str
    problem_type: str | None = None
    evidence_density: EvidenceDensity | None = None
    selected_personas: list[str] = Field(min_length=1)
    skipped_personas: list[str] = Field(default_factory=list)
    role_assignments: dict[str, PersonaRole] = Field(default_factory=dict)
    routing_reason: list[str] = Field(min_length=1)
    skip_reasons: dict[str, str] = Field(default_factory=dict)
    routing_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RoutingRules(BaseModel):
    """ルーティングルール（問題タイプ別）."""

    preferred: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    """ルーティング設定."""

    enabled: bool = True
    lead_persona: str = "bright_generalist"
    lead_persona_mutable: bool = True
    fallback_personas: list[str] = Field(default_factory=lambda: ["data_researcher", "operator"])
    mandatory_audit_personas: list[str] = Field(default_factory=lambda: ["data_researcher"])
    max_personas_by_evidence_density: dict[str, int] = Field(
        default_factory=lambda: {"low": 3, "medium": 4, "high": 6}
    )
    routing_rules: dict[str, RoutingRules] = Field(default_factory=dict)


# ============================================================================
# Response Interface
# ============================================================================


class InsightResponse(BaseModel):
    """Insight Agent レスポンス."""

    run: RunInfo
    claims: list[ClaimItem] = Field(default_factory=list)
    assumptions: list[AssumptionItem] = Field(default_factory=list)
    limitations: list[LimitationItem] = Field(default_factory=list)
    problem_candidates: list[ProblemCandidateItem] = Field(default_factory=list)
    insights: list[InsightItem] = Field(default_factory=list)
    open_questions: list[OpenQuestionItem] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    failures: list[FailureItem] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source_units: list[SourceUnit] = Field(default_factory=list)
    routing_plan: RoutingPlan | None = None


# ============================================================================
# Internal Processing Types
# ============================================================================


class NormalizedRequest(BaseModel):
    """正規化済みリクエスト."""

    run_id: str
    request_id: str
    sources: list[Source]
    constraints: Constraints
    personas: list[PersonaDefinition]
    persona_source: PersonaSource
    persona_catalog_version: str | None
    context: Context
    options: Options


class PersonaRegistry(BaseModel):
    """Persona レジストリ."""

    personas: list[PersonaDefinition]
    persona_source: PersonaSource
    catalog_version: str | None = None
    primary_persona_id: str | None = None

