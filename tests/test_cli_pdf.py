from argparse import Namespace

from insight_core.cli import build_pdf_input_payload, build_request_from_dict, main


class TestPdfCliSupport:
    def test_build_request_from_pdf_source_path(self, monkeypatch, tmp_path):
        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        monkeypatch.setattr(
            "insight_core.request_loader.resolve_source_content",
            lambda payload: ("Extracted PDF text", payload.get("title") or "sample"),
        )

        args = Namespace(
            domain="machine_learning",
            include_source_units=False,
            checkpoint_path=None,
            resume=False,
            max_concurrency=6,
            request_id="req_pdf_001",
            source_id=None,
            title=None,
            japanese_summary=False,
        )
        payload = build_pdf_input_payload(pdf_path, args)

        request = build_request_from_dict(payload, args)

        assert request.request_id == "req_pdf_001"
        assert request.sources[0].source_type == "pdf"
        assert request.sources[0].title == "sample"
        assert request.sources[0].content == "Extracted PDF text"
        assert request.constraints.domain == "machine_learning"
        assert request.options.max_concurrency == 6

    def test_main_accepts_legacy_runless_invocation(self, monkeypatch, tmp_path, capsys):
        text_path = tmp_path / "sample.txt"
        text_path.write_text("hello", encoding="utf-8")

        monkeypatch.setattr('insight_core.cli.run', lambda **kwargs: {'version': 'output_schema_v2'})

        exit_code = main(['--text', str(text_path)])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert 'output_schema_v2' in captured.out
