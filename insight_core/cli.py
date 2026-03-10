"""CLI entry point for Insight Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from insight_core.pipeline import run_pipeline
from insight_core.schemas import (
    Constraints,
    Context,
    InsightRequest,
    Options,
    PersonaDefinition,
    Source,
)
from insight_core.source_loader import resolve_source_content


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Insight Agent - A problem discovery core agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=None,
        help="Path to input JSON file (InsightRequest format)",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to a PDF file to analyze directly",
    )
    parser.add_argument(
        "--source-id",
        type=str,
        default=None,
        help="Source ID to use with --pdf",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Source title to use with --pdf",
    )
    parser.add_argument(
        "--request-id",
        type=str,
        default=None,
        help="Optional request ID override for direct PDF runs",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to output JSON file (default: stdout)",
    )
    parser.add_argument(
        "--include-source-units",
        action="store_true",
        help="Include source units in response",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Domain context for analysis",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=None,
        help="Checkpoint JSON path for saving intermediate progress",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint when available",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=None,
        help="Maximum concurrent LLM calls for extraction and evaluation",
    )
    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if bool(args.input) == bool(args.pdf):
        print("Error: specify exactly one of --input or --pdf", file=sys.stderr)
        return 1

    if args.input and not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    if args.pdf and not args.pdf.exists():
        print(f"Error: PDF file not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        if args.input:
            with open(args.input, encoding="utf-8") as f:
                input_data = json.load(f)
        else:
            input_data = build_pdf_input_payload(args.pdf, args)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading input: {e}", file=sys.stderr)
        return 1

    try:
        request = build_request_from_dict(input_data, args)
    except Exception as e:
        print(f"Error building request: {e}", file=sys.stderr)
        return 1

    try:
        response = run_pipeline(request)
    except Exception as e:
        print(f"Error running pipeline: {e}", file=sys.stderr)
        return 1

    output_json = response.model_dump_json(indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Response written to: {args.output}")
    else:
        print(output_json)

    return 0


def build_pdf_input_payload(pdf_path: Path, args: argparse.Namespace) -> dict:
    """Build an InsightRequest-like payload from a direct PDF path."""
    return {
        "mode": "insight",
        "request_id": args.request_id,
        "sources": [
            {
                "source_id": args.source_id or pdf_path.stem,
                "source_type": "pdf",
                "title": args.title or pdf_path.stem,
                "path": str(pdf_path),
            }
        ],
        "constraints": {},
        "options": {},
    }


def build_request_from_dict(data: dict, args: argparse.Namespace) -> InsightRequest:
    """Build InsightRequest from parsed JSON data."""
    sources = []
    for s in data.get("sources", []):
        content, title = resolve_source_content(s)
        sources.append(
            Source(
                source_id=s.get("source_id", f"src_{len(sources)+1}"),
                source_type=s.get("source_type", "text"),
                title=title,
                content=content,
                metadata=s.get("metadata"),
            )
        )

    personas = None
    if data.get("personas"):
        personas = [PersonaDefinition(**p) for p in data["personas"]]

    constraints_data = dict(data.get("constraints", {}))
    if args.domain:
        constraints_data["domain"] = args.domain
    constraints = Constraints(**constraints_data) if constraints_data else None

    context = Context(**data["context"]) if data.get("context") else None

    options_data = dict(data.get("options", {}))
    if args.include_source_units:
        options_data["include_source_units"] = True
    if args.checkpoint_path:
        options_data["checkpoint_path"] = str(args.checkpoint_path)
    if args.resume:
        options_data["resume"] = True
    if args.max_concurrency is not None:
        options_data["max_concurrency"] = args.max_concurrency
    options = Options(**options_data) if options_data else None

    return InsightRequest(
        mode=data.get("mode", "insight"),
        request_id=data.get("request_id"),
        sources=sources,
        constraints=constraints,
        personas=personas,
        context=context,
        options=options,
    )


if __name__ == "__main__":
    sys.exit(main())
