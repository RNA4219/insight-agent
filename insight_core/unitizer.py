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


def detect_section_boundaries(content: str) -> list[dict[str, Any]]:
    """Detect section boundaries in content.

    Looks for markdown-style headers and natural paragraph breaks.

    Args:
        content: The source content to analyze.

    Returns:
        List of boundary info dicts with 'type', 'level', 'start', 'end', 'title'.
    """
    boundaries = []
    lines = content.split("\n")

    current_pos = 0
    for i, line in enumerate(lines):
        line_len = len(line) + 1  # +1 for newline

        # Markdown headers (# Header)
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
    """Split content by paragraphs with size limit.

    Args:
        content: Content to split.
        max_chars: Maximum characters per unit.

    Returns:
        List of content chunks.
    """
    paragraphs = re.split(r"\n\s*\n", content)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If single paragraph exceeds max, split by sentences
        if len(para) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split by sentences
            sentences = re.split(r"(?<=[.!?。！？])\s+", para)
            for sent in sentences:
                if len(current_chunk) + len(sent) > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sent
                else:
                    current_chunk += " " + sent if current_chunk else sent
        else:
            # Add to current chunk
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def unitize_source(
    source: Source,
    max_chars: int = 2000,
) -> list[SourceUnit]:
    """Split a source into SourceUnits.

    Strategy:
    1. Try to detect section boundaries (markdown headers)
    2. Within each section, split by paragraphs
    3. Ensure each unit is under max_chars

    Args:
        source: The source to unitize.
        max_chars: Maximum characters per unit.

    Returns:
        List of SourceUnit objects.
    """
    units = []
    content = source.content

    if not content or not content.strip():
        return units

    # Detect section boundaries
    boundaries = detect_section_boundaries(content)

    if boundaries:
        # Split by sections
        lines = content.split("\n")
        section_starts = [b["line_index"] for b in boundaries]

        # Add end marker
        section_starts.append(len(lines))

        for i, boundary in enumerate(boundaries):
            start_line = boundary["line_index"]
            end_line = section_starts[i + 1]

            section_content = "\n".join(lines[start_line:end_line]).strip()

            if not section_content:
                continue

            # If section is too large, split further
            if len(section_content) > max_chars:
                chunks = split_by_paragraphs(section_content, max_chars)
                for j, chunk in enumerate(chunks):
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
        # No section boundaries, split by paragraphs
        chunks = split_by_paragraphs(content, max_chars)
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
    """Split multiple sources into SourceUnits.

    Args:
        sources: List of sources to unitize.
        max_chars: Maximum characters per unit.

    Returns:
        List of all SourceUnit objects.
    """
    all_units = []
    for source in sources:
        units = unitize_source(source, max_chars)
        all_units.extend(units)
    return all_units