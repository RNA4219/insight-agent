# Persona Routing - 要求定義書

## 1. 概要

Insight AgentのPersona評価において、全Persona並列評価からLead Persona主導のルーティング評価へ移行する。

### 1.1 目的

- 不要なPersona呼び出しの削減
- 問題タイプと評価者Personaの適合性向上
- ルーティング決定の説明可能性確保
- コード修正なしでの設定変更を実現
- 根拠の軽さに応じた評価の規律維持

### 1.2 スコープ

Persona選択とルーティングのみを対象とする。既存のclaim抽出、limitation抽出、evidence保存契約は変更しない（ルーティングメタデータの追加を除く）。

---

## 2. 機能要件

### FR-001: Lead Personaの導入
**優先度: 高**

システムは下流評価Personaを呼び出す前に、必ず1つのLead Personaを呼び出さなければならない。

**受け入れ基準:**
- AC-001: Lead Personaが必ず呼び出されること

### FR-002: デフォルトLead Persona
**優先度: 高**

デフォルトのLead Personaは `bright_generalist` とする。

**受け入れ基準:**
- AC-002: 明示的な設定がない場合、Lead Personaが `bright_generalist` であること

### FR-003: 設定可能なLead Persona
**優先度: 高**

Lead Personaは設定または実行時オプションで変更可能とする。コード編集を必要としないこと。

**受け入れ基準:**
- AC-003: 設定変更でLead Personaを変更でき、コード修正が不要であること

### FR-004: Lead Personaの責務
**優先度: 高**

Lead Personaは現在の入力に対してどの下流Personaを呼び出すべきかを決定する。

**考慮事項:**
- claims
- limitations
- assumptions（存在する場合）
- problem typing結果（利用可能な場合）
- evidence density
- オプションの実行コンテキスト

**受け入れ基準:**
- AC-004: Lead Personaが選択Persona一覧を出力すること

### FR-005: Routing Plan出力
**優先度: 高**

Lead Personaは構造化された `routing_plan` を返さなければならない。

**必須フィールド:**
| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `lead_persona` | string | ✓ | Lead Persona ID |
| `selected_personas` | array[string] | ✓ | 選択されたPersona一覧（1件以上） |
| `skipped_personas` | array[string] | - | スキップされたPersona一覧 |
| `role_assignments` | object | ✓ | Persona毎の役割マップ |
| `routing_reason` | array[string] | ✓ | 選択理由（1件以上） |
| `skip_reasons` | object | - | スキップ理由マップ |
| `routing_confidence` | number | ✓ | ルーティング信頼度（0-1） |

**オプションフィールド:**
| フィールド | 型 | 説明 |
|-----------|-----|------|
| `problem_type` | string | 粗い問題分類 |
| `evidence_density` | enum | low/medium/high |

**受け入れ基準:**
- AC-005: 各runでrouting_planが保存されること

### FR-006: 役割ベースのディスパッチ
**優先度: 高**

Lead Personaは選択された各Personaに役割を割り当てなければならない。

**定義済み役割:**
| 役割 | 説明 |
|------|------|
| `evidence_checker` | 証拠確認 |
| `hypothesis_refiner` | 仮説精緻化 |
| `operational_risk_reviewer` | 運用リスクレビュー |
| `structural_abstraction` | 構造的抽象化 |
| `novelty_probe` | 新規性探索 |

**受け入れ基準:**
- AC-006: 選択された全Personaに役割が割り当てられていること

### FR-007: Evidence Density対応ルーティング
**優先度: 中**

Lead Personaは証拠密度が低い場合、呼び出すPersona数を削減する。

**期待動作:**
| 証拠密度 | Persona数（目安） |
|---------|------------------|
| low | 2-3 |
| medium | 3-4 |
| high | 必要に応じて拡張可 |

**受け入れ基準:**
- AC-007: 低証拠密度入力で、Persona呼び出し数が従来より少ないこと

### FR-008: スキップ理由の保持
**優先度: 中**

スキップされたPersonaについて、明示的なスキップ理由を保持する。

### FR-009: 監査Personaの必須含入
**優先度: 高**

設定で明示的に無効化されていない限り、選択セットに最低1つの監査向けPersonaを含める。

**推奨監査Persona:**
- `data_researcher`
- `researcher`
- `operator`

**受け入れ基準:**
- AC-008: 監査Personaが最低1名含まれること（無効化されていない場合）

### FR-010: ルーティングフォールバック
**優先度: 高**

Lead Personaが有効なrouting_planを返せない場合、フォールバックルールを適用する。

**推奨フォールバック:**
- Lead Persona: `bright_generalist`
- 下流Persona: `data_researcher`, `operator`

