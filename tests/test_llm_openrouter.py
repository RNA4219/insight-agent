import os

from insight_core.llm_client import LLMClient


def test_llm_client_reads_openrouter_provider(monkeypatch):
    monkeypatch.setenv("MEMX_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://example.com")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "insight-agent")
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "180")

    client = LLMClient()

    assert client.provider == "openrouter"
    assert client.model == "openai/gpt-4.1-mini"
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.timeout_seconds == 180.0
    assert client.default_headers["HTTP-Referer"] == "https://example.com"
    assert client.default_headers["X-Title"] == "insight-agent"
