# Insight Agent Requirements

## 1. 文書の役割

本書は Insight Agent の正本要件を定義する。
既存の `insight-agent_requirements_summary.md` を要約版の入力資料とみなし、本書では実装判断に必要な粒度まで要件を確定する。

本書の対象は以下である。

* プロダクトの目的と責務
* 機能要件
* 非機能要件
* MVP 段階定義
* 受け入れ条件

推論の規約は `reasoning_policy.md`、入出力の形は `interfaces.md`、実装準備と構成設計は `implementation_spec.md` を正本とする。

## 2. 位置づけ

Insight Agent は、論文・技術資料・設計資料・調査メモなどを読み取り、課題候補と高次の気づきを構造化して返す課題発見専用コアである。

本エージェントは要約器でもロードマップ生成器でもない。
役割は、後続の設計・研究・ロードマップ工程へ引き渡せる「根拠付きの問題設定」を生成することにある。

## 3. 目的

Insight Agent は、入力資料に対して以下を実現しなければならない。

* 主張を抽出する
* 前提を抽出する
* limitation と評価漏れを抽出する
* ギャップ、矛盾、欠落、運用上の不整合を検出する
* problem candidate を定式化する
* problem candidate を束ねて insight を生成する
* 根拠不足の論点を open question として保持する

## 4. スコープ

### 4.1 対象

* 論文
* 技術記事
* 設計資料
* 調査メモ
* 要約済みテキスト
* 外部工程で抽出済みの本文テキスト

### 4.2 対象外

* 実装コード生成
* R&D ロードマップ生成そのもの
* 実験計画の詳細分解
* 無制限な自律探索
* raw PDF / HTML の取得
* UI 構築

## 5. システム責務

Insight Agent は最低限、以下の責務を持つ。

1. 入力 source を正規化する
2. source を意味単位の unit へ分解する
3. claim / assumption / limitation を抽出する
4. gap / omission / contradiction を検出する
5. problem candidate を生成する
6. persona に基づいて候補を評価する
7. insight と open question を生成する
8. evidence と confidence を付与して構造化レスポンスを返す
9. 失敗時は failure context を残して partial / failed として返す
10. 実行時に適用した persona セットを追跡可能にする

## 6. 機能要件

### 6.1 入力正規化

* `mode=insight` の request を受け取ること
* `sources` を 1 件以上受け取ること
* source ごとに `source_id` と本文を必須とすること
* 長文は section / heading / paragraph 境界を優先して分割すること
* 分割後も `parent_source_id` と `unit_id` で追跡可能であること

### 6.2 抽出

* claim は著者または資料の明示主張を抽出すること
* assumption は明示前提と暗黙前提を区別せず保持しつつ、claim と混同しないこと
* limitation は明示 limitation に加え、評価不足や一般化不能性も含めて抽出対象とすること
* 各抽出 item は evidence を 1 件以上参照すること

### 6.3 課題発見

* problem candidate は本文の言い換えではなく、破綻可能性または構造的欠落を表現すること
* problem candidate は `problem_type`、`scope`、`decision`、`confidence` を必ず持つこと
* support_signals と failure_signals を持てる構造を備えること
* 根拠が不十分な場合は hypothesis を無理に確定せず open question に逃がすこと

### 6.4 評価

* 標準 persona として `bright_generalist`、`data_researcher`、`curiosity_entertainer`、`researcher`、`operator`、`strategist` の 6 種をサポートすること
* persona ごとの評価結果と統合 decision を返せること
* `primary_persona` 指定時は統合判断に優先反映すること
* `data_researcher` または `operator` が致命的 feasibility / evidence grounding / maintainability 問題で reject した候補は accept しないこと
* persona 数が増えても評価順序と統合結果が決定的であること

### 6.5 persona 構成

