"""Unitizer module.

Responsible for:
- Splitting sources into SourceUnits
- Section / heading / paragraph boundary based splitting
- Assigning parent_source_id, unit_id, order_index
"""

from __future__ import annotations

import re
from typing import Any

from insight_core.schemas import Source, SourceUnit

PDF_MAX_CHARS = 5000


def detect_section_boundaries(content: str) -> list[dict[str, Any]]:
    """Detect section boundaries in content."""
    boundaries = []
    lines = content.split("\n")

    current_pos = 0
    for i, line in enumerate(lines):
        line_len = len(line) + 1
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            boundaries.append({
                "type": "header",
                "level": level,
                "start": current_pos,
                "line_index": i,
                "title": title,
            })

        current_pos += line_len

    return boundaries


def split_by_paragraphs(content: str, max_chars: int = 2000) -> list[str]:
    """Split content by paragraphs with size limit."""
    paragraphs = re.split(r"\n\s*\n", content)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            sentences = re.split(r"(?<=[.!?。！？])\s+", para)
            for sent in sentences:
                if len(current_chunk) + len(sent) > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sent
                else:
                    current_chunk += " " + sent if current_chunk else sent
        else:
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def _resolve_max_chars(source: Source, default_max_chars: int) -> int:
    if source.source_type == "pdf":
        return max(default_max_chars, PDF_MAX_CHARS)
    return default_max_chars


def unitize_source(
    source: Source,
    max_chars: int = 2000,
) -> list[SourceUnit]:
    """Split a source into SourceUnits."""
    units = []
    content = source.content
    source_max_chars = _resolve_max_chars(source, max_chars)

    if not content or not content.strip():
        return units

    boundaries = detect_section_boundaries(content)

    if boundaries:
        lines = content.split("\n")
        section_starts = [b["line_index"] for b in boundaries]
        section_starts.append(len(lines))

        for i, boundary in enumerate(boundaries):
            start_line = boundary["line_index"]
            end_line = section_starts[i + 1]
            section_content = "\n".join(lines[start_line:end_line]).strip()

            if not section_content:
                continue

            if len(section_content) > source_max_chars:
                chunks = split_by_paragraphs(section_content, source_max_chars)
                for chunk in chunks:
                    unit_id = f"unit_{source.source_id}_{len(units) + 1}"
                    units.append(
                        SourceUnit(
                            unit_id=unit_id,
                            parent_source_id=source.source_id,
                            section_path=[boundary.get("title", "")] if boundary.get("title") else [],
                            order_index=len(units),
                            content=chunk,
                            char_count=len(chunk),
                        )
                    )
            else:
                unit_id = f"unit_{source.source_id}_{len(units) + 1}"
                units.append(
                    SourceUnit(
                        unit_id=unit_id,
                        parent_source_id=source.source_id,
                        section_path=[boundary.get("title", "")] if boundary.get("title") else [],
                        order_index=len(units),
                        content=section_content,
                        char_count=len(section_content),
                    )
                )
    else:
        chunks = split_by_paragraphs(content, source_max_chars)
        for chunk in chunks:
            unit_id = f"unit_{source.source_id}_{len(units) + 1}"
            units.append(
                SourceUnit(
                    unit_id=unit_id,
                    parent_source_id=source.source_id,
                    section_path=[],
                    order_index=len(units),
                    content=chunk,
                    char_count=len(chunk),
                )
            )

    return units


def unitize_sources(
    sources: list[Source],
    max_chars: int = 2000,
) -> list[SourceUnit]:
    """Split multiple sources into SourceUnits."""
    all_units = []
    for source in sources:
        units = unitize_source(source, max_chars)
        all_units.extend(units)
    return all_units
