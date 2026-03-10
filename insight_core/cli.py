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


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Insight Agent - A problem discovery core agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Path to input JSON file (InsightRequest format)",
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

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        with open(args.input, encoding="utf-8") as f:
            input_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
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
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Response written to: {args.output}")
    else:
        print(output_json)

    return 0


def build_request_from_dict(data: dict, args: argparse.Namespace) -> InsightRequest:
    """Build InsightRequest from parsed JSON data."""
    sources = []
    for s in data.get("sources", []):
        sources.append(
            Source(
                source_id=s.get("source_id", f"src_{len(sources)+1}"),
                source_type=s.get("source_type", "text"),
                title=s.get("title"),
                content=s["content"],
                metadata=s.get("metadata"),
            )
        )

    personas = None
    if data.get("personas"):
        personas = [PersonaDefinition(**p) for p in data["personas"]]

    constraints_data = data.get("constraints", {})
    if args.domain:
        constraints_data["domain"] = args.domain
    constraints = Constraints(**constraints_data) if constraints_data else None

    context = Context(**data["context"]) if data.get("context") else None

    options_data = data.get("options", {})
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