**受け入れ基準:**
- AC-009: routing無効時、フォールバックが適用・記録されること

### FR-011: 決定論的モード対応
**優先度: 低**

同一入力・同一設定で安定したルーティング結果を生成する決定論的モードをサポートする。

### FR-012: ルーティングメタデータの永続化
**優先度: 高**

ルーティングメタデータをrun結果と共に永続化し、後でトレース可能にする。

---

## 3. 非機能要件

### NFR-001: 説明可能性
**優先度: 高**

人間のレビューアが各Personaが選択/スキップされた理由を理解できること。

### NFR-002: コスト効率
**優先度: 高**

平均Persona呼び出し数が従来の全Persona設計より削減されること。

### NFR-003: 証拠規律
**優先度: 高**

ルーティング層は弱い根拠の仮説を強い根拠の事実として扱ってはならない。証拠密度が低い場合、推測的拡張より監査・確認役を優先する。

### NFR-004: 拡張性
**優先度: 中**

新規Personaは設定とルーティングルール更新で追加可能とし、大規模なアーキテクチャ変更を不要とする。

### NFR-005: 責任の分離
**優先度: 高**

Lead Personaはルーティングを担当し、下流レビュー作業を置き換えるものではない。下流Personaは割り当てられた役割出力に責任を持つ。

---

## 4. 制約事項

### CR-001: Lead Personaバイアス制御
**優先度: 高**

Lead Personaが自身の視点を強化するPersonaのみを選択することを防ぐ。最低1つの選択Personaは独立した監査またはバランス役として機能すること。

### CR-002: デフォルトでの新規性抑制
**優先度: 中**

`curiosity_entertainer` 等の新規性重視Personaは、デフォルトですべての入力で呼び出してはならない。Lead Personaが特定のメリットを識別した場合のみ選択する。

### CR-003: 低証拠抑制
**優先度: 高**

証拠密度が低い場合、過度なPersonaファンアウトを抑制し、insightの過度な拡張を減らす。

---

## 5. データ契約

### 5.1 Routing Plan JSON Schema

```json
{
  "lead_persona": "bright_generalist",
  "problem_type": "evaluation_gap",
  "evidence_density": "low",
  "selected_personas": ["data_researcher", "operator", "researcher"],
  "skipped_personas": ["curiosity_entertainer", "strategist"],
  "role_assignments": {
    "data_researcher": "evidence_checker",
    "operator": "operational_risk_reviewer",
    "researcher": "hypothesis_refiner"
  },
  "routing_reason": [
    "single-metric evaluation concern is dominant",
    "evidence density is low, so fan-out is constrained",
    "operational misread risk is material"
  ],
  "skip_reasons": {
    "curiosity_entertainer": "novelty contribution is low for this input",
    "strategist": "insufficient evidence for higher-order escalation"
  },
  "routing_confidence": 0.82
}
```

### 5.2 バリデーションルール

**アプリケーションロジックで検証:**
1. `selected_personas` の全ての値が `role_assignments` のキーに存在すること
2. `selected_personas` と `skipped_personas` が重複しないこと

---

## 6. 設定要件

### 6.1 設定ファイル形式（YAML）

```yaml
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

---

## 7. 処理フロー

### 7.1 改定フロー

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

### 7.2 フォールバックフロー

```
If routing_plan is invalid or lead persona fails:
1. Use fallback routing config
2. lead_persona: bright_generalist
3. downstream: [data_researcher, operator]
4. Record fallback event in failures
```

---

## 8. 受け入れテスト

| ID | テスト内容 | 対応要件 |
|----|-----------|---------|
| AC-001 | デフォルトでlead_personaが`bright_generalist`であること | FR-002 |
| AC-002 | 設定変更でlead_personaを変更できること | FR-003 |
| AC-003 | 低証拠密度入力でPersona数が従来より少ないこと | FR-007 |
| AC-004 | 各runでrouting_planが保存されること | FR-005, FR-012 |
| AC-005 | 選択された全Personaに役割が割り当てられていること | FR-006 |
| AC-006 | 監査Personaが最低1名含まれること | FR-009 |
| AC-007 | routing無効時、フォールバックが適用・記録されること | FR-010 |

---

## 9. 用語定義

| 用語 | 定義 |
|------|------|
| Lead Persona | ルーティング決定を担当するPersona |
| Downstream Persona | Lead Personaによって選択され評価を行うPersona |
| Evidence Density | 入力に含まれる証拠の密度（低/中/高） |
| Role Assignment | 選択Personaに割り当てられる役割 |
| Routing Plan | Lead Personaが出力するルーティング決定結果 |