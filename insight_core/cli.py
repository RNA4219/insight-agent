"""CLI entry point for Insight Agent."""

from __future__ import annotations

import argparse
import itertools
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from insight_core.pipeline import run_pipeline
from insight_core.result_formatter import build_agent_result
from insight_core.schemas import (
    Constraints,
    Context,
    InsightRequest,
    Options,
    PersonaDefinition,
    Source,
)
from insight_core.source_loader import resolve_source_content


OUTPUT_FORMAT_RESULT = "result"
OUTPUT_FORMAT_RAW = "raw"


@contextmanager
def spinner(message: str, enabled: bool = True):
    if not enabled:
        yield
        return

    stop_event = threading.Event()

    def _run() -> None:
        for frame in itertools.cycle("|/-\\"):
            if stop_event.wait(0.12):
                break
            print(f"\r{message} {frame}", end="", file=sys.stderr, flush=True)
        print(f"\r{message} done", file=sys.stderr, flush=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()


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
        "--output-format",
        choices=[OUTPUT_FORMAT_RESULT, OUTPUT_FORMAT_RAW],
        default=OUTPUT_FORMAT_RESULT,
        help="Output contract: compact API/CLI result or raw internal response",
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
    parser.add_argument(
        "--japanese-summary",
        action="store_true",
        help="Generate Japanese summary of analysis results",
    )
    return parser



def serialize_output(request: InsightRequest, response, output_format: str) -> str:
    """Serialize the pipeline result into the requested output contract."""
    if output_format == OUTPUT_FORMAT_RAW:
        return response.model_dump_json(indent=2)
    final_result = build_agent_result(request, response)
    import json
    return json.dumps(final_result, ensure_ascii=False, indent=2)



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
            import json

            with open(args.input, encoding="utf-8") as f:
                input_data = json.load(f)
        else:
            input_data = build_pdf_input_payload(args.pdf, args)
    except Exception as e:
        print(f"Error loading input: {e}", file=sys.stderr)
        return 1

    try:
        request = build_request_from_dict(input_data, args)
    except Exception as e:
        print(f"Error building request: {e}", file=sys.stderr)
        return 1

    print("入力サイズによっては数分かかることがあります。処理中はスピナーを表示します。", file=sys.stderr)

    try:
        with spinner("Insight Agent processing", enabled=sys.stderr.isatty()):
            response = run_pipeline(request)
    except Exception as e:
        print(f"Error running pipeline: {e}", file=sys.stderr)
        return 1

    output_json = serialize_output(request, response, args.output_format)

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
    if args.japanese_summary:
        options_data["include_japanese_summary"] = True
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
