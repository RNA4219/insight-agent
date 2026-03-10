# Insight Agent Interfaces

## 1. 目的

本書は Insight Agent の入出力インターフェースを定義する。  
requirements.md が責務・スコープ・品質基準を定義し、reasoning_policy.md が推論規約を定義するのに対し、本書は実装者が迷わず入出力とデータ構造を扱えるように、要求を具体的なオブジェクト形へ落とし込むことを目的とする。

本書で定義するものは以下である。

- リクエスト I/F
- レスポンス I/F
- 内部処理単位
- 共通メタデータ
- 各出力要素のスキーマ
- status / decision / enum 定義
- エラー時の返却契約

## 2. 設計原則

### 2.1 JSON first

正規インターフェースは JSON とする。  
CLI / API / MCP のいずれも同じ論理スキーマを共有し、ラッパー差分は transport 層に閉じ込める。

### 2.2 Top-level と item-level を分離する

レスポンスは run 全体の状態を表す top-level と、各生成物を表す item-level を分離する。  
top-level は処理結果全体の状態を、item-level は各 claim / assumption / limitation / problem_candidate / insight / open_question の個別判断を持つ。

### 2.3 認識論的メタデータを item 単位で持つ

`epistemic_mode`、`derivation_type`、`confidence`、`update_rule` などは top-level ではなく item-level に付与する。  
run 全体の `confidence` は全体安定度を示す別値として扱う。

### 2.4 必須最小と拡張可能性を両立する

MVP で必要な必須フィールドは固定する。  
ただし将来の拡張に備え、追加メタデータや評価結果を格納可能な構造とする。

## 3. 利用形態

Insight Agent の論理インターフェースは以下の 3 形態から呼び出される想定とする。

- CLI
- API
- MCP

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
    "primary_persona": "operator"
  },
  "context": {
    "notes": "optional"
  },
  "options": {
    "include_source_units": false,
    "include_intermediate_items": false
  }
}
````

## 4.2 フィールド定義

### `mode`

固定値 `insight`。
Insight Agent 呼び出しであることを示す。

### `request_id`

任意。
呼び出し元での追跡用 ID。未指定時は実行側で採番してよい。

### `sources`

必須。
処理対象の入力資料配列。最低 1 件以上。

### `constraints`

任意。
件数制限、ドメイン指定、評価優先 persona などを定義する。

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

## 5.2 必須フィールド

### `source_id`

必須。
資料単位の一意識別子。

### `source_type`

必須。
以下のいずれかを取る。

* `text`
* `paper`
* `article`
* `design_doc`
* `memo`
* `summary`
* `other`

### `title`

任意だが推奨。
資料名または簡易ラベル。

### `content`

必須。
処理対象テキスト本文。

### `metadata`

任意。
出典や補助情報。

## 6. Internal Processing Interface

## 6.1 SourceUnit

Source は内部で `SourceUnit` に正規化される。
`SourceUnit` は API の正規返却対象ではないが、`options.include_source_units=true` の場合に返却可能とする。

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

## 6.2 フィールド定義

### `unit_id`

unit 単位の一意識別子。

### `parent_source_id`

元の source を示す ID。

### `section_path`

見出しや章立ての階層表現。存在しない場合は空配列可。

### `order_index`

資料内の順序番号。

### `content`

unit 本文。

### `char_count`

参考用文字数。

## 6.3 分割方針

* 長文は section / heading / paragraph 境界を優先して分割する
* 1 unit は「意味が保てる最小まとまり」を目安とする
* 機械的な固定長分割は最後の fallback とする
* 分割後も元資料との対応を追跡可能であること

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
    "finished_at": "2026-03-10T12:00:03Z"
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

## 7.2 フィールド定義

### `run`

必須。
実行単位の状態。

### `claims`

必須。
`ClaimItem` 配列。

### `assumptions`

必須。
`AssumptionItem` 配列。

### `limitations`

必須。
`LimitationItem` 配列。

### `problem_candidates`

必須。
`ProblemCandidateItem` 配列。

### `insights`

必須。
`InsightItem` 配列。

### `open_questions`

必須。
`OpenQuestionItem` 配列。

### `evidence_refs`

