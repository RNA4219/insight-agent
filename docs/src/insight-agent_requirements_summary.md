# Insight Agent 要件定義まとめ

## 1. 位置づけ

Insight Agent は、論文・技術資料・設計資料・調査メモなどを読み取り、単なる要約ではなく、後続の研究・設計・ロードマップ生成に使える「課題候補」と「気づき」を構造化して返す課題発見専用コアである。

本エージェントは、解決策の詳細設計や実験計画そのものを担わない。  
それらは後続の Roadmap Agent へ委譲する。

## 2. 目的

Insight Agent の目的は以下である。

- 資料中の主張を抽出する
- 主張の前提を抽出する
- 明示的・暗黙的な限界を抽出する
- 欠落、矛盾、運用ギャップ、評価漏れを検出する
- 課題候補を定式化する
- 上位の気づきを insight として束ねる
- 根拠不足な論点を open_question として保持する

要するに、Insight Agent の価値は「内容説明」ではなく「どこが課題かに気づくこと」にある。

## 3. 解決したい問題

既存の検索・要約・スキル的処理では、以下が弱い。

- 背景文脈を踏まえた課題発見
- 主張と前提の分離
- limitation や未記述領域の抽出
- ありきたりな要約を超えた insight 生成
- 後続の R&D ロードマップに接続できる粒度での課題定義

Insight Agent は、この不足を埋めるためのコアとして設計する。

## 4. スコープ

### 4.1 対象

- 論文
- 技術記事
- 設計資料
- 調査メモ
- 要約済みテキスト
- 外部工程で抽出済みの本文テキスト

### 4.2 対象外

- 実装コード生成
- R&D ロードマップ生成そのもの
- 実験計画の詳細分解
- 無制限な自律探索
- 深い多段推論のオーケストレーション
- raw PDF / HTML の取得
- UI 構築

## 5. 役割

Insight Agent の役割は、入力資料を読み、課題候補と気づきを構造化して返すことに集約される。

内部処理としては、最低限以下の流れを持つ。

1. 入力正規化
2. unit 分解
3. claim 抽出
4. assumption 抽出
5. limitation 抽出
6. gap / omission / contradiction 検出
7. problem_candidate 生成
8. insight 生成
9. open_question 生成
10. 候補評価
11. 結果構造化

## 6. 入力要件

### 6.1 入力単位

- 外部入力は汎用
- 内部処理単位は、論文相当のまとまりに正規化する
- 長文入力は section / heading / paragraph 境界で分割する
- `parent_source_id` と `unit_id` を保持する

### 6.2 最低入力形式