* persona 定義は JSON 配列で与えられ、追加数にハード上限を設けないこと
* request ごとに `personas[]` を省略した場合は標準 6 persona セットを適用すること
* `primary_persona` は `personas[].persona_id` のいずれかを参照すること
* `persona_id` は集合内で一意であること
* `weight` を持つ場合は正の数とし、統合時に正規化すること
* persona 定義は目的、優先軸、ペナルティ、時間軸、リスク許容度、根拠選好を保持できること

### 6.6 監査性

* `run` には適用した `applied_personas` を記録すること
* `run` には persona の取得元を示す `persona_source` を記録すること
* 標準 persona 利用時は `persona_catalog_version` を記録すること

### 6.7 出力

* 正規出力は JSON とすること
* top-level には `run`、`claims`、`assumptions`、`limitations`、`problem_candidates`、`insights`、`open_questions`、`evidence_refs`、`confidence` を含むこと
* `partial` / `failed` の場合でも `failures` を返すこと
* `options.include_source_units=true` の場合は `source_units` を返せること

## 7. 非機能要件

### 7.1 アーキテクチャ

* CLI / API / MCP は薄いラッパーにすること
* 業務ロジックは `insight_core` 相当のコアモジュールに集約すること
* transport 層と推論ロジック層を分離すること

### 7.2 品質

* 同一入力に対し、極端にぶれた出力を避けること
* 不確実な場合は confidence を下げ、open question を増やすこと
* 出典不明の断定を避けること
* 後続の保存層や Roadmap Agent が再加工なしで利用できる形にすること

### 7.3 運用

* `run_id` 単位で追跡可能であること
* 複数 source の処理に拡張可能であること
* 失敗時に再試行判断ができる failure context を残すこと
* 標準 persona カタログはファイルとしてバージョン管理されること

## 8. MVP 定義

### 8.1 MVP-1

* 単一資料入力
* claim / assumption / limitation 抽出
* problem candidate を最大 3 件返却
* persona evaluation の最小実装
* JSON 出力
* confidence 付与
* applied persona 監査情報の出力

### 8.2 MVP-2

* 複数資料入力
* source unit 分解
* insight / open question の充実
* item メタデータの拡張
* custom persona merge の安定化

### 8.3 MVP-3

* 非同期バッチ
* CLI / API / MCP の共通コア化完了
* scenario / vision の整理強化
* failure context の再利用強化

## 9. 受け入れ条件

### 9.1 MVP-1 受け入れ条件

* 単一 source の request を受け取り、`completed` または `partial` で JSON を返せる
* `claims`、`assumptions`、`limitations` の各配列が空であっても構造として常に存在する
* 少なくとも 1 件の `problem_candidate` もしくは 1 件以上の `open_question` を返す
* 主要 item すべてに `confidence` と `evidence_refs` が付与される
* persona 評価の統合 `decision` が problem candidate に入る
* `run.applied_personas`、`run.persona_source`、`run.persona_catalog_version` が妥当な値で返る
* 根拠不足の候補を hypothesis として断定しない

### 9.2 品質受け入れ条件

* claim と assumption の混同がない
* limitation が本文の欠落や評価不足として抽出できる
* problem candidate が単なる要約文になっていない
* insight が候補の羅列ではなく上位構造の説明になっている
* 同一 persona セットと同一入力で適用順序が変わらない
* failed / partial 時に `failures` が返る

## 10. オープン事項

以下は実装前に方針合意が必要な設計論点であり、本書では未確定として保持する。

* evidence の `span` を文字範囲で持つか、token 範囲も持つか
* source 分割の閾値を文字数基準、段落基準、またはモデル token 基準のどれに置くか
* 外部知識を許可する場合の出典契約をどこまで必須にするか
* `persona_catalog_version` の命名規則をどこまで厳格にするか

## 11. 文書間の関係

* 本書は「何を満たすか」を定義する
* `reasoning_policy.md` は「どういう規律で推論するか」を定義する
* `interfaces.md` は「どの JSON を返すか」を定義する
* `implementation_spec.md` は「どう実装に分解するか」を定義する
