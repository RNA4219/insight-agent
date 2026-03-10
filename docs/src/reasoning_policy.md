# Insight Agent Reasoning Policy

## 1. 文書の役割

本書は Insight Agent の推論規約を定義する。
目的は、課題発見の品質を一定に保ち、要約への退化と無根拠な飛躍の両方を防ぐことである。

## 2. 基本原則

* 課題発見は要約より優先する
* すべての主要生成物は evidence に接続する
* 断定よりも epistemic labeling を優先する
* 根拠不足の論点は open question に逃がす
* hypothesis は制約付き推論としてのみ許可する
* persona 数が増えても統合判断は決定的で再現可能でなければならない

## 3. Epistemic Mode

### 3.1 observation

入力資料または明示的な外部知識から直接確認できる事実。

### 3.2 interpretation

observation を整理、再表現、要約したもの。

### 3.3 hypothesis

observation / interpretation / 背景知識から導かれる検証可能な説明または破綻予測。

### 3.4 scenario

複数 hypothesis の関係を束ねた構造的または時系列的展開。

### 3.5 vision

長期方向性や探索価値を示す意味づけ。
反証可能性は必須ではない。

### 3.6 open_question

重要だが、現時点では閉じるべきでない問い。

## 4. Mode 昇格規約

### 4.1 interpretation から hypothesis への昇格条件

* どの evidence から導いたか説明できる
* 依拠する claim / assumption / limitation を示せる
* 何が観測されれば支持されるか述べられる
* 何が観測されれば崩れるか述べられる
* 単なる感想や総評ではない

### 4.2 hypothesis から scenario への昇格条件

* 複数 hypothesis 間の関係が明示されている
* 因果または時系列の接続が説明されている
* 単独仮説ではなく展開候補として意味がある

### 4.3 禁止事項

* 反証可能性のない表現を hypothesis にしない
* vision を hypothesis に偽装しない
* open question を無理に hypothesis に閉じない

## 5. Discovery Policy

problem candidate は、以下のいずれかに該当する場合に生成してよい。

* 主張の成立条件が狭い
* 暗黙前提が実運用で破綻しうる
* limitation が未記述または過小評価されている
* 評価指標が本質的問題を捉えていない
* 研究条件では成立しても継続運用に落ちない
* スケール、コスト、保守、統合の観点が欠落している
* 他知識や過去事例との照合で矛盾や空白がある
* 局所問題の背後に、より本質的な構造問題がある

## 6. Hypothesis and Leap Policy

### 6.1 仮説を生成してよい場面

* 暗黙前提から破綻可能性が見える
* 評価不足により未検証の重要領域がある
* 背景知識との照合で見落としが推定できる
* 実装、運用、保守、継続利用の抜けが推定できる
* 単体成功が全体成功を保証しないと判断できる

### 6.2 仮説の制約

* claim / assumption / limitation のどれから導いたか説明できる
* evidence または contrastive reference を持つ
* 検証可能である
* open question と区別される
* 飛躍が大きい場合は confidence を下げる
* 根拠が薄い場合は open question に逃がす

### 6.3 許容される飛躍

* 同一テーマ内での文脈拡張
* 過去知見との比較による欠落推定
* 評価軸の置き換え
* 短期成功から長期リスクの推定
* 個別最適から全体最適への再解釈

### 6.4 許容しない飛躍

* 根拠ゼロの大胆仮説
* 検証不能な物語化
* 無制限なドメイン外類推
* 仮説ではなく断言へのすり替え

## 7. Confidence Policy

### 7.1 定義

confidence は真偽保証ではなく、根拠密度、整合性、飛躍の大きさ、反証可能性、競合解釈の少なさを総合した安定度指標である。

### 7.2 形式

* `0.00` から `1.00` の実数を取る
* `high`: 0.75 以上
* `medium`: 0.45 以上 0.75 未満
* `low`: 0.45 未満

### 7.3 算定要素

* evidence の直接性
* evidence 数と一貫性
* claim / assumption / limitation との接続明瞭性
* 飛躍段数
* 競合解釈の数
* 反証条件の明瞭性
* persona 間評価の一致度

### 7.4 mode ごとの初期帯域

* `observation`: 0.80 - 0.98
* `interpretation`: 0.60 - 0.85
* `hypothesis`: 0.35 - 0.75
* `scenario`: 0.25 - 0.65
* `vision`: 0.20 - 0.55
* `open_question`: 0.10 - 0.40

## 8. Persona-based Evaluation Policy

### 8.1 標準 persona

* `bright_generalist`: 万能で明るい性格。広い観点から可能性、親しみやすさ、前向きな活用余地を拾う
* `data_researcher`: データ分析が得意な研究者型。根拠密度、検証可能性、再現性、評価設計を重視する
* `curiosity_entertainer`: 人間の感じる面白さを探求するトーク芸人型。新奇性、語れる切り口、驚き、共有したくなる価値を重視する
* `researcher`: 研究価値、新規性、説明力、検証可能性を重視する
* `operator`: 実運用移植性、保守性、統合容易性を重視する
* `strategist`: 波及効果、上位構造、長期耐久性、探索価値を重視する

### 8.2 persona 定義の拡張方針

* persona はハードコードではなく JSON 定義で追加可能とする
* 人数にハード上限は設けないが、`persona_id` の重複は不正とする
* `weight` は正の数とし、統合時には正規化して扱う
* 実行時は request の `personas[]` が優先され、未指定時は標準 6 persona セットをロードする
* 評価順序は `personas[]` の配列順を正とし、未指定時は標準セット順を正とする

### 8.3 共通評価軸

* evidence_grounding
* novelty
* explanatory_power
* feasibility
* maintainability
* testability
* leverage
* robustness

### 8.4 decision

統合判断は以下を用いる。

* `accept`
* `reserve`
* `reject`
* `needs_more_evidence`

### 8.5 conflict 解決

* `primary_persona` があれば最終タイブレークに使う
* `data_researcher` または `operator` が致命的な feasibility / evidence grounding / maintainability 問題で reject した候補は reserve または reject に寄せる
* それ以外は正規化済み `weight` による重み付き多数決を基本とする
* 重み付き結果が同率なら、評価順序の先頭側の persona 判断を優先する
* 全 persona が reserve / needs_more_evidence の場合は open question 化を検討する

## 9. Insight Policy

insight は problem candidate の要約ではなく、上位構造の再定式化でなければならない。

生成条件は以下とする。

* 複数候補に共通構造がある
* 単一強候補を上位制約として再定式化できる
* 後続の Roadmap Agent がテーマとして扱える

禁止事項は以下とする。

* 単なる総評
* 候補の羅列
* 根拠接続のない思想化

## 10. Open Question Policy

open question は失敗物ではなく、未閉鎖の重要論点として保持する。

* hypothesis に閉じるには根拠が足りないときに使う
* `promotion_condition` と `closure_condition` を必須とする
* `review_after` を持たせ、再評価可能にする
* stale 化しても自動採用や自動棄却はしない

## 11. Failure Policy

Insight Agent は十分な候補を生成できなかった場合でも、失敗を破棄してはならない。

最低限、以下を構造化して返す。

* どの工程で詰まったか
* 何が不足しているか
* hypothesis に閉じるには何が足りなかったか
* 追加資料または追加文脈が必要か

## 12. 実装上の運用ガード

* `epistemic_mode` の誤分類を避ける
* problem candidate を要約文にしない
* hypothesis を過剰に膨らませない
* open question を断定回避の逃がし先として使う
* confidence の高さだけで採否を決めない
* 同一 persona セットと同一入力では `applied_personas` と最終 decision が再現すること
