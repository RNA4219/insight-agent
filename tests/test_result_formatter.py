import json

from insight_core.cli import OUTPUT_FORMAT_RAW, OUTPUT_FORMAT_RESULT, serialize_output
from insight_core.response_builder import build_response
from insight_core.result_formatter import _apply_prompt_repetition_feedback, build_agent_result
from insight_core.schemas import (
    ClaimItem,
    Constraints,
    Decision,
    DerivationType,
    EpistemicMode,
    FailureItem,
    InsightRequest,
    OpenQuestionItem,
    Options,
    PersonaSource,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
    RunStatus,
    Source,
    UpdateRule,
)
from insight_core.schemas import NormalizedRequest


def _build_request() -> tuple[InsightRequest, NormalizedRequest]:
    request = InsightRequest(
        mode='insight',
        request_id='req_result_001',
        sources=[Source(source_id='src_1', title='Doc', content='demo text')],
        constraints=Constraints(domain='machine_learning', max_problem_candidates=3, max_insights=2),
        options=Options(include_intermediate_items=False),
    )
    normalized = NormalizedRequest(
        run_id='run_result_001',
        request_id='req_result_001',
        sources=request.sources,
        constraints=request.constraints,
        personas=[],
        persona_source=PersonaSource.DEFAULT,
        persona_catalog_version='default_personas.v4',
        context={},
        options=request.options,
    )
    return request, normalized


def _build_response():
    request, normalized = _build_request()
    response = build_response(
        normalized_request=normalized,
        claims=[
            ClaimItem(
                id='cl_001',
                statement='SkillNet significantly enhances agent performance in benchmark environments.',
                epistemic_mode=EpistemicMode.OBSERVATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.9,
                evidence_refs=['ev_001'],
                update_rule=UpdateRule.RETAIN,
            ),
            ClaimItem(
                id='cl_002',
                statement='SkillNet supports real-world deployment.',
                epistemic_mode=EpistemicMode.INTERPRETATION,
                derivation_type=DerivationType.DIRECT,
                confidence=0.85,
                evidence_refs=['ev_002'],
                update_rule=UpdateRule.RETAIN,
            ),
        ],
        assumptions=[],
        limitations=[],
        problem_candidates=[
            ProblemCandidateItem(
                id='pb_001',
                statement='ベンチマーク環境と実世界の間の一般化ギャップを考慮していない',
                problem_type=ProblemType.GENERALIZATION_GAP,
                scope=ProblemScope.SYSTEM,
                epistemic_mode=EpistemicMode.HYPOTHESIS,
                derivation_type=DerivationType.INFERRED,
                confidence=0.74,
                parent_refs=['cl_001', 'cl_002'],
                support_signals=['評価はシミュレート環境に限定', '実世界展開を主張'],
                failure_signals=['複数ベンチマークで一貫して改善'],
                decision=Decision.NEEDS_MORE_EVIDENCE,
                update_rule=UpdateRule.RETAIN,
            ),
            ProblemCandidateItem(
                id='pb_002',
                statement='導入責任と障害対応の計画がなく、実運用コストが不明確である',
                problem_type=ProblemType.OPERATIONAL_RISK,
                scope=ProblemScope.LOCAL,
                epistemic_mode=EpistemicMode.HYPOTHESIS,
                derivation_type=DerivationType.INFERRED,
                confidence=0.7,
                parent_refs=['cl_002'],
                support_signals=['運用フローが語られていない', '責任分界が曖昧'],
                failure_signals=['フルライフサイクル支援を主張'],
                decision=Decision.NEEDS_MORE_EVIDENCE,
                update_rule=UpdateRule.RETAIN,
            ),
        ],
        insights=[],
        open_questions=[
            OpenQuestionItem(
                question_id='oq_pb_001',
                statement='別データ分布でも性能が維持されるか未確認',
                confidence=0.41,
                parent_refs=['pb_001'],
                promotion_condition='別データ分布で再評価すること',
                closure_condition='一般化可否が確認されること',
            )
        ],
        evidence_refs=[],
        failures=[
            FailureItem(
                failure_id='fl_001',
                stage='evaluation',
                reason='partial timeout',
                suggested_next_action='retry evaluation',
            )
        ],
        confidence=0.77,
        status=RunStatus.PARTIAL,
    )
    return request, response


def test_build_agent_result_returns_output_schema_v2_shape():
    request, response = _build_response()
    result = build_agent_result(request, response)

    assert result['version'] == 'output_schema_v2'
    assert result['run']['status'] == 'partial'
    assert result['problems'][0]['problem_type'] == 'claim_scope_mismatch'
    assert result['risk_notes'][0]['risk_type'] == 'deployment_extrapolation'
    assert len(result['insights']) >= 2
    assert result['reasoning_summary']['recommended_reading'] == 'accept_core_results_with_scope_caution'
    assert result['open_questions'][0]['question_type'] == 'validation_experiment'


def test_serialize_output_returns_v2_contract_by_default():
    request, response = _build_response()
    payload = json.loads(serialize_output(request, response, OUTPUT_FORMAT_RESULT))

    assert payload['version'] == 'output_schema_v2'
    assert 'nodes' in payload and 'problems' in payload and 'risk_notes' in payload
    assert 'claims' not in payload


