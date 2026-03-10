# Insight Agent Interfaces

## 1. 目的

本書は Insight Agent の入出力インターフェースを定義する。
`requirements.md` が責務・スコープ・品質基準を定義し、`reasoning_policy.md` が推論規約を定義するのに対し、本書は実装者が迷わず入出力とデータ構造を扱えるように、要求を具体的なオブジェクト形へ落とし込むことを目的とする。

本書で定義するものは以下である。

* リクエスト I/F
* レスポンス I/F
* 内部処理単位
* 共通メタデータ
* persona の JSON 定義
* 各出力要素のスキーマ
* status / decision / enum 定義
* エラー時の返却契約

## 2. 設計原則

### 2.1 JSON first

正規インターフェースは JSON とする。
CLI / API / MCP のいずれも同じ論理スキーマを共有し、ラッパー差分は transport 層に閉じ込める。

### 2.2 Top-level と item-level を分離する

レスポンスは run 全体の状態を表す top-level と、各生成物を表す item-level を分離する。

### 2.3 認識論的メタデータを item 単位で持つ

`epistemic_mode`、`derivation_type`、`confidence`、`update_rule` などは item-level に付与する。
run 全体の `confidence` は全体安定度を示す別値として扱う。

### 2.4 persona は JSON で拡張可能にする

persona はコードへ固定埋め込みせず、JSON 配列で定義可能とする。
request で `personas[]` が与えられた場合はそれを優先し、未指定時は標準 6 persona セットを適用する。

## 3. 利用形態

Insight Agent の論理インターフェースは以下の 3 形態から呼び出される想定とする。

* CLI
* API
* MCP

どの形態でも、最終的に `InsightRequest` を受け取り、`InsightResponse` を返す。

## 4. Top-level Request Interface

## 4.1 InsightRequest

```json
{
  "mode": "insight",
  "request_id": "req_001",
  "sources": [
    {
      "source_id": "src_001",
      "source_type": "text",
      "title": "Paper A",
      "content": "..."
    }
  ],
  "constraints": {
    "domain": "optional",
    "max_problem_candidates": 5,
    "max_insights": 3,
    "primary_persona": "data_researcher"
  },
  "personas": [
    {
      "persona_id": "data_researcher",
      "name": "Data Researcher",
      "role": "データ分析が得意な研究者",
      "description": "根拠密度、検証可能性、評価設計を重視する。",
      "objective": "再現可能で分析可能な課題を特定する",
      "priorities": ["evidence_grounding", "testability", "explanatory_power"],
      "penalties": ["unsupported_leap", "weak_measurement"],
      "time_horizon": "short_to_mid_term",
      "risk_tolerance": "low",
      "evidence_preference": "quantitative",
      "acceptance_rule": "測定可能な検証計画に落ちること",
      "weight": 1.0
    }
  ],
  "context": {
    "notes": "optional"
  },
  "options": {
    "include_source_units": false,
    "include_intermediate_items": false
  }
}
```

## 4.2 フィールド定義

### `mode`

固定値 `insight`。

### `request_id`

任意。
呼び出し元での追跡用 ID。未指定時は実行側で採番してよい。

### `sources`

必須。
処理対象の入力資料配列。最低 1 件以上。

### `constraints`

任意。
件数制限、ドメイン指定、評価優先 persona などを定義する。

### `personas`

任意。
評価に使う persona 定義の JSON 配列。未指定時は標準 6 persona セットを用いる。ハード上限は設けないが、`persona_id` 重複は許容しない。

### `context`

任意。
呼び出し元から補足情報を与える自由領域。推論規約を上書きするものではない。

### `options`

任意。
デバッグや検証のための追加出力制御。

## 5. Source Interface

## 5.1 Source

```json
{
  "source_id": "src_001",
  "source_type": "text",
  "title": "Paper A",
  "content": "...",
  "metadata": {
    "author": "optional",
    "url": "optional",
    "published_at": "optional",
    "language": "optional"
  }
}
```

## 6. Internal Processing Interface

## 6.1 SourceUnit

```json
{
  "unit_id": "unit_001",
  "parent_source_id": "src_001",
  "section_path": ["3", "3.2", "Limitations"],
  "order_index": 12,
  "content": "...",
  "char_count": 840
}
```

## 7. Top-level Response Interface

## 7.1 InsightResponse

