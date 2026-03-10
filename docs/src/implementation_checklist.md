# Implementation Checklist - Persona Routing

## 現状実装状況

### ✅ 実装済み（MVP-1 + 拡張）

| カテゴリ | 機能 | モジュール | 状態 |
|---------|------|-----------|------|
| 非同期API | `complete_async`, `complete_json_async` | `llm_client.py` | ✅ 完了 |
| リトライ機能 | `max_retries`, `retry_backoff_seconds` | `llm_client.py` | ✅ 完了 |
| チェックポイント | 保存・復旧・resume | `pipeline.py` | ✅ 完了 |
| 並列実行 | `max_concurrency`, Semaphore | `extractor.py`, `evaluator.py` | ✅ 完了 |
| パイプライン非同期化 | `run_pipeline_async` | `pipeline.py` | ✅ 完了 |
| 基本スキーマ | Claim, Assumption, Limitation, ProblemCandidate等 | `schemas.py` | ✅ 完了 |
| Persona評価 | 6種デフォルトPersona | `evaluator.py` | ✅ 完了 |

### ❌ 未実装（Persona Routing要件）

| カテゴリ | 機能 | 必要モジュール | 優先度 |
|---------|------|---------------|-------|
| スキーマ | `RoutingPlan`, `RoutingConfig` | `schemas.py` | 高 |
| スキーマ | `EvidenceDensity`, `PersonaRole` (enum) | `schemas.py` | 高 |
| スキーマ | `InsightResponse.routing_plan` 追加 | `schemas.py` | 高 |
| ルーティング | Lead Persona呼び出し | `router/lead_persona.py` | 高 |
| ルーティング | routing_plan生成・バリデーション | `router/validator.py` | 高 |
| ルーティング | Evidence Density推定 | `router/density_estimator.py` | 中 |
| ルーティング | フォールバック処理 | `router/fallback.py` | 中 |
| 設定 | YAML/JSON設定読み込み | `router/config.py` | 中 |
| パイプライン | ルーティング統合 | `pipeline.py` | 高 |

---

## 実装チェックリスト

### Phase 1: スキーマ追加（高優先度）

- [ ] `EvidenceDensity` enum追加（low/medium/high）
- [ ] `PersonaRole` enum追加
- [ ] `RoutingPlan` モデル追加
- [ ] `RoutingConfig` モデル追加
- [ ] `InsightResponse` に `routing_plan: RoutingPlan | None` 追加
- [ ] `Options` に `routing_enabled: bool` 追加

### Phase 2: Router モジュール実装（高優先度）

- [ ] `insight_core/router/` ディレクトリ作成
- [ ] `router/__init__.py` 作成
- [ ] `router/schemas.py` - RoutingPlan, RoutingConfig定義
- [ ] `router/config.py` - YAML/JSON設定読み込み
- [ ] `router/density_estimator.py` - Evidence Density推定ロジック
- [ ] `router/lead_persona.py` - Lead Persona呼び出し・routing_plan生成
- [ ] `router/validator.py` - routing_plan整合性検証
- [ ] `router/fallback.py` - フォールバックルーティング生成

### Phase 3: パイプライン統合（高優先度）

- [ ] `run_pipeline_async` にルーティングステップ追加
- [ ] Lead Persona呼び出し後、selected_personasのみ評価
- [ ] routing_planのInsightResponseへの格納
- [ ] フォールバック時のエラーハンドリング
- [ ] routing_planのチェックポイント保存・復旧対応

### Phase 4: 設定ファイル（中優先度）

- [ ] `config/routing.yaml` 作成
- [ ] デフォルトルーティングルール定義
- [ ] problem_type別のpreferred/optional personas定義
- [ ] `max_personas_by_evidence_density` 設定

### Phase 5: テスト（中優先度）

- [ ] `RoutingPlan` バリデーションテスト
- [ ] Evidence Density推定テスト
- [ ] Lead Personaルーティングテスト（モック使用）
- [ ] フォールバックテスト
- [ ] パイプライン統合テスト
- [ ] 低密度入力でPersona数が制限されることの確認

### Phase 6: CLI対応（低優先度）

- [ ] `--routing-enabled/--no-routing` オプション追加
- [ ] `--lead-persona` オプション追加
- [ ] `--routing-config` オプション追加

---

## 詳細タスク

