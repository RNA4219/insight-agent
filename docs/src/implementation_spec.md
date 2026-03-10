# Insight Agent Implementation Specification

## 1. 目的

本書は Insight Agent の実装準備用仕様書である。
`requirements.md` と `reasoning_policy.md` を、開発着手可能なモジュール責務、処理シーケンス、検証観点へ落とし込む。

## 2. 実装方針

* transport と core を分離する
* core は純粋関数寄りに保ち、CLI / API / MCP から共通利用する
* 抽出、発見、評価、統合を明確な段階に分ける
* 失敗は例外で潰さず `failures` と `run.status` に残す
* persona は JSON registry と request inline 定義の両方を扱えるようにする
* MVP-1 は単一 source の品質安定化を優先する

## 3. 推奨モジュール構成

### 3.1 `insight_core.request_normalizer`

責務:
* request の必須項目検証
* request_id / run_id の補完
* source 型の正規化
* options / constraints の既定値補完

入出力:
* 入力: `InsightRequest`
* 出力: `NormalizedRequest`

### 3.2 `insight_core.unitizer`

責務:
* source を `SourceUnit` へ分解
* section / heading / paragraph 境界ベースで分割
* `parent_source_id`、`unit_id`、`order_index` を採番

### 3.3 `insight_core.extractor`

責務:
* claim / assumption / limitation を抽出
* item ごとの evidence 候補を紐づけ
* 直接抽出と推論抽出を区別

### 3.4 `insight_core.discovery`

責務:
* gap / omission / contradiction を検出
* problem candidate を生成
* support_signals / failure_signals / fatal_risks を付与

### 3.5 `insight_core.evaluator`

責務:
* JSON で定義された persona 別スコアリング
* persona weight を正規化して weighted_score を算出
* candidate の統合 decision を決定

### 3.6 `insight_core.consolidator`

責務:
* problem candidate から insight を生成
* 根拠不足の候補を open question へ落とす
* top-level confidence と run.status を確定する
* `run.applied_personas`、`run.persona_source`、`run.persona_catalog_version` を構成する

### 3.7 `insight_core.response_builder`

責務:
* `InsightResponse` を構成
* `options.include_source_units` を反映
* `failures` を最終レスポンスに統合

### 3.8 `insight_core.persona_registry`

責務:
* 標準 persona 6 種を JSON からロード
* request の `personas[]` を validation して実行時 registry を構成
* `primary_persona` が registry 内の `persona_id` を指しているか検証
* `persona_id` 重複、weight 不正値、空配列を validation error にする
* default / request / merged の取得元を判定する

推奨データ形式:
* `config/personas/default_personas.json`
* request 内 `personas[]`

## 4. 推奨処理シーケンス

1. request を検証し、persona registry を含む既定値を補完する
2. source を unit に分割する
3. unit から claim / assumption / limitation を抽出する
4. 抽出結果をもとに problem candidate を生成する
5. candidate を persona で評価し、weight を正規化する
6. insight / open question / failures を統合する
7. confidence と run.status を確定し response を返す

## 5. 実装データフロー

### 5.1 入力

* `InsightRequest`
* domain や primary_persona を含む constraints、ならびに `personas[]`
* notes などの context

### 5.2 中間生成物

* `NormalizedRequest`
* `ResolvedPersonaDefinition[]`
* `SourceUnit[]`
* `ClaimItem[]`
* `AssumptionItem[]`
* `LimitationItem[]`
* `ProblemCandidateDraft[]`
* `PersonaScore[]`
* `FailureItem[]`

### 5.3 出力

* `InsightResponse`

## 6. エラーハンドリング契約

### 6.1 `failed`

以下の場合は `failed` を返す。

* request 必須項目が不足し、処理継続不能
* source 本文が空で、意味抽出不能
* persona 定義に重複 `persona_id`、不正 `weight`、不正 `primary_persona` がある
* core 処理中に復旧不能な内部エラーが発生

### 6.2 `partial`

以下の場合は `partial` を返す。

* claim は抽出できたが problem candidate の品質が不足
* evidence 接続が一部不安定
* insight は作れないが open question は返せる

### 6.3 `completed`

以下を満たす場合は `completed` を返す。

* 最低 1 件の有効な problem candidate または insight がある
* 主要 item に evidence と confidence が付いている
* 適用 persona 情報が `run` に記録されている
* failure があっても結果全体として受け入れ条件を満たす

## 7. MVP-1 実装スコープ

### 7.1 必須

* 単一 source 処理
* request / response の schema 実装
* source unit 分割の最小実装
* claim / assumption / limitation 抽出
* problem candidate 最大 3 件生成
* persona 評価の最小実装
* insight 1 件以内、open question 3 件以内の生成
* failure context 返却
* default persona catalog のロード

### 7.2 後回し

* 複数 source の相互比較最適化
* scenario / vision の本格運用
* 非同期ジョブ制御
* 高度な persona カスタマイズ UI

## 8. 受け入れテスト観点

### 8.1 正常系

* 単一論文入力で `claims` / `assumptions` / `limitations` が返る
* limitation が明示されない資料でも、評価不足や運用ギャップが抽出される
* problem candidate に `decision` と `persona_scores` が入る
* `run.applied_personas` と `run.persona_source` が返る

### 8.2 境界系

* 短文メモ入力でも `partial` と `open_questions` を返せる
* persona 数が多くても array 順に deterministic に評価される
* `max_problem_candidates=0` のような不正 constraints を validation error として扱える
* evidence 候補が 1 件しかない場合でも confidence を下げて返せる

### 8.3 異常系

* `sources=[]` を reject できる
* `content` 欠落を `failed` で返せる
* `primary_persona` が未定義 ID を指したとき `failed` で返せる
* 内部抽出失敗時に `failures.stage` が埋まる

## 9. 品質ゲート

MVP-1 着手前に以下を満たすこと。

* `requirements.md`、`reasoning_policy.md`、`interfaces.md` の用語が一致している
* `problem_type`、`decision`、`epistemic_mode` の enum が固定されている
* source 分割方針が 1 つに決まっている
* default persona catalog JSON が存在する
* 同一 persona セットで同一入力なら `applied_personas` と decision が再現する

MVP-1 完了条件は以下とする。

* 最小完全レスポンス例を再現できる
* `partial` と `failed` の両方の返却パスをテストで確認済み
* item-level confidence と run-level confidence の区別が実装されている
* `run.persona_catalog_version` が標準セット利用時に返る

## 10. 未決定事項

* 抽出器をルールベース主導にするか、LLM 呼び出し主導にするか
* evidence の quote を必須化するか
* span を文字位置で持つか、unit 内相対位置で持つか
* custom persona を default と merge する既定戦略
* `persona_catalog_version` の命名規約
* external knowledge を使う場合の provenance 契約

## 11. 実装着手順

1. `interfaces.md` の schema を型として定義する
2. request validation、persona registry、response builder を先に作る
3. `config/personas/default_personas.json` を読み込む基盤を作る
4. unitizer と extractor の最小版を実装する
5. discovery / evaluator / consolidator を順に実装する
6. 正常系、partial、failed の各サンプルで受け入れ確認する
