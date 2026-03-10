"""LLM client module.

Provides a unified interface for LLM calls supporting OpenAI and Alibaba (DashScope).
Configuration is loaded from .env file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load .env from project root
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class LLMClient:
    """LLM client wrapper supporting OpenAI and Alibaba (DashScope)."""

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
    ):
        """Initialize LLM client.

        Args:
            model: Model identifier to use. Falls back to env var.
            provider: Provider to use ('openai' or 'alibaba'). Falls back to MEMX_LLM_PROVIDER.
            api_key: Optional API key. Falls back to provider-specific env var.
            base_url: Optional base URL. Falls back to provider-specific env var.
            max_tokens: Maximum tokens for response.
        """
        self.max_tokens = max_tokens

        # Determine provider
        self.provider = provider or os.environ.get("MEMX_LLM_PROVIDER", "openai")

        # Set configuration based on provider
        if self.provider == "alibaba":
            self.model = model or os.environ.get("MEMX_ALIBABA_MODEL", "glm-5")
            self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
            self.base_url = base_url or os.environ.get(
                "MEMX_ALIBABA_BASE_URL",
                "https://coding-intl.dashscope.aliyuncs.com/v1"
            )
        else:  # openai
            self.model = model or os.environ.get("MEMX_OPENAI_MODEL", "gpt-4o-mini")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            self.base_url = base_url or os.environ.get("MEMX_OPENAI_BASE_URL")

        if not self.api_key:
            raise ValueError(
                f"API key not found for provider '{self.provider}'. "
                f"Set {'DASHSCOPE_API_KEY' if self.provider == 'alibaba' else 'OPENAI_API_KEY'} in .env"
            )

        # Initialize OpenAI client (works for both OpenAI and DashScope)
        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self._client = OpenAI(**client_kwargs)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Make a completion request.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.
            temperature: Sampling temperature.

        Returns:
            Response text.
        """
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

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Make a completion request expecting JSON response.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON dict.

        Raises:
            ValueError: If response is not valid JSON.
        """
        response = self.complete(system_prompt, user_prompt, temperature)

        # Try to extract JSON from response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first line (```json or ```) and last line (```)
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
    """Create an LLM client instance using .env configuration.

    Returns:
        LLMClient instance.
    """
    return LLMClient()