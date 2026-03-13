# Insight Agent

論文・技術資料・設計資料などを読み取り、課題候補と高次の気づきを構造化して返す**課題発見専用コアエージェント**。

## 特徴

- 主張・前提・制約の抽出
- ギャップ・矛盾・欠落の検出
- Personaベースの多角的評価
- Personaの obsession / blind spot を Discovery・Evaluator・Consolidator に反映
- 構造化JSON出力

## セットアップ

### 1. 依存関係のインストール

```bash
cd insight-agent
pip install -e .
```

### 2. 環境変数の設定

`.env`ファイルをプロジェクトルートに作成：

```env
# 単一プロバイダ
LLM_PROVIDER=openrouter

# 複数プロバイダ failover / round-robin
# LLM_PROVIDER_SEQUENCE=openai,openrouter,alibaba
# LLM_PROVIDER_SEQUENCE が設定されている場合は LLM_PROVIDER より優先されます

# OpenAI使用時
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-5-mini-2025-08-07

# OpenRouter使用時
OPENROUTER_API_KEY=sk-or-xxx
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Alibaba (DashScope) 使用時
DASHSCOPE_API_KEY=sk-xxx
ALIBABA_MODEL=glm-5
ALIBABA_BASE_URL=https://coding-intl.dashscope.aliyuncs.com/v1
```

`LLM_PROVIDER_SEQUENCE` を使うと、呼び出しごとに開始プロバイダをずらしつつ、失敗時は次のプロバイダへ順に切り替えます。単一プロバイダで同じモデルを連打して詰まるケースの緩和を狙った設定です。

加えて、各 stage で出力トークン上限を個別に絞れます。たとえば extraction は短い JSON だけ返せばよいので `LLM_MAX_TOKENS_EXTRACTION=900` のように小さめに設定できます。使える環境変数は `LLM_MAX_TOKENS_ROUTING` / `EXTRACTION` / `DISCOVERY` / `EVALUATION` / `CONSOLIDATION` / `SUMMARY` です。

長文入力で待ち時間が重い場合は、既定の `LLM_TIMEOUT_SECONDS=60` を起点に `LLM_TIMEOUT_SECONDS` または provider 個別の `OPENAI_TIMEOUT_SECONDS` / `OPENROUTER_TIMEOUT_SECONDS` / `ALIBABA_TIMEOUT_SECONDS` と、`LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF_SECONDS` で retry 挙動も調整できます。

## 使い方

### Python API

#### 簡易API

```python
from insight_core import run_insight_result

result = run_insight_result(
    sources=[{
        "source_id": "src_001",
        "title": "Sample Paper",
        "content": "..."
    }],
    domain="machine_learning"  # オプション
)

print(result.summary.reasoning)
print(result.model_dump_json(indent=2))
```

#### 完全API

```python
from insight_core import run_pipeline_result, InsightRequest, Source, Constraints

request = InsightRequest(
    mode="insight",
    request_id="my_request_001",
    sources=[
        Source(
            source_id="src_001",
            source_type="text",
            title="My Document",
            content="解析したいテキスト..."
        )
    ],
    constraints=Constraints(
        domain="machine_learning",
        max_problem_candidates=5,
        max_insights=3
    )
)

result = run_pipeline_result(request)
```

#### カスタムPersona

```python
from insight_core import run_pipeline_result, InsightRequest, Source, PersonaDefinition

custom_persona = PersonaDefinition(
    persona_id="security_auditor",
    name="Security Auditor",
    role="セキュリティ専門家",
    description="セキュリティリスクと脆弱性を重視",
    objective="セキュリティ上の問題を特定する",
    priorities=["robustness", "feasibility"],
    penalties=["security_risk", "data_exposure"],
    acceptance_rule="セキュリティリスクが許容範囲であること",
    weight=1.5
)

request = InsightRequest(
    mode="insight",
    sources=[Source(source_id="src_001", content="...")],
    personas=[custom_persona]
)

result = run_pipeline_result(request)
```

### CLI

CLI はデフォルトで `output_schema_v2` を返します。これは次段の生成AIが再調査・実験にそのまま進みやすいよう、`nodes / problems / risk_notes / insights / open_questions / reasoning_summary` を中心に薄くまとめた contract です。内部の詳細 schema が必要なときだけ `--output-format raw` を使います。

#### 基本実行

```bash
python -m insight_core.cli -i input.json -o output.json
```

#### PDFを直接解析

```bash
python -m insight_core.cli --pdf material/sample.pdf -o output.json --domain machine_learning
```

PDF を直接解析した場合、抽出したテキストは `material/sample.txt` のように PDF と同じ場所へ保存されます。次回以降はその `.txt` を再利用するため、リトライや比較実行が軽くなります。

#### ドメイン指定

```bash
python -m insight_core.cli -i input.json -o output.json --domain machine_learning
```

#### 内部 raw schema を出力する

```bash
python -m insight_core.cli -i input.json -o output.json --output-format raw
```

#### ソースユニットを含める

```bash
python -m insight_core.cli -i input.json -o output.json --output-format raw --include-source-units
```

## 入力フォーマット

`input.json`:

```json
{
  "mode": "insight",
  "request_id": "example_001",
  "sources": [
    {
      "source_id": "src_001",
      "source_type": "text",
      "title": "Sample Paper",
      "content": "解析対象のテキスト..."
    }
  ],
  "constraints": {
    "domain": "machine_learning",
    "max_problem_candidates": 5,
    "max_insights": 3
  },
  "options": {
    "include_source_units": false
  }
}
```

