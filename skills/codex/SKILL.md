# Codex Skill for insight-agent

## 目的

この repo で Codex が迷わず作業開始できるようにするための最小ガイドです。

## 最初に見る場所

1. `README.md`
2. `docs/src/output_schema_v2.json`
3. `insight_core/runner.py`
4. `insight_core/runtime_config.py`
5. `insight_core/request_loader.py`

## 正規入口

- API の本命は `run()`
- CLI の本命は `python -m insight_core.cli run ...`
- `run_pipeline_result()` / `run_insight_result()` は互換 wrapper

## 変更方針

- 入口を増やすより `run()` に寄せる
- 挙動差分は config で吸収する
- 入力形式差分は loader 層で吸収する
- 出力形式差分は formatter 層で吸収する
- 既定の外部契約は `output_schema_v2`

## 触るときの注意

- `insight_core/pipeline.py` は中核なので、責務追加は慎重に行う
- `insight_core/cli.py` は薄い adapter に保つ
- `insight_core/runtime_config.py` の優先順位は `default -> file -> env -> override -> request local`
- `raw` は debug 用なので外部契約の中心にしない

## よく使う確認

```bash
python -m pytest -q
python -m insight_core.cli run --help
python -m insight_core.cli run -i examples/sample_request.json
```

## 変更後チェック

- canonical runner を迂回していないか
- CLI / API の既定出力が `output_schema_v2` で一致しているか
- JSON / PDF / text のどれも `InsightRequest` に正規化されるか
- README の利用例が現状実装とズレていないか