```json
{
  "run": {
    "run_id": "run_001",
    "request_id": "req_001",
    "mode": "insight",
    "status": "completed",
    "started_at": "2026-03-10T12:00:00Z",
    "finished_at": "2026-03-10T12:00:03Z",
    "applied_personas": ["bright_generalist", "data_researcher", "operator"],
    "persona_source": "default",
    "persona_catalog_version": "default_personas.v1"
  },
  "claims": [],
  "assumptions": [],
  "limitations": [],
  "problem_candidates": [],
  "insights": [],
  "open_questions": [],
  "evidence_refs": [],
  "failures": [],
  "confidence": 0.78,
  "source_units": []
}
```

## 8. Run Interface

## 8.1 RunInfo

```json
{
  "run_id": "run_001",
  "request_id": "req_001",
  "mode": "insight",
  "status": "completed",
  "started_at": "2026-03-10T12:00:00Z",
  "finished_at": "2026-03-10T12:00:03Z",
  "applied_personas": ["bright_generalist", "data_researcher", "operator"],
  "persona_source": "default",
  "persona_catalog_version": "default_personas.v1"
}
```

## 8.2 フィールド定義

### `status`

* `completed`
* `partial`
* `failed`

### `applied_personas`

適用した persona ID の配列。評価順序そのものを表す。

### `persona_source`

persona の取得元。以下のいずれかを取る。

* `default`
* `request`
* `merged`

### `persona_catalog_version`

標準 persona 利用時のカタログ識別子。request inline のみで評価した場合は `request_inline` を返してよい。

## 9. 共通 Item Interface

## 9.1 BaseItem

```json
{
  "id": "base_001",
  "statement": "string",
  "epistemic_mode": "interpretation",
  "derivation_type": "direct",
  "confidence": 0.82,
  "evidence_refs": ["ev_001"],
  "parent_refs": [],
  "update_rule": "retain"
}
```

## 10. Evidence Interface

## 10.1 EvidenceRef

```json
{
  "evidence_id": "ev_001",
  "source_id": "src_001",
  "unit_id": "unit_003",
  "quote": "optional",
  "span": {
    "start": 120,
    "end": 240
  },
  "note": "optional"
}
```

## 11. Claim Interface

## 11.1 ClaimItem

```json
{
  "id": "cl_001",
  "statement": "モデル X はベンチマーク Y で従来法を上回る。",
  "epistemic_mode": "observation",
  "derivation_type": "direct",
  "confidence": 0.93,
  "evidence_refs": ["ev_001"],
  "parent_refs": [],
  "update_rule": "retain"
}
```

## 12. Assumption Interface

## 12.1 AssumptionItem

```json
{
  "id": "as_001",
  "statement": "評価データ分布が実運用分布と大きく乖離しないことが前提となっている。",
  "epistemic_mode": "interpretation",
  "derivation_type": "inferred",
  "confidence": 0.67,
  "evidence_refs": ["ev_002"],
  "parent_refs": ["cl_001"],
  "update_rule": "revise"
}
```

## 13. Limitation Interface

## 13.1 LimitationItem

```json
{
  "id": "lm_001",
  "statement": "長期運用条件での性能検証が不足している。",
  "epistemic_mode": "interpretation",
  "derivation_type": "direct",
  "confidence": 0.86,
  "evidence_refs": ["ev_003"],
  "parent_refs": ["cl_001"],
  "update_rule": "retain"
}
```

## 14. Problem Candidate Interface

## 14.1 ProblemCandidateItem

```json
{
  "problem_id": "pb_001",
  "statement": "評価が短期ベンチマークに偏っており、長期運用時の性能劣化が未検証である。",
  "problem_type": "evaluation_gap",
  "scope": "system",
  "epistemic_mode": "hypothesis",
  "derivation_type": "inferred",
  "confidence": 0.68,
  "evidence_refs": ["ev_003", "ev_007"],
  "parent_refs": ["cl_002", "lm_001"],
  "assumption_refs": ["as_004"],
  "limitation_refs": ["lm_001"],
  "support_signals": [
    "評価期間が短い",
    "継続運用条件の記述がない"
  ],
  "failure_signals": [
    "長期運用データで同傾向が維持される",
    "分布変化下での追試結果が良好"
  ],
  "fatal_risks": [
    "別資料で長期性能データが既に示されている場合、この候補は弱まる"
  ],
  "persona_scores": [
    {
      "persona_id": "data_researcher",
      "axis_scores": {
        "evidence_grounding": 0.81,
        "novelty": 0.58,
        "explanatory_power": 0.77,
        "feasibility": 0.73,
        "maintainability": 0.55,
        "testability": 0.80,
        "leverage": 0.69,
        "robustness": 0.64
      },
      "weighted_score": 0.74,
      "applied_weight": 1.0,
      "decision": "accept",
      "reason_summary": "評価軸の欠落が明確で、追試計画に落とし込みやすい。"
    },
    {
      "persona_id": "operator",
      "axis_scores": {
        "evidence_grounding": 0.73,
        "novelty": 0.42,
        "explanatory_power": 0.66,
        "feasibility": 0.82,
        "maintainability": 0.79,
        "testability": 0.71,
        "leverage": 0.61,
        "robustness": 0.76
      },
      "weighted_score": 0.75,
      "applied_weight": 1.0,
      "decision": "accept",
      "reason_summary": "運用条件での検証不足は導入時リスクとして扱いやすい。"
    }
  ],
  "decision": "accept",
  "update_rule": "retain"
}
```

