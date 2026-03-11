# Insight Agent

論文・技術資料・設計資料などを読み取り、課題候補と高次の気づきを構造化して返す**課題発見専用コアエージェント**。

## 特徴

- 主張・前提・制約の抽出
- ギャップ・矛盾・欠落の検出
- Personaベースの多角的評価
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
# プロバイダー選択: openai / alibaba / openrouter
LLM_PROVIDER=openrouter

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

## 使い方

### Python API

#### 簡易API

```python
from insight_core import run_insight

response = run_insight(
    sources=[{
        "source_id": "src_001",
        "title": "Sample Paper",
        "content": "..."
    }],
    domain="machine_learning"  # オプション
)

# 結果を確認
print(f"Status: {response.run.status}")
print(f"Claims: {len(response.claims)}")
print(f"Problem Candidates: {len(response.problem_candidates)}")
```

#### 完全API

```python
from insight_core import run_pipeline, InsightRequest, Source, Constraints

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

response = run_pipeline(request)
```

#### カスタムPersona

```python
from insight_core import run_pipeline, InsightRequest, Source, PersonaDefinition

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

response = run_pipeline(request)
```

### CLI

#### 基本実行

```bash
python -m insight_core.cli -i input.json -o output.json
```

#### PDFを直接解析

```bash
python -m insight_core.cli --pdf material/sample.pdf -o output.json --domain machine_learning
```

#### ドメイン指定

```bash
python -m insight_core.cli -i input.json -o output.json --domain machine_learning
```

#### ソースユニットを含める

```bash
python -m insight_core.cli -i input.json -o output.json --include-source-units
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

```json
{
  "run": {
    "run_id": "run_xxx",
    "request_id": "example_001",
    "mode": "insight",
    "status": "completed",
    "started_at": "2026-03-10T12:00:00Z",
    "finished_at": "2026-03-10T12:00:30Z",
    "applied_personas": ["bright_generalist", "data_researcher", ...],
    "persona_source": "default",
    "persona_catalog_version": "default_personas.v3"
  },
  "claims": [...],
  "assumptions": [...],
  "limitations": [...],
  "problem_candidates": [
    {
      "id": "pb_001",
      "statement": "評価が短期ベンチマークに偏っている",
      "problem_type": "evaluation_gap",
      "scope": "system",
      "decision": "accept",
      "confidence": 0.72,
      "persona_scores": [...]
    }
  ],
  "insights": [...],
  "open_questions": [...],
  "evidence_refs": [...],
  "failures": [],
  "confidence": 0.78
}
```

## サンプルコマンド

### クイックスタート

```bash
# サンプル入力で実行
python -m insight_core.cli -i examples/sample_request.json

# 出力をファイルに保存
python -m insight_core.cli -i examples/sample_request.json -o results.json

# Pythonで直接実行
python -c "
from insight_core import run_insight
response = run_insight(
    sources=[{'source_id': 'test', 'content': 'Your text here...'}],
    domain='general'
)
print(response.model_dump_json(indent=2))
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

デフォルトで7種類のPersonaが適用されます。`default_personas.v3` では、各Personaに以下のような詳細設定が入っています。

- `key_questions`: そのPersonaが最初に確認する問い
- `evidence_requirements`: 判断に必要とする根拠
- `trigger_signals`: 呼び出す価値が高い状況
- `red_flags`: 強く警戒する兆候
- `optional_notes`: 口調・匿名性・安全ガードなどの補助メモ
- `synthesis_style`: 最終コメントのまとめ方

| Persona ID | 役割 | 重視点 |
|------------|------|--------|
| `bright_generalist` | 万能な探索者 | 波及効果、採用容易性 |
| `data_researcher` | データ分析研究者 | 根拠、検証可能性 |
| `curiosity_entertainer` | 面白さを探求 | 新規性、語りやすさ |
| `researcher` | 研究価値重視 | 新規性、説明力 |
| `operator` | 実運用重視 | 実現性、保守性 |
| `strategist` | 戦略的視点 | 長期波及、堅牢性 |
| `moon_gazer` | 監督AI視点 | 論点圧縮、境界管理、破綻検知 |

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

