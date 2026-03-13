from types import SimpleNamespace

from insight_core.runner import RAW_FORMAT, run
from insight_core.schemas import InsightRequest, Source


class DummyResponse:
    def __init__(self):
        self.run = SimpleNamespace(status='completed')

    def model_dump_json(self, indent=2):
        return '{"raw": true}'


def test_run_uses_canonical_config_and_formats_result(monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    monkeypatch.delenv('LLM_PROVIDER_SEQUENCE', raising=False)
    monkeypatch.delenv('LLM_TIMEOUT_SECONDS', raising=False)
    captured = {}

    def fake_run_pipeline(request, llm, verbose):
        captured['request'] = request
        captured['llm'] = llm
        captured['verbose'] = verbose
        return DummyResponse()

    monkeypatch.setattr('insight_core.runner.run_pipeline', fake_run_pipeline)
    monkeypatch.setattr('insight_core.runner.build_agent_result', lambda request, response: {'version': 'output_schema_v2', 'source_count': len(request.sources)})

    result = run(
        request_dict={
            'mode': 'insight',
            'request_id': 'req_1',
            'sources': [{'source_id': 'src_1', 'source_type': 'text', 'title': 'Doc', 'content': 'hello'}],
        },
        config_dict={
            'pipeline': {'limits': {'max_concurrency': 9, 'max_problem_candidates': 8}},
            'output': {'format': 'result'},
            'llm': {'provider': 'openrouter', 'timeout_seconds': 77},
        },
        verbose=False,
    )

    assert result['version'] == 'output_schema_v2'
    assert captured['request'].options.max_concurrency == 9
    assert captured['request'].constraints.max_problem_candidates == 8
    assert captured['llm'].provider == 'openrouter'
    assert captured['llm'].timeout_seconds == 77
    assert captured['verbose'] is False


def test_run_raw_returns_response_object(monkeypatch):
    response = DummyResponse()
    monkeypatch.setattr('insight_core.runner.run_pipeline', lambda request, llm, verbose: response)

    result = run(
        request=InsightRequest(sources=[Source(source_id='src_1', title='Doc', content='hello')]),
        config_dict={'output': {'format': RAW_FORMAT}},
        verbose=False,
    )

    assert result is response
