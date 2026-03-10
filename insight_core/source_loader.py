"""Source loading helpers for Insight Agent."""

from __future__ import annotations

from pathlib import Path

try:
    import fitz
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    fitz = None


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract plain text from a PDF file."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required to read PDF files")

    doc = fitz.open(path)
    page_texts: list[str] = []
    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text:
            continue
        page_texts.append(f"[Page {page_index}]\n{text}")

    if not page_texts:
        raise ValueError(f"No extractable text found in PDF: {path}")

    return "\n\n".join(page_texts)


def resolve_source_content(source_data: dict) -> tuple[str, str | None]:
    """Resolve source content and title from inline text or file-backed payload."""
    source_type = source_data.get("source_type", "text")
    title = source_data.get("title")

    if source_data.get("content"):
        return source_data["content"], title

    source_path = source_data.get("path") or source_data.get("file_path")
    if not source_path:
        raise ValueError("Source must provide either 'content' or 'path'")

    path = Path(source_path)
    if source_type == "pdf" or path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path), title or path.stem

    content = path.read_text(encoding="utf-8")
    return content, title or path.stem
