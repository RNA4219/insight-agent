"""LLM client module.

Provides a unified interface for LLM calls supporting OpenAI-compatible providers.
Configuration is loaded from .env file.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

DEFAULT_TIMEOUT_SECONDS = 120.0


def _first_env(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return default


class LLMClient:
    """LLM client wrapper supporting OpenAI-compatible providers."""

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        timeout_seconds: float | None = None,
    ):
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.provider = (provider or os.environ.get("MEMX_LLM_PROVIDER", "openai")).lower()

        if self.provider == "alibaba":
            self.model = model or os.environ.get("MEMX_ALIBABA_MODEL", "glm-5")
            self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
            self.base_url = base_url or os.environ.get(
                "MEMX_ALIBABA_BASE_URL",
                "https://coding-intl.dashscope.aliyuncs.com/v1",
            )
            self.timeout_seconds = timeout_seconds or float(os.environ.get("MEMX_ALIBABA_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
            self.default_headers: dict[str, str] = {}
            missing_key_hint = "DASHSCOPE_API_KEY"
        elif self.provider == "openrouter":
            self.model = model or _first_env(
                "MEMX_OPENROUTER_MODEL",
                "OPENROUTER_API_MODEL",
                default="openai/gpt-4.1-mini",
            )
            self.api_key = api_key or _first_env("OPENROUTER_API_KEY", "OPENROUTER_KEY")
            self.base_url = base_url or _first_env(
                "MEMX_OPENROUTER_BASE_URL",
                "OPENROUTER_BASE_URL",
                "OPENROUTER_API_BASE",
                default="https://openrouter.ai/api/v1",
            )
            self.timeout_seconds = timeout_seconds or float(
                _first_env(
                    "MEMX_OPENROUTER_TIMEOUT_SECONDS",
                    "OPENROUTER_TIMEOUT_SECONDS",
                    default=str(DEFAULT_TIMEOUT_SECONDS),
                )
            )
            self.default_headers = {}
            referer = _first_env("MEMX_OPENROUTER_SITE_URL", "OPENROUTER_SITE_URL")
            title = _first_env("MEMX_OPENROUTER_APP_NAME", "OPENROUTER_APP_NAME")
            if referer:
                self.default_headers["HTTP-Referer"] = referer
            if title:
                self.default_headers["X-Title"] = title
            missing_key_hint = "OPENROUTER_API_KEY"
        else:
            self.model = model or os.environ.get("MEMX_OPENAI_MODEL", "gpt-4o-mini")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            self.base_url = base_url or os.environ.get("MEMX_OPENAI_BASE_URL")
            self.timeout_seconds = timeout_seconds or float(os.environ.get("MEMX_OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
            self.default_headers = {}
            missing_key_hint = "OPENAI_API_KEY"

        if not self.api_key:
            raise ValueError(
                f"API key not found for provider '{self.provider}'. Set {missing_key_hint} in .env"
            )

        client_kwargs: dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_seconds}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        if self.default_headers:
            client_kwargs["default_headers"] = self.default_headers

        self._client = OpenAI(**client_kwargs)
        self._async_client = AsyncOpenAI(**client_kwargs)

    def _request_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def _request_completion_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        response = await self._async_client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def _complete_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._request_completion(system_prompt, user_prompt, temperature)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        assert last_error is not None
        raise last_error

    async def _complete_with_retry_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._request_completion_async(system_prompt, user_prompt, temperature)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_backoff_seconds * attempt)

        assert last_error is not None
        raise last_error

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        return self._complete_with_retry(system_prompt, user_prompt, temperature)

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        try:
            return await self._complete_with_retry_async(system_prompt, user_prompt, temperature)
        except Exception:
            return await asyncio.to_thread(
                self._complete_with_retry,
                system_prompt,
                user_prompt,
                temperature,
            )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        response = self.complete(system_prompt, user_prompt, temperature)
        return self._parse_json_response(response)

    async def complete_json_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        response = await self.complete_async(system_prompt, user_prompt, temperature)
        return self._parse_json_response(response)

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
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response[:500]}") from e


def create_client() -> LLMClient:
    return LLMClient()
