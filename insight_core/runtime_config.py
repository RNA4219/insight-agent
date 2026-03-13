from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional until config file is used
    yaml = None


class LLMConfig(BaseModel):
    provider: str | None = None
    provider_sequence: list[str] = Field(default_factory=list)
    model: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    temperature: float = 0.7
    max_tokens: int = 4096
    stage_max_tokens: dict[str, int] = Field(default_factory=dict)


class RoutingConfigModel(BaseModel):
    enabled: bool = True
    primary_persona: str | None = None
    auto_select_personas: bool = True


class PipelineLimitsConfig(BaseModel):
    max_problem_candidates: int = 5
    max_insights: int = 3
    max_concurrency: int = 4


class PipelineConfig(BaseModel):
    routing: RoutingConfigModel = Field(default_factory=RoutingConfigModel)
    limits: PipelineLimitsConfig = Field(default_factory=PipelineLimitsConfig)
    partial_on_error: bool = True


class OutputConfig(BaseModel):
    format: str = "result"
    include_source_units: bool = False
    include_debug: bool = False
    include_intermediate_items: bool = False
    include_japanese_summary: bool = False
    pretty_print: bool = True


class RuntimeOptionsConfig(BaseModel):
    log_level: str = "INFO"
    tracing: bool = False
    cache: bool = True
    fail_fast: bool = False


class RuntimeConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    runtime: RuntimeOptionsConfig = Field(default_factory=RuntimeOptionsConfig)


DEFAULT_STAGE_TOKEN_ENVS = {
    "routing": "LLM_MAX_TOKENS_ROUTING",
    "extraction": "LLM_MAX_TOKENS_EXTRACTION",
    "discovery": "LLM_MAX_TOKENS_DISCOVERY",
    "evaluation": "LLM_MAX_TOKENS_EVALUATION",
    "consolidation": "LLM_MAX_TOKENS_CONSOLIDATION",
    "summary": "LLM_MAX_TOKENS_SUMMARY",
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_config_file(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    suffix = config_path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML config files")
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Config file must contain a mapping at the top level")
        return loaded
    raise ValueError(f"Unsupported config file format: {config_path}")


def _config_from_env() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if provider_sequence := os.environ.get("LLM_PROVIDER_SEQUENCE"):
        data = _deep_merge(data, {"llm": {"provider_sequence": [item.strip() for item in provider_sequence.split(",") if item.strip()]}})
    if provider := os.environ.get("LLM_PROVIDER"):
        data = _deep_merge(data, {"llm": {"provider": provider}})
    if timeout := os.environ.get("LLM_TIMEOUT_SECONDS"):
        data = _deep_merge(data, {"llm": {"timeout_seconds": float(timeout)}})
    if retries := os.environ.get("LLM_MAX_RETRIES"):
        data = _deep_merge(data, {"llm": {"max_retries": int(retries)}})
    if backoff := os.environ.get("LLM_RETRY_BACKOFF_SECONDS"):
        data = _deep_merge(data, {"llm": {"retry_backoff_seconds": float(backoff)}})
    if output_format := os.environ.get("INSIGHT_OUTPUT_FORMAT"):
        data = _deep_merge(data, {"output": {"format": output_format}})
    if include_units := os.environ.get("INSIGHT_INCLUDE_SOURCE_UNITS"):
        data = _deep_merge(data, {"output": {"include_source_units": include_units.lower() == "true"}})
    if include_debug := os.environ.get("INSIGHT_INCLUDE_DEBUG"):
        data = _deep_merge(data, {"output": {"include_debug": include_debug.lower() == "true"}})
    if max_problem_candidates := os.environ.get("INSIGHT_MAX_PROBLEM_CANDIDATES"):
        data = _deep_merge(data, {"pipeline": {"limits": {"max_problem_candidates": int(max_problem_candidates)}}})
    if max_insights := os.environ.get("INSIGHT_MAX_INSIGHTS"):
        data = _deep_merge(data, {"pipeline": {"limits": {"max_insights": int(max_insights)}}})
    if max_concurrency := os.environ.get("INSIGHT_MAX_CONCURRENCY"):
        data = _deep_merge(data, {"pipeline": {"limits": {"max_concurrency": int(max_concurrency)}}})
    stage_tokens = {
        stage: int(os.environ[env_key])
        for stage, env_key in DEFAULT_STAGE_TOKEN_ENVS.items()
        if env_key in os.environ
    }
    if stage_tokens:
        data = _deep_merge(data, {"llm": {"stage_max_tokens": stage_tokens}})
    return data


def _config_from_overrides(overrides: dict[str, Any] | None = None, set_values: list[str] | None = None) -> dict[str, Any]:
    merged = overrides or {}
    for item in set_values or []:
        if "=" not in item:
            raise ValueError(f"Override must be in key=value format: {item}")
        key, raw_value = item.split("=", 1)
        current: dict[str, Any] = {}
        cursor = current
        parts = [part for part in key.split(".") if part]
        if not parts:
            raise ValueError(f"Override key is empty: {item}")
        for part in parts[:-1]:
            next_cursor: dict[str, Any] = {}
            cursor[part] = next_cursor
            cursor = next_cursor
        cursor[parts[-1]] = _parse_scalar(raw_value)
        merged = _deep_merge(merged, current)
    return merged


def _request_local_config(request_dict: dict[str, Any] | None) -> dict[str, Any]:
    if not request_dict:
        return {}
    if isinstance(request_dict.get("config_override"), dict):
        return request_dict["config_override"]
    context = request_dict.get("context") or {}
    extra = context.get("extra") or {}
    if isinstance(extra.get("config_override"), dict):
        return extra["config_override"]
    return {}


def load_runtime_config(
    config: RuntimeConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    set_values: list[str] | None = None,
    request_dict: dict[str, Any] | None = None,
) -> RuntimeConfig:
    if config is not None:
        base = config.model_dump(mode="json")
    else:
        base = RuntimeConfig().model_dump(mode="json")
    merged = _deep_merge(base, _load_config_file(config_path))
    merged = _deep_merge(merged, config_dict or {})
    merged = _deep_merge(merged, _config_from_env())
    merged = _deep_merge(merged, _config_from_overrides(overrides, set_values))
    merged = _deep_merge(merged, _request_local_config(request_dict))
    return RuntimeConfig.model_validate(merged)
