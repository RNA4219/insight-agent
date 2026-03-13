from pathlib import Path

import insight_core.source_loader as source_loader


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def get_text(self, mode: str) -> str:
        assert mode == "text"
        return self._text


class _FakeDoc:
    def __init__(self, pages: list[_FakePage]):
        self._pages = pages

    def __iter__(self):
        return iter(self._pages)


def test_extract_text_from_pdf_writes_cache(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        source_loader,
        "fitz",
        type("_FakeFitz", (), {"open": staticmethod(lambda path: _FakeDoc([_FakePage("Alpha"), _FakePage("Beta")]))}),
    )

    text = source_loader.extract_text_from_pdf(pdf_path)

    cache_path = pdf_path.with_suffix(".txt")
    assert text == "[Page 1]\nAlpha\n\n[Page 2]\nBeta"
    assert cache_path.exists()
    assert cache_path.read_text(encoding="utf-8") == text


def test_extract_text_from_pdf_reuses_cache_when_newer(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    cache_path = pdf_path.with_suffix(".txt")
    cache_path.write_text("cached text", encoding="utf-8")

    original_stat = Path.stat

    def fake_stat(path_obj: Path):
        stat_result = original_stat(path_obj)
        if path_obj == pdf_path:
            return stat_result.__class__((stat_result.st_mode, stat_result.st_ino, stat_result.st_dev, stat_result.st_nlink, stat_result.st_uid, stat_result.st_gid, stat_result.st_size, stat_result.st_atime, stat_result.st_mtime - 10, stat_result.st_ctime))
        return stat_result

    monkeypatch.setattr(Path, "stat", fake_stat)

    def fail_open(_path):
        raise AssertionError("fitz.open should not be called when cache is fresh")

    monkeypatch.setattr(source_loader, "fitz", type("_FakeFitz", (), {"open": staticmethod(fail_open)}))

    text = source_loader.extract_text_from_pdf(pdf_path)

    assert text == "cached text"