### 1. schemas.py 変更内容

```python
# 追加するEnum
class EvidenceDensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class PersonaRole(str, Enum):
    EVIDENCE_CHECKER = "evidence_checker"
    HYPOTHESIS_REFINER = "hypothesis_refiner"
    OPERATIONAL_RISK_REVIEWER = "operational_risk_reviewer"
    STRUCTURAL_ABSTRACTION = "structural_abstraction"
    NOVELTY_PROBE = "novelty_probe"

# 追加するモデル
class RoutingPlan(BaseModel):
    lead_persona: str
    problem_type: str | None = None
    evidence_density: EvidenceDensity | None = None
    selected_personas: list[str]
    skipped_personas: list[str] = []
    role_assignments: dict[str, PersonaRole]
    routing_reason: list[str]
    skip_reasons: dict[str, str] = {}
    routing_confidence: float

class RoutingConfig(BaseModel):
    enabled: bool = True
    lead_persona: str = "bright_generalist"
    lead_persona_mutable: bool = True
    fallback_personas: list[str] = ["data_researcher", "operator"]
    mandatory_audit_personas: list[str] = ["data_researcher"]
    max_personas_by_evidence_density: dict[str, int] = {
        "low": 3, "medium": 4, "high": 6
    }

# InsightResponse に追加
class InsightResponse(BaseModel):
    # 既存フィールド...
    routing_plan: RoutingPlan | None = None  # 追加
```

### 2. pipeline.py 変更内容

```python
# 新しいフロー
async def run_pipeline_async(...):
    # ... 既存の抽出処理 ...

    # Step 4.5: Routing（新規追加）
    if routing_config.enabled:
        # Evidence Density推定
        evidence_density = estimate_evidence_density(claims, limitations, evidence_refs)

        # Lead Persona呼び出し
        routing_plan = await run_routing(
            claims, assumptions, limitations,
            evidence_refs, problem_type, evidence_density,
            llm, routing_config
        )

        # 選択されたPersonaのみ評価
        selected_personas = [
            p for p in normalized.personas
            if p.persona_id in routing_plan.selected_personas
        ]
    else:
        # 従来の全Persona評価
        selected_personas = normalized.personas
        routing_plan = None

    # Step 5: Evaluate with selected personas only
    candidates = await evaluate_candidates_async(
        candidates, selected_personas, llm, ...
    )

    # レスポンスにrouting_planを含める
    return build_response(
        ...,
        routing_plan=routing_plan,
    )
```

### 3. router/lead_persona.py 実装内容

```python
async def generate_routing_plan(
    claims: list[ClaimItem],
    assumptions: list[AssumptionItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
    problem_type: str | None,
    evidence_density: EvidenceDensity,
    available_personas: list[PersonaDefinition],
    llm: LLMClient,
    config: RoutingConfig,
) -> RoutingPlan:
    """Lead Personaを呼び出してrouting_planを生成"""

    system_prompt = build_routing_prompt(
        claims, assumptions, limitations,
        problem_type, evidence_density,
        available_personas, config
    )

    response = await llm.complete_json_async(system_prompt, user_prompt)
    routing_plan = parse_routing_response(response)

    # バリデーション
    validate_routing_plan(routing_plan, available_personas, config)

    return routing_plan
```

---

## 受け入れ基準

### AC-ADD-001
- [ ] デフォルトでlead_personaが`bright_generalist`であること

### AC-ADD-002
- [ ] 設定変更でlead_personaを変更できること（コード修正不要）

### AC-ADD-003
- [ ] 低証拠密度入力で、呼び出しPersona数が従来より少ないこと

### AC-ADD-004
- [ ] 各runで`routing_plan`が保存されること

### AC-ADD-005
- [ ] 選択された全Personaにroleが割り当てられていること

### AC-ADD-006
- [ ] 監査Personaが最低1名含まれること（無効化されていない場合）

### AC-ADD-007
- [ ] routing無効時、フォールバックが適用・記録されること

---

## 推定工数

| Phase | 見積時間 |
|-------|---------|
| Phase 1: スキーマ | 1h |
| Phase 2: Router | 3h |
| Phase 3: 統合 | 2h |
| Phase 4: 設定 | 1h |
| Phase 5: テスト | 2h |
| Phase 6: CLI | 1h |
| **合計** | **10h** |