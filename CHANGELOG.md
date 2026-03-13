# Changelog

## v0.1.0

### Added
- 正規公開 API として `run()` / `run_async()` を追加
- `RuntimeConfig` と config merge ロジックを追加
- JSON / PDF / text を `InsightRequest` に正規化する loader を追加
- `output_schema_v2` formatter と release 向けの結果 contract を追加
- Claude / Codex 向けの repo-local skill を追加
- `examples/runtime.example.yaml` を追加

### Changed
- CLI の正規入口を `python -m insight_core.cli run ...` に整理
- CLI / API が同じ canonical runner を通る構成へ整理
- 既定出力を `output_schema_v2` に統一
- timeout / retry / stage token limit を config / env から調整できるように改善
- PDF 抽出結果を `.txt` キャッシュして再利用するように改善
- README を公開入口、Config、出力契約中心に再構成
- ルート直下の手動確認スクリプトとベンチマーク出力を整理

### Compatibility
- `run_pipeline_result()` / `run_insight_result()` は互換 wrapper として継続
- `python -m insight_core.cli --pdf ...` の旧形式も後方互換で継続

### Known limitations
- `raw` 出力は debug / internal 向けであり、外部契約の中心ではない
- 長い PDF や外部 provider の状態によっては実行時間が長くなる
- 一部の論文固有補正は formatter 側の postprocess で扱っている
