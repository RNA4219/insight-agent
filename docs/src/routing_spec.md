# Persona Routing Specification

## 1. 目的

本書は Insight Agent における Persona Routing 機能の実装仕様を定義する。
従来の全Persona並列評価から、Lead Persona主導のルーティング評価へ移行し、ノイズ削減・根拠適合性向上・設定容易性を実現する。

## 2. 設計原則

### 2.1 Lead Persona責任

- Lead Persona はルーティング決定のみを担当
- 下流Personaの評価作業自体は各Personaが責任を持つ
- Lead Personaの視点バイアスを防ぐため、独立した監査Personaを必ず含める

### 2.2 Evidence Density Aware

- 証拠密度に応じて呼び出すPersona数を動的調整
- 低密度時は過度な推測を避け、監査・確認役を優先

### 2.3 設定駆動

- コード修正なしでルーティング設定を変更可能
- YAML/JSON設定ファイルで制御

## 3. データ構造

### 3.1 RoutingPlan

```python
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


class RoutingPlan(BaseModel):
    lead_persona: str
    problem_type: str | None = None
    evidence_density: EvidenceDensity | None = None
    selected_personas: list[str] = Field(min_length=1)
    skipped_personas: list[str] = Field(default_factory=list)
    role_assignments: dict[str, PersonaRole]
    routing_reason: list[str] = Field(min_length=1)
    skip_reasons: dict[str, str] = Field(default_factory=dict)
    routing_confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='after')
    def validate_consistency(self):
        # selected_personas は全て role_assignments に存在すること
        for p in self.selected_personas:
            if p not in self.role_assignments:
                raise ValueError(f"Missing role assignment for: {p}")

        # selected と skipped は重複しないこと
        overlap = set(self.selected_personas) & set(self.skipped_personas)
        if overlap:
            raise ValueError(f"Overlapping personas: {overlap}")

        return self
```

### 3.2 RoutingConfig

```python
class RoutingRules(BaseModel):
    preferred: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    enabled: bool = True
    lead_persona: str = "bright_generalist"
    lead_persona_mutable: bool = True

    fallback_personas: list[str] = ["data_researcher", "operator"]

    mandatory_audit_personas: list[str] = ["data_researcher"]

    max_personas_by_evidence_density: dict[str, int] = {
        "low": 3,
        "medium": 4,
        "high": 6
    }

    routing_rules: dict[str, RoutingRules] = Field(default_factory=dict)
```

## 4. 処理フロー

### 4.1 改定フロー

```
1. Extract claims/assumptions/limitations
2. Estimate evidence density
3. Run problem typing (optional)
4. Invoke lead persona → receive routing_plan
5. Invoke only selected personas
6. Aggregate role-based outputs
7. Generate insights
8. Persist routing metadata
```

### 4.2 Fallback Flow

```
If routing_plan is invalid or lead persona fails:
1. Use fallback routing config
2. lead_persona: bright_generalist
3. downstream: [data_researcher, operator]
4. Record fallback event in failures
```

## 5. モジュール構成

### 5.1 `insight_core.router`

```
router/
├── __init__.py
├── schemas.py          # RoutingPlan, RoutingConfig, EvidenceDensity, PersonaRole
├── config.py           # Configuration loading from YAML/JSON
├── density_estimator.py # Evidence density estimation
├── lead_persona.py     # Lead persona invocation and routing plan generation
├── validator.py        # Routing plan validation
└── fallback.py         # Fallback routing logic
```

### 5.2 責務

| モジュール | 責務 |
|-----------|------|
| `config.py` | YAML/JSONからの設定読み込み、デフォルト値適用 |
| `density_estimator.py` | claims/limitationsから証拠密度を推定 |
| `lead_persona.py` | Lead Persona呼び出し、routing_plan生成 |
| `validator.py` | routing_plan整合性検証 |
| `fallback.py` | フォールバック時のルーティング生成 |

## 6. Evidence Density Estimation

### 6.1 推定ロジック

```python
def estimate_evidence_density(
    claims: list[ClaimItem],
    limitations: list[LimitationItem],
    evidence_refs: list[EvidenceRef],
) -> EvidenceDensity:
    """証拠密度を推定する"""

    # 基本スコア
    claim_count = len(claims)
    limitation_count = len(limitations)
    evidence_count = len(evidence_refs)

    # 信頼度平均
    claim_confidence = sum(c.confidence for c in claims) / len(claims) if claims else 0.5

    # 密度スコア計算
    density_score = (
        (claim_count * 0.2) +
        (evidence_count * 0.3) +
        (claim_confidence * 0.5) -
        (limitation_count * 0.1)  # limitationが多い = ギャップが多い
    )

    if density_score < 0.4:
        return EvidenceDensity.LOW
    elif density_score < 0.7:
        return EvidenceDensity.MEDIUM
    else:
        return EvidenceDensity.HIGH
```

