import pytest

from insight_core.llm_client import (
    LLMClient,
    complete_json_async_compat,
    get_stage_max_tokens,
)


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_API_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://example.com")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "insight-agent")
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "180")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.setenv("ALIBABA_MODEL", "glm-5")


def test_llm_client_reads_openrouter_provider(monkeypatch, provider_env):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    client = LLMClient()

    assert client.provider == "openrouter"
    assert client.model == "openai/gpt-4.1-mini"
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.timeout_seconds == 180.0
    assert client.default_headers["HTTP-Referer"] == "https://example.com"
    assert client.default_headers["X-Title"] == "insight-agent"


def test_llm_client_reads_provider_sequence(monkeypatch, provider_env):
    monkeypatch.setenv("LLM_PROVIDER_SEQUENCE", "openrouter, openai")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    client = LLMClient()

    assert client.provider_sequence == ["openrouter", "openai"]
    assert client.model_sequence == ["openai/gpt-4.1-mini", "gpt-5"]
    assert client.provider_label == "openrouter,openai"
    assert client.model_label == "openai/gpt-4.1-mini,gpt-5"




def test_llm_client_reads_retry_and_timeout_defaults_from_env(monkeypatch, provider_env):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SECONDS", "0.25")

    client = LLMClient()

    assert client.timeout_seconds == 45.0
    assert client.max_retries == 5
    assert client.retry_backoff_seconds == 0.25

def test_llm_client_rotates_providers_between_retry_attempts(monkeypatch, provider_env):
    monkeypatch.setenv("LLM_PROVIDER_SEQUENCE", "openrouter,openai")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    client = LLMClient(max_retries=3, retry_backoff_seconds=0)
    attempts: list[str] = []

    def fake_request(endpoint, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int | None = None) -> str:
        attempts.append(endpoint.provider)
        if len(attempts) < 3:
            raise RuntimeError("transient")
        return '{"ok": true}'

    monkeypatch.setattr(client, "_request_completion_with_endpoint", fake_request)

    result = client.complete_json("system", "user")

    assert result == {"ok": True}
    assert attempts == ["openrouter", "openai", "openrouter"]


def test_stage_max_tokens_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS_EXTRACTION", "321")

    assert get_stage_max_tokens("extraction") == 321


class LegacyAsyncStub:
    async def complete_json_async(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        return {"ok": True}


@pytest.mark.asyncio
async def test_complete_json_async_compat_supports_legacy_stub():
    result = await complete_json_async_compat(
        LegacyAsyncStub(),
        "system",
        "user",
        max_tokens=111,
    )

    assert result == {"ok": True}