必須。
`EvidenceRef` 配列。item から参照される根拠辞書。

### `failures`

任意だが推奨。
partial / failed 時の failure context 配列。

### `confidence`

必須。
run 全体の総合 confidence。

### `source_units`

任意。
`options.include_source_units=true` の場合に返却してよい。

## 8. Run Interface

## 8.1 RunInfo

```json
{
  "run_id": "run_001",
  "request_id": "req_001",
  "mode": "insight",
  "status": "completed",
  "started_at": "2026-03-10T12:00:00Z",
  "finished_at": "2026-03-10T12:00:03Z"
}
```

## 8.2 `status`

以下のいずれかを取る。

* `completed`
* `partial`
* `failed`

### `completed`

主要要件を満たして正常完了した状態。

### `partial`

一部成果は返せるが、十分な候補生成や根拠接続に失敗した状態。

### `failed`

有用な最終候補は十分に返せなかったが、failure context は構造化して返している状態。

## 9. 共通 Item Interface

すべての主要出力要素は共通メタデータを持つ。

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

## 9.2 共通フィールド定義

### `id`

必須。
各配列内で一意な識別子。

### `statement`

必須。
当該要素の本文。

### `epistemic_mode`

必須。
reasoning_policy.md の mode 定義に従う。

* `observation`
* `interpretation`
* `hypothesis`
* `scenario`
* `vision`
* `open_question`

### `derivation_type`

必須。
生成経路を示す。

* `direct`
* `inferred`
* `contrastive`
* `contextual`

### `confidence`

必須。
0.00 から 1.00 の実数。

### `evidence_refs`

必須。
`EvidenceRef.id` への参照配列。

### `parent_refs`

任意。
他要素への参照配列。

### `update_rule`

必須。
再評価時の基本方針。

* `retain`
* `revise`
* `discard`
* `branch`

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

## 10.2 フィールド定義

### `evidence_id`

必須。
根拠の一意識別子。

### `source_id`

必須。
どの source に属する根拠か。

### `unit_id`

任意だが推奨。
どの unit に属する根拠か。

### `quote`

任意。
短い引用または要約断片。

### `span`

任意。
文字範囲または位置情報。

### `note`

任意。
根拠補足。

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

## 11.2 補足

* claim は原則として `epistemic_mode=observation` を取る
* 著者の明示主張を抽出対象とする
* 再解釈を混ぜない

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

## 12.2 補足

* assumption は明示・暗黙の両方を含む
* 暗黙前提の場合は `derivation_type=inferred` が多い
* claim と混同しない

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

## 13.2 補足

