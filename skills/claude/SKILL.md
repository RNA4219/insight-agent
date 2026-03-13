# Claude Skill for insight-agent

## 目的

Claude がこの repo を読むときに、設計の芯と変更境界を短時間でつかめるようにするためのガイドです。

## まず理解すること

- この repo は課題発見エンジン
- 入力の正規化先は `InsightRequest`
- 実行の正規入口は `run()`
- 既定出力は `output_schema_v2`
- CLI と API は同じ canonical runner を通る

## 推奨読順

1. `README.md`
2. `docs/src/output_schema_v2.json`
3. `insight_core/schemas.py`
4. `insight_core/runner.py`
5. `insight_core/result_formatter.py`
6. `insight_core/pipeline.py`

## どこを直すべきか

- 入力の扱い: `insight_core/request_loader.py`
- 設定の優先順位: `insight_core/runtime_config.py`
- CLI の振る舞い: `insight_core/cli.py`
- 出力 contract: `insight_core/result_formatter.py`
- 実行フロー: `insight_core/pipeline.py`

## 変更の原則

- 新しいユーザー向け挙動は `run()` に集約する
- pipeline に I/O 都合の分岐を増やさない
- provider / timeout / routing の切り替えは config に寄せる
- 論文固有の補正は formatter 側に閉じ込める

## 検証

```bash
python -m pytest -q
python -m insight_core.cli run --help
python -m insight_core.cli run --text material/6296_Support_Vector_Generation.txt
```

## レビュー観点

- wrapper が本体扱いになっていないか
- README と実装の入口が一致しているか
- ルート直下に生成物や補助スクリプトが散らかっていないか
- `artifacts/`, `examples/`, `scripts/manual/`, `skills/` の役割が保たれているか
