"""LLM client module.

Provides a unified interface for LLM calls supporting OpenAI-compatible providers.
Configuration is loaded from .env file.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
DEFAULT_STAGE_MAX_TOKENS = {
    "routing": 500,
    "extraction": 900,
    "discovery": 1200,
    "evaluation": 400,
    "consolidation": 900,
    "summary": 1200,
}


@dataclass
class _ProviderEndpoint:
    provider: str
    model: str
    api_key: str
    base_url: str | None
    timeout_seconds: float
    default_headers: dict[str, str]
    client: OpenAI
    async_client: AsyncOpenAI


def _first_env(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return default


def _parse_provider_sequence(provider: str | None) -> list[str]:
    raw = os.environ.get("LLM_PROVIDER_SEQUENCE") or provider or os.environ.get("LLM_PROVIDER", "openai")
    providers = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return providers or ["openai"]


def get_stage_max_tokens(stage: str, default: int | None = None) -> int:
    normalized_stage = stage.strip().lower()
    fallback = default if default is not None else DEFAULT_STAGE_MAX_TOKENS.get(normalized_stage, 1024)
    env_key = f"LLM_MAX_TOKENS_{normalized_stage.upper()}"
    return int(os.environ.get(env_key, fallback))


def _supports_keyword_argument(method: Any, argument_name: str) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return False

    if argument_name in signature.parameters:
        return True

    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def complete_json_compat(
    llm: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    method = llm.complete_json
    kwargs: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and _supports_keyword_argument(method, "max_tokens"):
        kwargs["max_tokens"] = max_tokens
    return method(system_prompt, user_prompt, **kwargs)


async def complete_json_async_compat(
    llm: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    method = llm.complete_json_async
    kwargs: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and _supports_keyword_argument(method, "max_tokens"):
        kwargs["max_tokens"] = max_tokens
    return await method(system_prompt, user_prompt, **kwargs)


def complete_compat(
    llm: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    method = llm.complete
    kwargs: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and _supports_keyword_argument(method, "max_tokens"):
        kwargs["max_tokens"] = max_tokens
    return method(system_prompt, user_prompt, **kwargs)


async def complete_async_compat(
    llm: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    method = llm.complete_async
    kwargs: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and _supports_keyword_argument(method, "max_tokens"):
        kwargs["max_tokens"] = max_tokens
    return await method(system_prompt, user_prompt, **kwargs)


class LLMClient:
    """LLM client wrapper supporting OpenAI-compatible providers."""

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ):
        self.max_tokens = max_tokens
        self.max_retries = max_retries if max_retries is not None else int(
            os.environ.get("LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES)
        )
        self.retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else float(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", DEFAULT_RETRY_BACKOFF_SECONDS))
        )
        self._request_counter = itertools.count()

        requested_providers = _parse_provider_sequence(provider)
        self._provider_endpoints = [
            self._build_provider_endpoint(
                provider_name,
                model if index == 0 else None,
                api_key if index == 0 else None,
                base_url if index == 0 else None,
                timeout_seconds if index == 0 else None,
            )
            for index, provider_name in enumerate(requested_providers)
        ]

        primary = self._provider_endpoints[0]
        self.provider_sequence = [endpoint.provider for endpoint in self._provider_endpoints]
        self.model_sequence = [endpoint.model for endpoint in self._provider_endpoints]
        self.provider = primary.provider
        self.model = primary.model
        self.api_key = primary.api_key
        self.base_url = primary.base_url
        self.timeout_seconds = primary.timeout_seconds
        self.default_headers = dict(primary.default_headers)
        self.provider_label = ",".join(self.provider_sequence)
        self.model_label = ",".join(self.model_sequence)
        self.last_provider = primary.provider
        self.last_model = primary.model

    def _build_provider_endpoint(
        self,
        provider_name: str,
        model: str | None,
        api_key: str | None,
        base_url: str | None,
        timeout_seconds: float | None,
    ) -> _ProviderEndpoint:
        provider_name = provider_name.lower()

        if provider_name == "alibaba":
            resolved_model = model or os.environ.get("ALIBABA_MODEL", "glm-5")
            resolved_api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
            resolved_base_url = base_url or os.environ.get(
                "ALIBABA_BASE_URL",
                "https://coding-intl.dashscope.aliyuncs.com/v1",
            )
            resolved_timeout = timeout_seconds or float(
                _first_env("ALIBABA_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", default=str(DEFAULT_TIMEOUT_SECONDS))
            )
            default_headers: dict[str, str] = {}
            missing_key_hint = "DASHSCOPE_API_KEY"
        elif provider_name == "openrouter":
            resolved_model = model or _first_env(
                "OPENROUTER_MODEL",
                "OPENROUTER_API_MODEL",
                default="nvidia/nemotron-3-nano-30b-a3b:free",
            )
            resolved_api_key = api_key or _first_env("OPENROUTER_API_KEY", "OPENROUTER_KEY")
            resolved_base_url = base_url or _first_env(
                "OPENROUTER_BASE_URL",
                "OPENROUTER_API_BASE",
                default="https://openrouter.ai/api/v1",
            )
            resolved_timeout = timeout_seconds or float(
                _first_env("OPENROUTER_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", default=str(DEFAULT_TIMEOUT_SECONDS))
            )
            default_headers = {}
            referer = _first_env("OPENROUTER_SITE_URL")
            title = _first_env("OPENROUTER_APP_NAME")
            if referer:
                default_headers["HTTP-Referer"] = referer
            if title:
                default_headers["X-Title"] = title
            missing_key_hint = "OPENROUTER_API_KEY"
        elif provider_name == "openai":
            resolved_model = model or os.environ.get("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
            resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
            resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL")
            resolved_timeout = timeout_seconds or float(
                _first_env("OPENAI_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", default=str(DEFAULT_TIMEOUT_SECONDS))
            )
            default_headers = {}
            missing_key_hint = "OPENAI_API_KEY"
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        if not resolved_api_key:
            raise ValueError(
                f"API key not found for provider '{provider_name}'. Set {missing_key_hint} in .env"
            )

        client_kwargs: dict[str, Any] = {"api_key": resolved_api_key, "timeout": resolved_timeout}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        return _ProviderEndpoint(
            provider=provider_name,
            model=resolved_model,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            timeout_seconds=resolved_timeout,
            default_headers=default_headers,
            client=OpenAI(**client_kwargs),
            async_client=AsyncOpenAI(**client_kwargs),
        )

    def _next_provider_start_index(self) -> int:
        endpoints = getattr(self, "_provider_endpoints", None)
        if not endpoints:
            return 0

        request_counter = getattr(self, "_request_counter", None)
        if request_counter is None:
            return 0

        return next(request_counter) % len(endpoints)

    def _endpoint_for_attempt(
        self,
        attempt_index: int,
        start_index: int,
    ) -> _ProviderEndpoint | None:
        endpoints = getattr(self, "_provider_endpoints", None)
        if not endpoints:
            return None
        return endpoints[(start_index + attempt_index) % len(endpoints)]

    def _request_completion_with_endpoint(
        self,
        endpoint: _ProviderEndpoint,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        self.last_provider = endpoint.provider
        self.last_model = endpoint.model
        effective_max_tokens = self.max_tokens if max_tokens is None else max_tokens

        if endpoint.provider == "openai":
            response = endpoint.client.chat.completions.create(
                model=endpoint.model,
                max_completion_tokens=effective_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        else:
            response = endpoint.client.chat.completions.create(
                model=endpoint.model,
                max_tokens=effective_max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        return response.choices[0].message.content or ""

    async def _request_completion_async_with_endpoint(
        self,
        endpoint: _ProviderEndpoint,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        self.last_provider = endpoint.provider
        self.last_model = endpoint.model
        effective_max_tokens = self.max_tokens if max_tokens is None else max_tokens

        if endpoint.provider == "openai":
            response = await endpoint.async_client.chat.completions.create(
                model=endpoint.model,
                max_completion_tokens=effective_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        else:
            response = await endpoint.async_client.chat.completions.create(
                model=endpoint.model,
                max_tokens=effective_max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        return response.choices[0].message.content or ""

    def _request_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        endpoint = self._provider_endpoints[0]
        return self._request_completion_with_endpoint(
            endpoint,
            system_prompt,
            user_prompt,
            temperature,
            max_tokens=max_tokens,
        )

    async def _request_completion_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        endpoint = self._provider_endpoints[0]
        return await self._request_completion_async_with_endpoint(
            endpoint,
            system_prompt,
            user_prompt,
            temperature,
            max_tokens=max_tokens,
        )

    def _complete_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        last_error: Exception | None = None
        start_index = self._next_provider_start_index() if hasattr(self, "_next_provider_start_index") else 0

        for attempt_index in range(self.max_retries):
            endpoint = self._endpoint_for_attempt(attempt_index, start_index) if hasattr(self, "_endpoint_for_attempt") else None
            try:
                if endpoint is not None and hasattr(self, "_request_completion_with_endpoint"):
                    return self._request_completion_with_endpoint(
                        endpoint,
                        system_prompt,
                        user_prompt,
                        temperature,
                        max_tokens=max_tokens,
                    )
                if max_tokens is not None and _supports_keyword_argument(self._request_completion, "max_tokens"):
                    return self._request_completion(
                        system_prompt,
                        user_prompt,
                        temperature,
                        max_tokens=max_tokens,
                    )
                return self._request_completion(system_prompt, user_prompt, temperature)
            except Exception as exc:
                last_error = exc
                if attempt_index + 1 >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt_index + 1))

        assert last_error is not None
        raise last_error

    async def _complete_with_retry_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        last_error: Exception | None = None
        start_index = self._next_provider_start_index() if hasattr(self, "_next_provider_start_index") else 0

        for attempt_index in range(self.max_retries):
            endpoint = self._endpoint_for_attempt(attempt_index, start_index) if hasattr(self, "_endpoint_for_attempt") else None
            try:
                if endpoint is not None and hasattr(self, "_request_completion_async_with_endpoint"):
                    return await self._request_completion_async_with_endpoint(
                        endpoint,
                        system_prompt,
                        user_prompt,
                        temperature,
                        max_tokens=max_tokens,
                    )
                if max_tokens is not None and _supports_keyword_argument(self._request_completion_async, "max_tokens"):
                    return await self._request_completion_async(
                        system_prompt,
                        user_prompt,
                        temperature,
                        max_tokens=max_tokens,
                    )
                return await self._request_completion_async(system_prompt, user_prompt, temperature)
            except Exception as exc:
                last_error = exc
                if attempt_index + 1 >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_backoff_seconds * (attempt_index + 1))

        assert last_error is not None
        raise last_error

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        return self._complete_with_retry(system_prompt, user_prompt, temperature, max_tokens=max_tokens)

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        try:
            return await self._complete_with_retry_async(
                system_prompt,
                user_prompt,
                temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            return await asyncio.to_thread(
                self._complete_with_retry,
                system_prompt,
                user_prompt,
                temperature,
                max_tokens,
            )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.complete(
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens=max_tokens,
                )
                return self._parse_json_response(response)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)
        assert last_error is not None
        raise last_error

    async def complete_json_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.complete_async(
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens=max_tokens,
                )
                return self._parse_json_response(response)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_backoff_seconds * attempt)
        assert last_error is not None
        raise last_error

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)

        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse JSON response: {exc}\nResponse: {response[:500]}"
            ) from exc


def create_client() -> LLMClient:
    return LLMClient()