* limitation は明示 limitation だけでなく、評価不足や一般化不能性も含む
* 著者明示の limitation は `direct`
* 読み取りから補う limitation は `inferred`

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
      "persona_id": "researcher",
      "axis_scores": {
        "evidence_grounding": 0.62,
        "novelty": 0.71,
        "explanatory_power": 0.77,
        "feasibility": 0.73,
        "maintainability": 0.55,
        "testability": 0.80,
        "leverage": 0.69,
        "robustness": 0.64
      },
      "weighted_score": 0.72,
      "decision": "accept",
      "reason_summary": "評価軸の欠落が明確で、後続検証に落とし込みやすい。"
    }
  ],
  "decision": "accept",
  "update_rule": "retain"
}
```

## 14.2 必須フィールド

### `problem_id`

必須。
problem candidate の一意識別子。

### `statement`

必須。
課題候補本文。

### `problem_type`

必須。
以下のいずれか。

* `assumption_gap`
* `evaluation_gap`
* `operational_gap`
* `integration_gap`
* `long_horizon_gap`
* `cost_maintenance_gap`
* `safety_governance_gap`
* `adoption_gap`
* `knowledge_gap`
* `other`

### `scope`

必須。
課題の作用範囲。

* `local`
* `component`
* `system`
* `workflow`
* `organization`
* `ecosystem`

### `epistemic_mode`

必須。
原則として `interpretation` または `hypothesis`。

### `derivation_type`

必須。
`direct` / `inferred` / `contrastive` / `contextual`

### `confidence`

必須。
0.00 から 1.00。

### `evidence_refs`

必須。
根拠参照配列。

### `parent_refs`

任意だが推奨。
元となった claim / assumption / limitation 参照。

### `assumption_refs`

任意。
関連 assumption 参照。

### `limitation_refs`

任意。
関連 limitation 参照。

### `support_signals`

任意。
この候補を支持する条件。

### `failure_signals`

任意。
この候補が崩れる条件。

### `fatal_risks`

任意。
採用停止要因。

### `persona_scores`

任意だが推奨。
persona ごとの評価配列。

### `decision`

必須。
統合判断。

* `accept`
* `reserve`
* `reject`
* `needs_more_evidence`

### `update_rule`

必須。
retain / revise / discard / branch

## 15. Persona Score Interface

## 15.1 PersonaScore

```json
{
  "persona_id": "operator",
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
  "decision": "accept",
  "reason_summary": "運用移植時の監視項目として扱いやすい。"
}
```

## 15.2 フィールド定義

### `persona_id`

必須。
`researcher` / `operator` / `strategist` など。

### `axis_scores`

必須。
評価軸別スコア辞書。

### `weighted_score`

必須。
重み付き総合スコア。

### `decision`

必須。
persona 単位の判断。

### `reason_summary`

任意だが推奨。
簡潔な理由説明。

## 16. Insight Interface

## 16.1 InsightItem

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

## 16.2 補足

* insight は problem candidate の上位束ね
* 単一強候補の再定式化でもよい
* 単なる感想文にしない

## 17. Open Question Interface

## 17.1 OpenQuestionItem

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

## 17.2 フィールド定義

### `question_id`

必須。
open question の一意識別子。

### `promotion_condition`

必須。
hypothesis へ昇格する条件。

### `closure_condition`

必須。
closed へ移る条件。

### `review_after`

必須。
再確認時刻。

### `status`

必須。
以下のいずれか。

* `open`
* `promoted`
* `closed`
* `stale`

## 18. Failure Interface

## 18.1 FailureItem

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

## 18.2 フィールド定義

### `failure_id`

必須。
失敗文脈の識別子。

### `stage`

必須。
失敗発生段階。

* `normalization`
* `extraction`
* `discovery`
* `evaluation`
* `consolidation`

### `reason`

必須。
簡潔な失敗理由。

### `details`

任意。
詳細説明。

### `related_refs`

任意。
関連 source / unit / item 参照。

### `suggested_next_action`

任意。
再試行提案。

## 19. Constraints Interface

## 19.1 Constraints

```json
{
  "domain": "machine_learning",
  "max_problem_candidates": 5,
  "max_insights": 3,
  "primary_persona": "operator"
}
```

## 19.2 フィールド定義

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
複数 persona conflict 時の優先 persona。

## 20. Options Interface

## 20.1 Options

```json
{
  "include_source_units": false,
  "include_intermediate_items": false
}
```

### `include_source_units`

true の場合、正規化後 unit を返却してよい。

### `include_intermediate_items`

true の場合、補助的な中間解釈を返却してよい。
MVP では false を推奨する。

## 21. Enum Summary

## 21.1 `epistemic_mode`

* `observation`
* `interpretation`
* `hypothesis`
* `scenario`
* `vision`
* `open_question`

## 21.2 `derivation_type`

* `direct`
* `inferred`
* `contrastive`
* `contextual`

## 21.3 `update_rule`

* `retain`
* `revise`
* `discard`
* `branch`

## 21.4 `decision`

* `accept`
* `reserve`
* `reject`
* `needs_more_evidence`

## 21.5 `run.status`

* `completed`
* `partial`
* `failed`

## 21.6 `open_question.status`

* `open`
* `promoted`
* `closed`
* `stale`

## 22. requirements.md / reasoning_policy.md との接続

### 22.1 requirements.md との接続

requirements.md で定義したトップレベル出力項目は、本書の `InsightResponse` に対応する。

* `claims` → `ClaimItem[]`
* `assumptions` → `AssumptionItem[]`
* `limitations` → `LimitationItem[]`
* `problem_candidates` → `ProblemCandidateItem[]`
* `insights` → `InsightItem[]`
* `open_questions` → `OpenQuestionItem[]`
* `evidence_refs` → `EvidenceRef[]`
* `confidence` → run 全体 confidence

### 22.2 reasoning_policy.md との接続

reasoning_policy.md で定義した以下の要素は、各 item に埋め込む。

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

## 23. MVP サブセット

MVP-1 では最低限以下の実装を必須とする。

* `InsightRequest`
* `InsightResponse`
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

MVP-1 では以下は簡略化してよい。

* `scenario`
* `vision`
* `include_intermediate_items`
* 補助軸の詳細スコア
* 複雑な conflict 解決メタデータ

## 24. 最小完全レスポンス例

```json
{
  "run": {
    "run_id": "run_001",
    "request_id": "req_001",
    "mode": "insight",
    "status": "completed",
    "started_at": "2026-03-10T12:00:00Z",
    "finished_at": "2026-03-10T12:00:03Z"
  },
  "claims": [
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
  ],
  "assumptions": [
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
  ],
  "limitations": [
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
  ],
  "problem_candidates": [
    {
      "problem_id": "pb_001",
      "statement": "評価が短期ベンチマークに偏っており、長期運用時の性能劣化が未検証である。",
      "problem_type": "evaluation_gap",
      "scope": "system",
      "epistemic_mode": "hypothesis",
      "derivation_type": "inferred",
      "confidence": 0.68,
      "evidence_refs": ["ev_003"],
      "parent_refs": ["cl_001", "lm_001"],
      "assumption_refs": ["as_001"],
      "limitation_refs": ["lm_001"],
      "support_signals": [
        "評価期間が短い"
      ],
      "failure_signals": [
        "長期運用データで同傾向が維持される"
      ],
      "fatal_risks": [],
      "persona_scores": [],
      "decision": "accept",
      "update_rule": "retain"
    }
  ],
  "insights": [
    {
      "id": "in_001",
      "statement": "この資料の本質的ボトルネックは精度指標そのものではなく、評価設計が長期運用条件を捉えていない点にある。",
      "epistemic_mode": "interpretation",
      "derivation_type": "contextual",
      "confidence": 0.72,
      "evidence_refs": ["ev_003"],
      "parent_refs": ["pb_001"],
      "update_rule": "retain"
    }
  ],
  "open_questions": [
    {
      "question_id": "oq_001",
      "statement": "長期運用下で性能劣化が実際に起きるかは追加追試が必要である。",
      "epistemic_mode": "open_question",
      "derivation_type": "inferred",
      "confidence": 0.31,
      "evidence_refs": ["ev_003"],
      "parent_refs": ["pb_001"],
      "promotion_condition": "長期追試結果が得られること",
      "closure_condition": "必要検証が完了すること",
      "review_after": "2026-04-01T00:00:00Z",
      "status": "open",
      "update_rule": "revise"
    }
  ],
  "evidence_refs": [
    {
      "evidence_id": "ev_001",
      "source_id": "src_001",
      "unit_id": "unit_001",
      "quote": "モデル X はベンチマーク Y で従来法を上回る",
      "span": {
        "start": 10,
        "end": 42
      },
      "note": ""
    },
    {
      "evidence_id": "ev_002",
      "source_id": "src_001",
      "unit_id": "unit_002",
      "quote": "評価設定の説明",
      "span": {
        "start": 50,
        "end": 110
      },
      "note": ""
    },
    {
      "evidence_id": "ev_003",
      "source_id": "src_001",
      "unit_id": "unit_003",
      "quote": "長期運用条件についての記述欠落",
      "span": {
        "start": 120,
        "end": 210
      },
      "note": ""
    }
  ],
  "failures": [],
  "confidence": 0.78
}
```

## 25. 結論

Insight Agent のインターフェースは、run 全体の状態と item 単位の認識論的メタデータを明確に分離し、後続工程がそのまま利用できる構造を持たなければならない。

そのため、本書では以下を固定する。

* Top-level request / response
* Source / SourceUnit
* BaseItem
* EvidenceRef
* Claim / Assumption / Limitation
* ProblemCandidate
* Insight
* OpenQuestion
* Failure
* 各種 enum と接続規約

この I/F により、Insight Agent は単なる要約結果ではなく、後続の評価・保存・ロードマップ化に耐える構造化成果物を返す。