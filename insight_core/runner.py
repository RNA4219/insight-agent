from __future__ import annotations

from pathlib import Path
from typing import Any

from insight_core.llm_client import LLMClient
from insight_core.pipeline import run_pipeline, run_pipeline_async
from insight_core.request_loader import load_request
from insight_core.result_formatter import build_agent_result
from insight_core.runtime_config import RuntimeConfig, load_runtime_config
from insight_core.schemas import InsightRequest


RESULT_FORMAT = "result"
RAW_FORMAT = "raw"


def _build_llm_client(config: RuntimeConfig) -> LLMClient:
    provider = None
    if config.llm.provider_sequence:
        provider = ",".join(config.llm.provider_sequence)
    elif config.llm.provider:
        provider = config.llm.provider
    return LLMClient(
        model=config.llm.model,
        provider=provider,
        max_tokens=config.llm.max_tokens,
        max_retries=config.llm.max_retries,
        retry_backoff_seconds=config.llm.retry_backoff_seconds,
        timeout_seconds=config.llm.timeout_seconds,
    )


def _request_option_overrides(config: RuntimeConfig, checkpoint_path: str | None = None, resume: bool = False) -> dict[str, Any]:
    return {
        "include_source_units": config.output.include_source_units,
        "include_intermediate_items": config.output.include_intermediate_items,
        "include_japanese_summary": config.output.include_japanese_summary,
        "max_concurrency": config.pipeline.limits.max_concurrency,
        "checkpoint_path": checkpoint_path,
        "resume": resume,
    }


def _request_constraint_overrides(config: RuntimeConfig, domain: str | None = None) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        "max_problem_candidates": config.pipeline.limits.max_problem_candidates,
        "max_insights": config.pipeline.limits.max_insights,
    }
    if config.pipeline.routing.primary_persona:
        overrides["primary_persona"] = config.pipeline.routing.primary_persona
    if domain:
        overrides["domain"] = domain
    return overrides


def _format_result(request: InsightRequest, response: Any, output_format: str) -> Any:
    if output_format == RAW_FORMAT:
        return response
    return build_agent_result(request, response)


def run(
    *,
    request: InsightRequest | None = None,
    request_dict: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    set_values: list[str] | None = None,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
    checkpoint_path: str | None = None,
    resume: bool = False,
    domain: str | None = None,
    output_format: str | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> Any:
    runtime_config = load_runtime_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        overrides=overrides,
        set_values=set_values,
        request_dict=request_dict,
    )
    if request is None:
        request, request_payload = load_request(
            input_path=input_path,
            pdf_path=pdf_path,
            text_path=text_path,
            request_dict=request_dict,
            source_id=source_id,
            title=title,
            request_id=request_id,
            option_overrides=_request_option_overrides(runtime_config, checkpoint_path=checkpoint_path, resume=resume),
            constraint_overrides=_request_constraint_overrides(runtime_config, domain=domain),
        )
        _ = request_payload
    llm_client = llm or _build_llm_client(runtime_config)
    response = run_pipeline(request=request, llm=llm_client, verbose=verbose)
    return _format_result(request, response, output_format or runtime_config.output.format)


async def run_async(
    *,
    request: InsightRequest | None = None,
    request_dict: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    set_values: list[str] | None = None,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
    checkpoint_path: str | None = None,
    resume: bool = False,
    domain: str | None = None,
    output_format: str | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> Any:
    runtime_config = load_runtime_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        overrides=overrides,
        set_values=set_values,
        request_dict=request_dict,
    )
    if request is None:
        request, request_payload = load_request(
            input_path=input_path,
            pdf_path=pdf_path,
            text_path=text_path,
            request_dict=request_dict,
            source_id=source_id,
            title=title,
            request_id=request_id,
            option_overrides=_request_option_overrides(runtime_config, checkpoint_path=checkpoint_path, resume=resume),
            constraint_overrides=_request_constraint_overrides(runtime_config, domain=domain),
        )
        _ = request_payload
    llm_client = llm or _build_llm_client(runtime_config)
    response = await run_pipeline_async(request=request, llm=llm_client, verbose=verbose)
    return _format_result(request, response, output_format or runtime_config.output.format)