## 15. Persona Definition Interface

## 15.1 PersonaDefinition

```json
{
  "persona_id": "data_researcher",
  "name": "Data Researcher",
  "role": "データ分析が得意な研究者",
  "description": "根拠密度、検証可能性、評価設計を重視する。",
  "objective": "再現可能で分析可能な課題を特定する",
  "priorities": ["evidence_grounding", "testability", "explanatory_power"],
  "penalties": ["unsupported_leap", "weak_measurement"],
  "time_horizon": "short_to_mid_term",
  "risk_tolerance": "low",
  "evidence_preference": "quantitative",
  "acceptance_rule": "測定可能な検証計画に落ちること",
  "weight": 1.0
}
```

## 15.2 フィールド定義

### `persona_id`

必須。
request 内で一意な persona 識別子。

### `name`

必須。
persona 表示名。

### `role`

任意だが推奨。
persona の役割ラベル。

### `description`

任意だが推奨。
persona の判断スタイルの説明。

### `objective`

必須。
persona が重視する到達目標。

### `priorities`

必須。
高く評価する軸または観点の配列。

### `penalties`

任意。
減点対象の配列。

### `time_horizon`

任意。
重視する時間軸。

### `risk_tolerance`

任意。
リスク許容度。

### `evidence_preference`

任意。
好む根拠の型。

### `acceptance_rule`

必須。
受け入れ判断の短い規則。

### `weight`

任意。
persona の重み。未指定時は `1.0` とする。

## 16. Persona Score Interface

## 16.1 PersonaScore

```json
{
  "persona_id": "bright_generalist",
  "axis_scores": {
    "evidence_grounding": 0.62,
    "novelty": 0.50,
    "explanatory_power": 0.70,
    "feasibility": 0.79,
    "maintainability": 0.74,
    "testability": 0.82,
    "leverage": 0.66,
    "robustness": 0.68
  },
  "weighted_score": 0.73,
  "applied_weight": 1.0,
  "decision": "accept",
  "reason_summary": "複数の活用先に広げやすく、前向きな探索価値が高い。"
}
```

## 16.2 フィールド定義

### `persona_id`

必須。
`run.applied_personas` または `personas[].persona_id` を参照する。未指定時の標準値は `bright_generalist` / `data_researcher` / `curiosity_entertainer` / `researcher` / `operator` / `strategist`。

### `axis_scores`

必須。
評価軸別スコア辞書。

### `weighted_score`

必須。
重み付き総合スコア。

### `applied_weight`

必須。
正規化後に適用された weight。

### `decision`

必須。
persona 単位の判断。

### `reason_summary`

任意だが推奨。
簡潔な理由説明。

## 17. Insight Interface

## 17.1 InsightItem

```json
{
  "id": "in_001",
  "statement": "この手法の本質的ボトルネックはモデル精度ではなく、評価設計が短期ベンチマーク中心で長期運用条件を捉えていない点にある。",
  "epistemic_mode": "interpretation",
  "derivation_type": "contextual",
  "confidence": 0.72,
  "evidence_refs": ["ev_003", "ev_007"],
  "parent_refs": ["pb_001", "pb_003"],
  "update_rule": "retain"
}
```

## 18. Open Question Interface

## 18.1 OpenQuestionItem

```json
{
  "question_id": "oq_001",
  "statement": "長期運用時の性能劣化が実際に起きるかは、分布変化下での追試が必要である。",
  "epistemic_mode": "open_question",
  "derivation_type": "inferred",
  "confidence": 0.31,
  "evidence_refs": ["ev_003"],
  "parent_refs": ["pb_001"],
  "promotion_condition": "分布変化下での長期追試結果が得られること",
  "closure_condition": "必要検証が完了し、課題の実在性が確認または否定されること",
  "review_after": "2026-04-01T00:00:00Z",
  "status": "open",
  "update_rule": "revise"
}
```

## 19. Failure Interface

## 19.1 FailureItem