def test_serialize_output_raw_keeps_internal_response_shape():
    request, response = _build_response()
    payload = json.loads(serialize_output(request, response, OUTPUT_FORMAT_RAW))

    assert 'run' in payload and 'claims' in payload and 'reasoning_summary' in payload
    assert 'nodes' not in payload

def test_prompt_repetition_feedback_rewrites_wording_and_moves_nodes():
    result = {
        'nodes': [
            {'id': 'lm_unit_2512.14982v1_1_5', 'node_type': 'limitation', 'statement': 'この改善は推論を使用しない場合にのみ適用される', 'confidence': 0.8},
            {'id': 'as_unit_2512.14982v1_3_3', 'node_type': 'assumption', 'statement': 'The performance improvement is valid only when reasoning is not used.', 'confidence': 0.8},
            {'id': 'lm_unit_2512.14982v1_3_6', 'node_type': 'limitation', 'statement': 'The technique is only applicable when not using reasoning, limiting its generalization.', 'confidence': 0.8},
            {'id': 'cl_unit_2512.14982v1_2_2', 'node_type': 'claim', 'statement': 'プロンプトリピーティンは生成される出力の長さや測定されたレイテンシを増加させない', 'confidence': 0.9},
            {'id': 'cl_unit_2512.14982v1_3_2', 'node_type': 'claim', 'statement': 'latency is not impacted, as only the parallelizable pre-fill stage is affected.', 'confidence': 0.9},
        ],
        'problems': [
            {'id': 'pb_001', 'statement': 'old 1', 'problem_type': 'evaluation_gap', 'confidence': 0.8, 'decision': 'accept', 'support_bundle': {'claim_ids': [], 'assumption_ids': [], 'limitation_ids': [], 'evidence_ids': []}, 'next_checks': [], 'parent_refs': []},
            {'id': 'pb_002', 'statement': 'old 2', 'problem_type': 'assumption_weakness', 'confidence': 0.6, 'decision': 'needs_more_evidence', 'support_bundle': {'claim_ids': [], 'assumption_ids': [], 'limitation_ids': [], 'evidence_ids': ['ev_1']}, 'next_checks': [], 'parent_refs': []},
            {'id': 'pb_003', 'statement': 'old 3', 'problem_type': 'deployment_extrapolation', 'confidence': 0.6, 'decision': 'needs_more_evidence', 'support_bundle': {'claim_ids': ['cl_unit_2512.14982v1_2_2', 'cl_unit_2512.14982v1_3_2'], 'assumption_ids': [], 'limitation_ids': [], 'evidence_ids': ['ev_2']}, 'next_checks': [], 'parent_refs': ['cl_unit_2512.14982v1_3_2']},
        ],
        'risk_notes': [],
        'open_questions': [],
        'insights': [],
        'evidence_refs': [
            {'evidence_id': 'ev_20', 'source_id': '2512.14982v1', 'unit_id': 'unit_2512.14982v1_4', 'quote': 'reasoning often starts by repeating the prompt', 'evidence_role': ['main_support'], 'strength': 0.7},
        ],
        'reasoning_summary': {},
    }

    updated = _apply_prompt_repetition_feedback(result)

    latency_nodes = [node for node in updated['nodes'] if node['id'] == 'cl_unit_2512.14982v1_2_2']
    assert updated['nodes'][0]['statement'] == 'largest gains are reported when reasoning is disabled'
    assert next(node for node in updated['nodes'] if node['id'] == 'as_unit_2512.14982v1_3_3')['statement'] == 'The strongest performance gains are supported when reasoning is not used.'
    assert next(node for node in updated['nodes'] if node['id'] == 'as_unit_2512.14982v1_3_3')['confidence'] == 0.72
    assert next(node for node in updated['nodes'] if node['id'] == 'lm_unit_2512.14982v1_3_6')['statement'] == 'Support is strongest for non-reasoning settings; reasoning settings show weaker and mostly neutral effects.'
    assert next(node for node in updated['nodes'] if node['id'] == 'lm_unit_2512.14982v1_3_6')['confidence'] == 0.74
    assert len(latency_nodes) == 1
    assert latency_nodes[0]['statement'] == 'Prompt repetition does not materially increase measured latency in the tested settings, except for very long requests in some Anthropic models.'
    assert updated['problems'][0]['problem_type'] == 'external_validity_caution'
    assert updated['problems'][0]['support_bundle']['evidence_ids'] == ['ev_1', 'ev_7', 'ev_13', 'ev_5', 'ev_6', 'ev_18']
    assert updated['open_questions'][0]['question_type'] == 'mechanism_open_question'
    assert updated['open_questions'][0]['support_bundle']['evidence_ids'] == ['ev_1', 'ev_21', 'ev_3', 'ev_4', 'ev_20', 'ev_17']
    assert updated['risk_notes'][0]['risk_type'] == 'deployment_extrapolation'
    assert updated['risk_notes'][0]['support_bundle']['claim_ids'] == ['cl_unit_2512.14982v1_2_2']
    assert updated['insights'][1]['support_bundle']['evidence_ids'] == ['ev_1', 'ev_21', 'ev_3', 'ev_4', 'ev_20', 'ev_17']
    assert any(item['evidence_id'] == 'ev_21' for item in updated['evidence_refs'])
    assert updated['reasoning_summary']['recommended_reading'] == 'accept_core_results_with_scope_caution'