## 7. Lead Persona Prompt

### 7.1 ルーティング用プロンプト

```text
あなたは「{lead_persona_name}」として、以下の分析結果から最適な評価者を選定してください。

## 入力情報
- 主張: {claims}
- 前提: {assumptions}
- 制約: {limitations}
- 推定問題タイプ: {problem_type}
- 証拠密度: {evidence_density}

## 利用可能なPersona
{available_personas}

## 選択ルール
1. 証拠密度が低い場合、呼び出すPersona数を2-3に制限
2. 監査役Persona（data_researcher, operator等）を最低1名含める
3. novelty系Personaは明確なメリットがある場合のみ選択
4. 各選択Personaに役割を割り当てる

## 出力形式
JSON形式のrouting_planを出力してください。
```

## 8. 設定ファイル

### 8.1 デフォルト設定

```yaml
# config/routing.yaml
persona_routing:
  enabled: true
  lead_persona: bright_generalist
  lead_persona_mutable: true

  fallback_personas:
    - data_researcher
    - operator

  mandatory_audit_personas:
    - data_researcher

  max_personas_by_evidence_density:
    low: 3
    medium: 4
    high: 6

  routing_rules:
    evaluation_gap:
      preferred:
        - data_researcher
        - operator
        - researcher
      optional:
        - strategist

    generalization_gap:
      preferred:
        - researcher
        - strategist
        - data_researcher

    deployment_risk:
      preferred:
        - operator
        - strategist
        - researcher

    novelty_opportunity:
      preferred:
        - curiosity_entertainer
        - bright_generalist
```

## 9. 統合変更点

### 9.1 schemas.py 追加

```python
# insight_core/schemas.py に追加

class RoutingPlan(BaseModel):
    """Persona routing plan."""
    lead_persona: str
    problem_type: str | None = None
    evidence_density: EvidenceDensity | None = None
    selected_personas: list[str]
    skipped_personas: list[str] = Field(default_factory=list)
    role_assignments: dict[str, str]
    routing_reason: list[str]
    skip_reasons: dict[str, str] = Field(default_factory=dict)
    routing_confidence: float


class InsightResponse(BaseModel):
    # 既存フィールドに追加
    routing_plan: RoutingPlan | None = None
```

### 9.2 pipeline.py 変更

```python
# Step 4.5: Routing (新規追加)
if routing_config.enabled:
    routing_plan = await run_routing(
        claims, assumptions, limitations,
        evidence_refs, problem_type, evidence_density,
        llm, routing_config
    )
    selected_personas = [
        p for p in normalized.personas
        if p.persona_id in routing_plan.selected_personas
    ]
else:
    # 従来の全Persona評価
    selected_personas = normalized.personas
```

## 10. 検証事項

### 10.1 単体テスト

- [ ] RoutingPlan バリデーション（selected/skipped重複なし）
- [ ] RoutingPlan バリデーション（全selectedにrole割当あり）
- [ ] Evidence Density 推定（low/medium/high）
- [ ] Fallback routing 生成
- [ ] 設定ファイル読み込み

### 10.2 統合テスト

- [ ] 低密度入力でPersona数が3以下になる
- [ ] 監査Personaが必ず含まれる
- [ ] Lead Persona失敗時にフォールバック適用
- [ ] routing_planがInsightResponseに含まれる

## 11. 非機能要件

| 要件 | 内容 |
|------|------|
| 説明可能性 | 各Persona選択/スキップ理由が人間可読であること |
| コスト効率 | 平均Persona呼び出し数が従来より削減されること |
| 証拠規律 | 弱い根拠の仮説を強い事実として扱わないこと |
| 拡張性 | 新規Persona追加が設定変更のみで可能であること |

## 12. 移行計画

### Phase 1: 基盤実装

1. RoutingPlan/RoutingConfig スキーマ追加
2. 設定ファイル読み込み機能
3. Evidence Density 推定

### Phase 2: Lead Persona実装

1. Lead Persona プロンプト設計
2. routing_plan 生成ロジック
3. バリデーション

### Phase 3: パイプライン統合

1. pipeline.py への統合
2. フォールバック実装
3. メタデータ永続化

### Phase 4: テスト・検証

1. 単体テスト
2. 統合テスト
3. 既存テストとの互換性確認