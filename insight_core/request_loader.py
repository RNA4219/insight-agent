from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from insight_core.schemas import Constraints, Context, InsightRequest, Options, PersonaDefinition, Source
from insight_core.source_loader import resolve_source_content


def load_request_payload(
    *,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    request_dict: dict[str, Any] | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    if request_dict is not None:
        return request_dict
    provided = [value is not None for value in (input_path, pdf_path, text_path)]
    if sum(provided) != 1:
        raise ValueError("Specify exactly one of input_path, pdf_path, text_path, or request_dict")
    if input_path is not None:
        return json.loads(Path(input_path).read_text(encoding="utf-8"))
    if pdf_path is not None:
        path = Path(pdf_path)
        return {
            "mode": "insight",
            "request_id": request_id,
            "sources": [{
                "source_id": source_id or path.stem,
                "source_type": "pdf",
                "title": title or path.stem,
                "path": str(path),
            }],
            "constraints": {},
            "options": {},
        }
    path = Path(text_path)
    return {
        "mode": "insight",
        "request_id": request_id,
        "sources": [{
            "source_id": source_id or path.stem,
            "source_type": "text",
            "title": title or path.stem,
            "path": str(path),
        }],
        "constraints": {},
        "options": {},
    }


def build_request_from_payload(payload: dict[str, Any], *, option_overrides: dict[str, Any] | None = None, constraint_overrides: dict[str, Any] | None = None) -> InsightRequest:
    sources = []
    for source_data in payload.get("sources", []):
        content, resolved_title = resolve_source_content(source_data)
        sources.append(
            Source(
                source_id=source_data.get("source_id", f"src_{len(sources)+1}"),
                source_type=source_data.get("source_type", "text"),
                title=resolved_title,
                content=content,
                metadata=source_data.get("metadata"),
            )
        )
    personas = [PersonaDefinition(**persona) for persona in payload.get("personas", [])] or None
    constraints_data = dict(payload.get("constraints", {}))
    constraints_data.update(constraint_overrides or {})
    constraints = Constraints(**constraints_data) if constraints_data else None
    context = Context(**payload["context"]) if payload.get("context") else None
    options_data = dict(payload.get("options", {}))
    options_data.update(option_overrides or {})
    options = Options(**options_data) if options_data else None
    return InsightRequest(
        mode=payload.get("mode", "insight"),
        request_id=payload.get("request_id"),
        sources=sources,
        constraints=constraints,
        personas=personas,
        context=context,
        options=options,
    )


def load_request(
    *,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    request_dict: dict[str, Any] | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
    option_overrides: dict[str, Any] | None = None,
    constraint_overrides: dict[str, Any] | None = None,
) -> tuple[InsightRequest, dict[str, Any]]:
    payload = load_request_payload(
        input_path=input_path,
        pdf_path=pdf_path,
        text_path=text_path,
        request_dict=request_dict,
        source_id=source_id,
        title=title,
        request_id=request_id,
    )
    return build_request_from_payload(payload, option_overrides=option_overrides, constraint_overrides=constraint_overrides), payload