## 出力フォーマット

デフォルトの API / CLI 返却は `output_schema_v2` です。

```json
{
  "version": "output_schema_v2",
  "run": {
    "run_id": "run_xxx",
    "request_id": "example_001",
    "status": "partial"
  },
  "nodes": [
    {
      "id": "cl_001",
      "node_type": "claim",
      "statement": "SkillNet significantly enhances agent performance...",
      "epistemic_mode": "source_fact",
      "derivation_type": "quoted",
      "confidence": 0.94,
      "evidence_refs": ["ev_001"],
      "source_scope": "core_result",
      "update_rule": "retain"
    }
  ],
  "problems": [
    {
      "id": "pb_001",
      "statement": "SkillNet's benchmark gains are supported, but the deployment-level framing appears broader than the evaluated scope.",
      "epistemic_mode": "critique_hypothesis",
      "derivation_type": "inferred_near",
      "confidence": 0.74,
      "problem_type": "claim_scope_mismatch",
      "support_bundle": {
        "claim_ids": ["cl_001"],
        "assumption_ids": ["as_001"],
        "limitation_ids": ["lm_001"],
        "evidence_ids": ["ev_001", "ev_015"]
      },
      "evidence_sufficiency": {
        "status": "partial",
        "missing": ["real_world_eval"],
        "support_count": 2,
        "counter_count": 1
      },
      "decision": "needs_more_evidence",
      "next_checks": ["実世界相当タスクで再評価する", "主張の適用範囲を明文化する"]
    }
  ],
  "risk_notes": [
    {
      "id": "rk_pb_003",
      "statement": "実運用への外挿には責任分界と障害対応の追加設計が必要である。",
      "risk_type": "deployment_extrapolation",
      "next_checks": ["導入責任を定義する", "障害対応フローを設計する"]
    }
  ],
  "insights": [
    {
      "id": "ins_v2_001",
      "statement": "ベンチマーク上の性能改善は直接支持されている一方、主張の適用範囲は評価スコープより広い。",
      "epistemic_mode": "system_inference",
      "derivation_type": "summarized",
      "confidence": 0.76
    }
  ],
  "open_questions": [
    {
      "question_id": "oq_pb_001",
      "question_type": "validation_experiment",
      "statement": "実世界相当タスクで、ベンチマークと同等の改善率が再現されるか",
      "required_evidence_type": ["deployment_eval", "transfer_benchmark", "ablation"]
    }
  ],
  "evidence_refs": [
    {
      "evidence_id": "ev_001",
      "evidence_role": ["main_support", "evaluation_setup"],
      "strength": 0.94
    }
  ],
  "confidence": 0.78,
  "routing_plan": {},
  "reasoning_summary": {
    "headline": "ベンチマーク上の強い結果は支持されるが、主張の適用範囲には留保が必要。",
    "what_is_supported": ["40% reward improvement is directly supported."],
    "what_remains_open": ["Generalization beyond text-based simulated environments."],
    "recommended_reading": "accept_core_results_with_scope_caution"
  }
}
```

内部の詳細 schema が必要な場合は `run_pipeline()` / `run_insight()` または CLI の `--output-format raw` を使います。

## サンプルコマンド

### クイックスタート

```bash
# サンプル入力で実行
python -m insight_core.cli -i examples/sample_request.json

# 出力をファイルに保存
python -m insight_core.cli -i examples/sample_request.json -o results.json

# Pythonで直接実行
python -c "
from insight_core import run_insight_result
result = run_insight_result(
    sources=[{'source_id': 'test', 'content': 'Your text here...'}],
    domain='general'
)
print(result.model_dump_json(indent=2))
"
```

### テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# 特定のテストのみ
pytest tests/test_insight_agent.py::TestSchemas -v
```

## 標準Persona

デフォルトで8種類のPersonaが適用されます。`default_personas.v4` では、各Personaに以下のような詳細設定が入っています。

- `obsession`: そのPersonaが反応しやすい執着点
- `blind_spot`: そのPersonaが軽視しやすい盲点
- `key_questions`: そのPersonaが最初に確認する問い
- `evidence_requirements`: 判断に必要とする根拠
- `trigger_signals`: 前のめりになる兆候
- `red_flags`: 却下や保留に寄せる兆候
- `optional_notes`: 口調・安全ガード・判断姿勢の補助メモ
- `synthesis_style`: 最終コメントのまとめ癖

| Persona ID | 役割 | 重視点 |
|------------|------|--------|
| `bright_generalist` | 多面探索者 | 波及効果、トレードオフ整理 |
| `data_researcher` | 検証主義者 | 根拠、反証可能性 |
| `curiosity_entertainer` | 話題化演出家 | 新規性、伝播力 |
| `researcher` | 研究設計者 | 仮説、説明力 |
| `operator` | 現場番人 | 導入性、保守性 |
| `strategist` | 構造戦略家 | 長期波及、構造因 |
| `moon_gazer` | 監督AI視点 | 論点圧縮、境界管理、破綻検知 |
| `detective` | 矛盾追跡者 | 因果追跡、競合仮説、再検証 |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                      InsightRequest                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Request Normalizer (正規化・検証)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Unitizer (ソース分割)                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Extractor (Claim/Assumption/Limitation抽出)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Discovery (課題候補発見)                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Evaluator (Persona評価)                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Consolidator (Insight/OpenQuestion統合)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      InsightResponse                         │
└─────────────────────────────────────────────────────────────┘
```

## ライセンス

MIT License