```json
{
  "mode": "insight",
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
    "max_problem_candidates": 5
  },
  "context": {
    "notes": "optional"
  }
}
````

### 6.3 必須入力

* `mode`
* `sources[]`
* 各 source の `source_id`
* 各 source の本文または実質同等の内容

## 7. 出力要件

### 7.1 正規出力

出力は JSON を正とする。
自然文のみの出力は禁止しないが、正規出力は構造化 JSON とする。

### 7.2 必須トップレベル項目

* `run`
* `claims`
* `assumptions`
* `limitations`
* `problem_candidates`
* `insights`
* `open_questions`
* `evidence_refs`
* `confidence`

### 7.3 出力の基本方針

* 主要要素は evidence に接続すること
* 根拠不足の論点は open_question に逃がすこと
* run 全体の `confidence` と、各要素個別の `confidence` を区別すること
* 失敗も構造化して残すこと

## 8. 認識論的モード

Insight Agent の各生成物は、以下の `epistemic_mode` を持つ。

### 8.1 observation

入力資料または明示的な外部知識から直接確認できる事実。

### 8.2 interpretation

observation を整理・要約・再表現したもの。
まだ新規説明や仮説には達していない。

### 8.3 hypothesis

observation / interpretation / 既知背景から導かれた、検証可能な説明または破綻予測。

### 8.4 scenario

複数の hypothesis を束ねた将来展開または構造展開。

### 8.5 vision

長期方向性、探索価値、意味づけを表す表現。
反証可能性は必須ではない。

### 8.6 open_question

重要だが、現時点では十分な根拠がなく、仮説として閉じるべきでない問い。

## 9. mode の昇格条件

### 9.1 interpretation → hypothesis

以下を満たす場合に限る。

* どの evidence から導いたか説明できる
* どの claim / assumption / limitation に依拠するか示せる
* 何が観測されれば支持が強まるか述べられる
* 何が観測されれば崩れるか述べられる
* 単なる感想や総評ではない

### 9.2 hypothesis → scenario

以下を満たす場合に限る。

* 複数 hypothesis 間の関係が明示されている
* 因果または時系列の接続が説明されている
* 単独仮説ではなく展開候補として意味がある

### 9.3 禁止事項

* 反証可能性のない表現を hypothesis として扱わない
* vision を hypothesis に偽装しない
* open_question を無理に hypothesis に閉じない

## 10. 課題発見規約

### 10.1 problem_candidate とみなす条件

以下のいずれかを満たす場合、problem_candidate として扱ってよい。

* 主張の成立条件が狭い
* 前提が暗黙であり、実運用で破綻しうる
* limitation が未記述または過小評価されている
* 評価指標が本質的問題を十分に捉えていない
* 研究条件では成立するが継続運用に落ちない
* スケール、コスト、保守、統合の観点が欠落している
* 他知識や過去事例と照合すると矛盾または空白がある
* 局所問題より、背後の構造問題の方が本質的である
* 成功事例だが再現条件が不透明である
* 単体では成立しても、上流または下流接続で破綻しうる

### 10.2 優先順位

課題発見は以下の順で優先する。

1. 明示的 limitation
2. 暗黙 assumption
3. evaluation gap
4. operational gap
5. long-horizon gap
6. integration gap
7. cost / maintenance gap
8. governance / safety gap
9. adoption gap
10. knowledge transfer gap

### 10.3 禁止事項

以下は problem_candidate として不十分または禁止とする。

* 本文の言い換えだけで終わるもの
* 一般論の焼き直し
* 根拠に接続しない断定
* 目新しさだけを狙った飛躍
* 背景文脈を無視した思いつき
* 何が課題か不明瞭な美文
* 単なる感想や好みの表明
* 解決策まで混ぜ込んだ肥大化問題定義

## 11. 仮説生成と飛躍の規約

### 11.1 基本方針

Insight Agent は、根拠不足の箇所について仮説を生成してよい。
ただし、仮説は事実と混同せず、明示的に hypothesis として扱う。

ここでいう飛躍は自由連想ではなく、制約付き推論である。
observation / assumption / limitation / 背景知識を接続し、未記述の問題候補または検証可能仮説を構成することを指す。

### 11.2 仮説を生成してよい場面

* limitation が明示されていないが、暗黙前提から破綻可能性が見える
* 評価不足により未検証の重要領域が存在する
* 背景知識と照合して見落としが推定できる
* 実装、運用、保守、継続利用における抜けが推定できる
* 単体成功が全体成功を保証しないと判断できる
* 条件が本文で過度に理想化されている
* 他資料との比較で説明されていない差分がある

### 11.3 仮説の制約

* どの claim / assumption / limitation から導いたか説明できる
* evidence または contrastive reference を持つ
* 検証可能である
* open_question と区別される
* 誇張しすぎない
* 飛躍が大きい場合は confidence を下げる
* 根拠が薄い場合は open_question に逃がす
* vision を hypothesis として偽装しない

### 11.4 仮説の優先型

* 条件破綻仮説
* 運用移植仮説
* 評価漏れ仮説
* 時間軸仮説
* 統合仮説
* スケール仮説
* 採用仮説

### 11.5 許容される飛躍

* 同一テーマ内での文脈拡張
* 過去知見との比較による欠落推定
* 評価軸の置き換え
* 短期成功から長期リスクの推定
* 個別最適から全体最適への再解釈
* 類似ドメインとの構造比較
* limitation の不在自体をリスクシグナルとして読むこと

### 11.6 許容しない飛躍

* 根拠ゼロの大胆仮説
* 単なる新奇性狙い
* ドメイン外への無制限な類推
* 検証不能な物語化
* 仮説ではなく断言へのすり替え
* 複数飛躍を無注釈でまとめること

## 12. confidence 規約

### 12.1 定義

confidence は、出力がどの程度安定した根拠と整合性を持つかを示す指標である。
真偽保証ではなく、根拠密度・整合性・飛躍の大きさ・反証可能性・競合解釈の少なさを総合して付与する。

### 12.2 形式

confidence は `0.00` から `1.00` の実数で表す。

表示帯域は以下とする。

* `high`: 0.75 以上
* `medium`: 0.45 以上 0.75 未満
* `low`: 0.45 未満

### 12.3 基本算定要素

* evidence の直接性
* evidence 数と一貫性
* claim / assumption / limitation との接続明瞭性
* 飛躍段数
* 競合解釈の数
* 反証条件の明瞭性
* persona 間評価の一致度

### 12.4 mode ごとの初期帯域

* `observation`: 0.80 - 0.98
* `interpretation`: 0.60 - 0.85
* `hypothesis`: 0.35 - 0.75
* `scenario`: 0.25 - 0.65
* `vision`: 0.20 - 0.55
* `open_question`: 0.10 - 0.40

### 12.5 運用ルール

* `high` でも hypothesis は observation にならない
* `low` でも探索価値が高ければ reserve 可能
* `low` の hypothesis は open_question への変換候補として再確認する
* confidence のみで採否を決めず、fatal_risk と persona 評価を併用する

## 13. Persona-based Evaluation

### 13.1 基本方針

候補は単なる好みではなく、定義済み persona の価値関数に従って評価する。
persona はキャラクターではなく、目的、制約、時間軸、リスク許容度、根拠選好を持つ評価レンズである。

### 13.2 必須属性

各 persona は最低限以下を持つ。

* `persona_id`
* `name`
* `objective`
* `priorities`
* `penalties`
* `time_horizon`
* `risk_tolerance`
* `evidence_preference`
* `acceptance_rule`

### 13.3 共通評価軸

* evidence_grounding
* novelty
* explanatory_power
* feasibility
* maintainability
* testability
* leverage
* robustness

必要に応じて以下を補助軸として追加してよい。

* cost_efficiency
* integration_readiness
* adoption_readiness
* long_term_durability
* safety_risk

### 13.4 標準 persona

#### researcher

研究価値、新規性、説明力、検証可能性を重視する。
unsupported_leap、triviality、曖昧問題定義を強く嫌う。

#### operator

実運用移植性、保守性、統合容易性、evidence grounding を重視する。
運用リスクや保守負債の見落としを強く嫌う。

#### strategist

波及効果、上位構造、長期耐久性、探索価値を重視する。
局所最適だけの指摘や downstream に接続しない課題を嫌う。

### 13.5 decision

候補の統合判断は以下を取る。

* `accept`
* `reserve`
* `reject`
* `needs_more_evidence`

### 13.6 persona conflict 解決

* `primary_persona` が指定されていればそれを優先する
* 指定がない場合は feasibility block を優先する
* operator が致命的 feasibility / maintainability 問題で reject した候補は、全体として reserve または reject に寄せる
* researcher のみ accept の場合は `research_only=true` として保持可能
* strategist のみ accept の場合は `visionary_or_long_horizon=true` を付けた reserve とする
* 全 persona が reserve / needs_more_evidence の場合は open_question 化を検討する

## 14. problem_candidate の基本スキーマ

各 `problem_candidate` は最低限以下を持つ。

* `problem_id`
* `statement`
* `problem_type`
* `scope`
* `epistemic_mode`
* `derivation_type`
* `confidence`
* `evidence_refs`
* `parent_refs`
* `assumption_refs`
* `limitation_refs`
* `support_signals`
* `failure_signals`
* `fatal_risks`
* `persona_scores`
* `decision`
* `update_rule`

### 14.1 `problem_type`

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

### 14.2 `scope`

* `local`
* `component`
* `system`
* `workflow`
* `organization`
* `ecosystem`

### 14.3 `derivation_type`

* `direct`
* `inferred`
* `contrastive`
* `contextual`

### 14.4 `update_rule`

* `retain`
* `revise`
* `discard`
* `branch`

## 15. insight 生成規約

### 15.1 目的

insight は problem_candidate を束ねた上位気づきである。
単なる総評ではなく、「何が本質的ボトルネックか」を示す必要がある。

### 15.2 生成条件

以下のいずれかを満たす場合に生成してよい。

* 複数の problem_candidate に共通構造がある
* 単一の強い problem_candidate を上位構造として再定式化できる
* 局所問題ではなく、評価、運用、統合、時間軸の上位制約を示せる
* 後続の Roadmap Agent がテーマとして扱える
* 本質的制約が明確である

### 15.3 禁止事項

* 単なる要約
* 候補の羅列
* 総花的な感想
* どこが本質か不明瞭な美文
* 根拠接続のない思想化

## 16. open_question の扱い

open_question は未完成の失敗物ではなく、未閉鎖の重要論点として保持する。

各 open_question は少なくとも以下を持つ。

* `question_id`
* `created_at`
* `review_after`
* `promotion_condition`
* `closure_condition`
* `status`

`status` は以下を取る。

* `open`
* `promoted`
* `closed`
* `stale`

`stale` は、`review_after` を過ぎても再評価されず、promotion_condition と closure_condition のいずれも満たしていない状態を指す。
stale となった open_question は、自動採用も自動棄却もせず、次回レビュー時に `closed` / `promoted` / `open` のいずれかへ再分類する。

`closed` の条件は以下のいずれかとする。

* 必要な検証により十分に解消された
* より上位の insight または hypothesis に吸収された
* 前提問題設定自体が無効化された
* 後続優先度が著しく低く、探索対象から外された

## 17. 失敗時の扱い

Insight Agent は失敗を捨てない。
十分な課題候補を生成できなかった場合でも、以下を構造化して返す。

* どの工程で詰まったか
* 何が不足しているか
* hypothesis に閉じるには何が足りなかったか
* open_question として残すべきか
* 追加資料または追加文脈が必要か

status は以下を取る。

* `completed`
* `partial`
* `failed`

`failed` は価値ゼロではなく、再試行可能な failure context を残した状態とみなす。

## 18. 非機能要件

* CLI / API / MCP は薄いラッパーにする
* 業務ロジックは `insight_core` に集約する
* 複数 source を非同期処理できる
* `run_id` 単位で状態追跡できる
* 同じ入力で極端にぶれない
* 不確実な場合は confidence を下げ、open_question を増やす
* 主要出力は evidence_ref を持つ
* 出典不明の断定を避ける
* 出力は後続の Roadmap Agent や保存層にそのまま渡せること

## 19. 品質基準

Insight Agent の出力は、以下を満たすほど高品質とみなす。

* claim と assumption が分離されている
* limitation が抽出されている
* problem_candidate が要約に終わっていない
* epistemic_mode が適切に付与されている
* hypothesis が support / failure の観点を持つ
* open_question が断定回避の逃がし先として機能している
* persona-based evaluation により採用理由が説明できる
* insight が上位構造を示している
* evidence_refs が主要出力に付いている
* confidence が mode と整合している

## 20. MVP 定義

### MVP-1

* 単一資料入力
* claim / assumption / limitation 抽出
* problem_candidate 3 件以内生成
* JSON 出力
* confidence 付与
* persona-based evaluation を最低限通す

### MVP-2

* 複数資料入力
* unit 分解
* insight / open_question 追加
* candidate ごとのメタデータ充実

### MVP-3

* 非同期バッチ
* CLI / API / MCP 共通コア化
* scenario / vision の整理強化
* failure context の再利用強化

## 21. 実装上の最低指針

MVP 段階では以下を優先する。

* Epistemic mode の誤分類を避ける
* problem_candidate を本文の言い換えで終わらせない
* hypothesis を過剰に膨らませない
* open_question を適切に使う
* persona-based evaluation を必ず通す
* confidence を必ず付与する
* insight を総評文にしない

MVP 段階では以下は後回しでよい。

* persona の過度な細分化
* 10 軸以上の複雑な評価関数
* 長大な scenario 展開
* vision の高度な最適化
* 自律的な深掘りループ

## 22. 結論

Insight Agent は、要約機ではなく、根拠に anchored された課題発見専用コアとして設計する。
そのために、以下の5本柱を持つ。

* Epistemic Mode Policy
* Discovery Policy
* Hypothesis and Leap Policy
* Confidence Policy
* Persona-based Evaluation Policy

この5本柱により、Insight Agent は「何が書いてあるか」を超えて、「どこが課題か」「何が抜けているか」「何を後続工程へ渡すべきか」を構造化して返す。

```

このまま次に `interfaces.md` に落とせる粒度です。
```
