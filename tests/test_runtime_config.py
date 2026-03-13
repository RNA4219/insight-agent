from insight_core.runtime_config import load_runtime_config


def test_runtime_config_merges_precedence(monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    monkeypatch.delenv('LLM_PROVIDER_SEQUENCE', raising=False)
    monkeypatch.setenv('LLM_TIMEOUT_SECONDS', '90')
    monkeypatch.setenv('INSIGHT_MAX_INSIGHTS', '4')

    config = load_runtime_config(
        config_dict={
            'llm': {'timeout_seconds': 45, 'provider': 'openai'},
            'pipeline': {'limits': {'max_insights': 2}},
        },
        overrides={'pipeline': {'limits': {'max_problem_candidates': 7}}},
        set_values=['llm.timeout_seconds=120', 'output.format=raw'],
        request_dict={'config_override': {'pipeline': {'limits': {'max_insights': 6}}}},
    )

    assert config.llm.timeout_seconds == 120
    assert config.llm.provider == 'openai'
    assert config.pipeline.limits.max_problem_candidates == 7
    assert config.pipeline.limits.max_insights == 6
    assert config.output.format == 'raw'
