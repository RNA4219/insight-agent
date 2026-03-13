"""CLI entry point for Insight Agent."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from insight_core.request_loader import build_request_from_payload
from insight_core.result_formatter import build_agent_result
from insight_core.runner import run


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


def _normalized_argv(argv: list[str] | None = None) -> list[str]:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return ["run"]
    if argv[0] in {"run", "-h", "--help"}:
        return argv
    return ["run", *argv]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Insight Agent - A problem discovery core agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run insight analysis")
    run_parser.add_argument("-i", "--input", type=Path, default=None, help="Path to input JSON file")
    run_parser.add_argument("--pdf", type=Path, default=None, help="Path to a PDF file to analyze")
    run_parser.add_argument("--text", type=Path, default=None, help="Path to a text file to analyze")
    run_parser.add_argument("--source-id", type=str, default=None, help="Source ID override")
    run_parser.add_argument("--title", type=str, default=None, help="Source title override")
    run_parser.add_argument("--request-id", type=str, default=None, help="Optional request ID override")
    run_parser.add_argument("-o", "--output", type=Path, default=None, help="Path to output JSON file")
    run_parser.add_argument("--config", type=Path, default=None, help="Path to YAML/JSON config file")
    run_parser.add_argument("--set", dest="set_values", action="append", default=[], help="Override config value, e.g. --set llm.timeout_seconds=90")
    run_parser.add_argument("--output-format", choices=[OUTPUT_FORMAT_RESULT, OUTPUT_FORMAT_RAW], default=None, help="Override output format")
    run_parser.add_argument("--include-source-units", action="store_true", help="Override config to include source units")
    run_parser.add_argument("--domain", type=str, default=None, help="Domain context for analysis")
    run_parser.add_argument("--checkpoint-path", type=Path, default=None, help="Checkpoint JSON path")
    run_parser.add_argument("--resume", action="store_true", help="Resume from checkpoint when available")
    run_parser.add_argument("--max-concurrency", type=int, default=None, help="Maximum concurrent LLM calls")
    run_parser.add_argument("--japanese-summary", action="store_true", help="Generate Japanese summary")
    return parser


def build_pdf_input_payload(pdf_path: Path, args: argparse.Namespace) -> dict:
    return {
        "mode": "insight",
        "request_id": args.request_id,
        "sources": [{
            "source_id": args.source_id or pdf_path.stem,
            "source_type": "pdf",
            "title": args.title or pdf_path.stem,
            "path": str(pdf_path),
        }],
        "constraints": {},
        "options": {},
    }


def build_request_from_dict(data: dict, args: argparse.Namespace):
    option_overrides: dict[str, object] = {}
    if getattr(args, "include_source_units", False):
        option_overrides["include_source_units"] = True
    if getattr(args, "checkpoint_path", None):
        option_overrides["checkpoint_path"] = str(args.checkpoint_path)
    if getattr(args, "resume", False):
        option_overrides["resume"] = True
    if getattr(args, "max_concurrency", None) is not None:
        option_overrides["max_concurrency"] = args.max_concurrency
    if getattr(args, "japanese_summary", False):
        option_overrides["include_japanese_summary"] = True
    constraint_overrides: dict[str, object] = {}
    if getattr(args, "domain", None):
        constraint_overrides["domain"] = args.domain
    return build_request_from_payload(data, option_overrides=option_overrides, constraint_overrides=constraint_overrides)


def serialize_output(request, response, output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_RAW:
        return response.model_dump_json(indent=2)
    return json.dumps(build_agent_result(request, response), ensure_ascii=False, indent=2)


def serialize_result(result: object, output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_RAW and hasattr(result, "model_dump_json"):
        return result.model_dump_json(indent=2)
    return json.dumps(result, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalized_argv(argv))

    if args.command != "run":
        parser.print_help()
        return 1

    provided_inputs = [bool(args.input), bool(args.pdf), bool(args.text)]
    if sum(provided_inputs) != 1:
        print("Error: specify exactly one of --input, --pdf, or --text", file=sys.stderr)
        return 1

    for path_arg, label in ((args.input, "Input file"), (args.pdf, "PDF file"), (args.text, "Text file")):
        if path_arg and not path_arg.exists():
            print(f"Error: {label} not found: {path_arg}", file=sys.stderr)
            return 1

    override_dict: dict[str, object] = {}
    if args.include_source_units:
        override_dict.setdefault("output", {})["include_source_units"] = True
    if args.max_concurrency is not None:
        override_dict.setdefault("pipeline", {}).setdefault("limits", {})["max_concurrency"] = args.max_concurrency
    if args.japanese_summary:
        override_dict.setdefault("output", {})["include_japanese_summary"] = True

    print("入力サイズによっては数分かかることがあります。処理中はスピナーを表示します。", file=sys.stderr)

    try:
        with spinner("Insight Agent processing", enabled=sys.stderr.isatty()):
            result = run(
                input_path=args.input,
                pdf_path=args.pdf,
                text_path=args.text,
                source_id=args.source_id,
                title=args.title,
                request_id=args.request_id,
                config_path=args.config,
                overrides=override_dict,
                set_values=args.set_values,
                checkpoint_path=str(args.checkpoint_path) if args.checkpoint_path else None,
                resume=args.resume,
                domain=args.domain,
                output_format=args.output_format,
                verbose=True,
            )
    except Exception as exc:
        print(f"Error running pipeline: {exc}", file=sys.stderr)
        return 1

    chosen_format = args.output_format or OUTPUT_FORMAT_RESULT
    output_json = serialize_result(result, chosen_format)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Response written to: {args.output}")
    else:
        print(output_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