```json
{
  "failure_id": "fl_001",
  "stage": "discovery",
  "reason": "problem_candidate が本文の言い換えに留まった",
  "details": "入力が薄く、limitation と assumption の分離が不安定だった",
  "related_refs": ["src_001", "unit_002"],
  "suggested_next_action": "追加資料を投入し、assumption 抽出を再試行する"
}
```

## 20. Constraints Interface

## 20.1 Constraints

```json
{
  "domain": "machine_learning",
  "max_problem_candidates": 5,
  "max_insights": 3,
  "primary_persona": "data_researcher"
}
```

## 20.2 フィールド定義

### `domain`

任意。
読解補助のための対象領域指定。

### `max_problem_candidates`

任意。
返却する課題候補の最大件数。

### `max_insights`

任意。
返却する insight の最大件数。

### `primary_persona`

任意。
複数 persona conflict 時の優先 persona。`personas[].persona_id` のいずれかを指定する。

## 21. Options Interface

## 21.1 Options

```json
{
  "include_source_units": false,
  "include_intermediate_items": false
}
```

## 22. Enum Summary

## 22.1 `epistemic_mode`

* `observation`
* `interpretation`
* `hypothesis`
* `scenario`
* `vision`
* `open_question`

## 22.2 `derivation_type`

* `direct`
* `inferred`
* `contrastive`
* `contextual`

## 22.3 `update_rule`

* `retain`
* `revise`
* `discard`
* `branch`

## 22.4 `decision`

* `accept`
* `reserve`
* `reject`
* `needs_more_evidence`

## 22.5 `run.status`

* `completed`
* `partial`
* `failed`

## 22.6 `run.persona_source`

* `default`
* `request`
* `merged`

## 22.7 `open_question.status`

* `open`
* `promoted`
* `closed`
* `stale`

## 23. `requirements.md` / `reasoning_policy.md` との接続

### 23.1 `requirements.md` との接続

`requirements.md` で定義したトップレベル出力項目は、本書の `InsightResponse` に対応する。

* `claims` → `ClaimItem[]`
* `assumptions` → `AssumptionItem[]`
* `limitations` → `LimitationItem[]`
* `problem_candidates` → `ProblemCandidateItem[]`
* `insights` → `InsightItem[]`
* `open_questions` → `OpenQuestionItem[]`
* `evidence_refs` → `EvidenceRef[]`
* `confidence` → run 全体 confidence
* `personas[]` → `PersonaDefinition[]`
* `run.applied_personas` / `run.persona_source` / `run.persona_catalog_version` → persona 監査情報

### 23.2 `reasoning_policy.md` との接続

`reasoning_policy.md` で定義した以下の要素は、各 item に埋め込む。

* `epistemic_mode`
* `derivation_type`
* `confidence`
* `update_rule`

また以下は対応 item に埋め込む。

* `support_signals`
* `failure_signals`
* `persona_scores`
* `promotion_condition`
* `closure_condition`

## 24. MVP サブセット

MVP-1 では最低限以下の実装を必須とする。

* `InsightRequest`
* `InsightResponse`
* `RunInfo`
* `PersonaDefinition`
* `ClaimItem`
* `AssumptionItem`
* `LimitationItem`
* `ProblemCandidateItem`
* `InsightItem`
* `OpenQuestionItem`
* `EvidenceRef`
* `FailureItem`
* `confidence`
* `decision`
* `epistemic_mode`
* `derivation_type`

## 25. 最小完全レスポンス例

```json
{
  "run": {
    "run_id": "run_001",
    "request_id": "req_001",
    "mode": "insight",
    "status": "completed",
    "started_at": "2026-03-10T12:00:00Z",
    "finished_at": "2026-03-10T12:00:03Z",
    "applied_personas": ["bright_generalist", "data_researcher", "curiosity_entertainer", "researcher", "operator", "strategist"],
    "persona_source": "default",
    "persona_catalog_version": "default_personas.v1"
  },
  "claims": [],
  "assumptions": [],
  "limitations": [],
  "problem_candidates": [],
  "insights": [],
  "open_questions": [],
  "evidence_refs": [],
  "failures": [],
  "confidence": 0.78
}
```

## 26. 結論

Insight Agent のインターフェースは、run 全体の状態と item 単位の認識論的メタデータを明確に分離し、後続工程がそのまま利用できる構造を持たなければならない。

そのため、本書では以下を固定する。

* Top-level request / response
* Source / SourceUnit
* BaseItem
* EvidenceRef
* Claim / Assumption / Limitation
* ProblemCandidate
* PersonaDefinition / PersonaScore
* RunInfo の persona 監査情報
* Insight
* OpenQuestion
* Failure
* 各種 enum と接続規約
