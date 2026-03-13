# Insight Agent

論文・技術資料・設計資料を `InsightRequest` に正規化し、課題候補・洞察・未解決論点を `output_schema_v2` で返す課題発見エンジンです。CLI と Python API はどちらも同じ canonical runner `run()` を通ります。

## 何ができるか

- 主張・前提・制約の抽出
- persona ベースの多角評価
- problem / risk / insight / open question の構造化
- PDF / JSON / text を同じ内部契約へ正規化
- Config 駆動の provider / timeout / routing / output 制御

## 最短導線

### インストール

```bash
cd insight-agent
pip install -e .
```

### 環境変数

`.env` の最低限は次だけです。

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-xxx
OPENROUTER_API_MODEL=openrouter/hunter-alpha
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
LLM_RETRY_BACKOFF_SECONDS=0.5
```

複数 provider を使う場合は `LLM_PROVIDER_SEQUENCE=openrouter,openai,alibaba` を使います。

### CLI

```bash
python -m insight_core.cli run --pdf material/sample.pdf -o output.json
python -m insight_core.cli run -i examples/sample_request.json
python -m insight_core.cli run --text notes.txt --set llm.timeout_seconds=90
python -m insight_core.cli run --pdf material/sample.pdf --config config/runtime.example.yaml
```

後方互換のため `python -m insight_core.cli --pdf ...` も引き続き動きますが、公開入口は `run` です。

### Python API

```python
from insight_core import InsightRequest, RuntimeConfig, Source, run

request = InsightRequest(
    mode="insight",
    request_id="req_demo_001",
    sources=[
        Source(
            source_id="src_001",
            source_type="text",
            title="Demo",
            content="解析したい本文...",
        )
    ],
)

config = RuntimeConfig.model_validate({
    "llm": {
        "provider_sequence": ["openrouter", "openai"],
        "timeout_seconds": 60,
    },
    "pipeline": {
        "limits": {
            "max_problem_candidates": 5,
            "max_insights": 3,
        }
    },
    "output": {
        "format": "result",
    },
})

result = run(request=request, config=config)
```

`run(request_dict=payload, config_dict=cfg)` のような dict ベース呼び出しも使えます。既存の `run_pipeline_result()` / `run_insight_result()` は互換 wrapper です。

## 設計の芯

### 1. 公開入口は 1 つ

- 正規 API: `run()`
- CLI: `insight_core.cli run`
- どちらも同じ pipeline を通る

### 2. 挙動変更は Config で行う

- provider / provider sequence
- timeout / retry
- stage token limits
- output format
- routing / persona primary
- pipeline limits

### 3. 入力契約は `InsightRequest`

外部入力が JSON / PDF / text でも、内部では常に `InsightRequest` に正規化されます。

### 4. 既定出力は `output_schema_v2`

`raw` はデバッグ用です。CLI / API の既定返却、README の例、比較対象は `output_schema_v2` に揃えています。

## Config

設定の優先順位は次のとおりです。

1. デフォルト設定
2. config file
3. 環境変数
4. CLI `--set` / API override
5. request 内 `config_override`

### 例

```yaml
llm:
  provider_sequence:
    - openrouter
    - openai
  timeout_seconds: 60
  max_retries: 2
  retry_backoff_seconds: 0.5

pipeline:
  routing:
    enabled: true
    primary_persona: bright_generalist
    auto_select_personas: true
  limits:
    max_problem_candidates: 5
    max_insights: 3
    max_concurrency: 4

output:
  format: result
  include_source_units: false
  include_debug: false
  include_intermediate_items: false

runtime:
  log_level: INFO
  fail_fast: false
```

`LLM_MAX_TOKENS_ROUTING` / `EXTRACTION` / `DISCOVERY` / `EVALUATION` / `CONSOLIDATION` / `SUMMARY` で stage 別 token cap も調整できます。

## CLI の責務

CLI は薄い adapter に留めています。

- 入力の受け取り
- config file / env / `--set` のマージ
- 実行中表示
- 結果の保存または stdout 出力

pipeline の細かい挙動は config で制御します。

## 入力と loader

### 対応入力

- JSON: `-i input.json`
- PDF: `--pdf paper.pdf`
- text: `--text note.txt`

PDF は抽出テキストを同じ場所に `.txt` キャッシュします。次回以降はキャッシュを再利用するため、リトライや比較実行が軽くなります。

## 出力

既定返却は `output_schema_v2` です。主要フィールドは次のとおりです。

- `run`
- `nodes`
- `problems`
- `risk_notes`
- `insights`
- `open_questions`
- `evidence_refs`
- `reasoning_summary`

`raw` が必要なときだけ `--output-format raw` または `run(..., output_format="raw")` を使います。

## Persona / Routing

persona は config と routing で扱います。

- 通常運用: 自動選択
- 必要時: `pipeline.routing.primary_persona` で主担当を固定
- 詳細確認: `raw` 出力の routing 情報を見る

通常利用では persona を毎回手で指定しなくてよい構造にしています。

## Skills

この repo には LLM 作業者向けの repo-local skill を追加しています。

- `skills/codex/SKILL.md`: Codex 向けの作業入口、推奨コマンド、確認観点
- `skills/claude/SKILL.md`: Claude 向けの読み方、変更方針、検証手順

どちらも「まず何を読むか」「どの入口を使うか」「何を壊しやすいか」を短くまとめた onboarding 用です。

## ルート構成

```text
insight-agent/
  config/           設定と persona / routing 定義
  docs/src/         要件、設計メモ、schema
  examples/         最小入力例と設定例
  insight_core/     実装本体
  material/         入力サンプルと PDF 抽出キャッシュ
  artifacts/        実行結果、ベンチマーク、比較出力
  scripts/manual/   手動確認用スクリプト
  skills/           Claude / Codex 向け repo-local skill
  tests/            自動テスト
```

## 開発メモ

- 公開 API の本命は `run()`
- `run_pipeline_result()` / `run_insight_result()` は互換 wrapper
- 新しい入力形式を足すときは CLI ではなく loader 層へ追加する
- 新しい出力形式を足すときは pipeline 本体ではなく formatter 側へ追加する

## テスト

```bash
python -m pytest -q
python -m insight_core.cli run --help
```

## リリース

- changelog: [CHANGELOG.md](C:/Users/ryo-n/Codex_dev/insight-agent/CHANGELOG.md)
- release note: [docs/releases/v0.1.0.md](C:/Users/ryo-n/Codex_dev/insight-agent/docs/releases/v0.1.0.md)

## ライセンス

MIT License
