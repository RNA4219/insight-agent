from insight_core.response_builder import build_failure_response, build_response
from insight_core.schemas import (
    AssumptionItem,
    ClaimItem,
    Constraints,
    Decision,
    DerivationType,
    EpistemicMode,
    EvidenceRef,
    FailureItem,
    InsightItem,
    LimitationItem,
    NormalizedRequest,
    OpenQuestionItem,
    Options,
    PersonaScore,
    PersonaSource,
    ProblemCandidateItem,
    ProblemScope,
    ProblemType,
    RunStatus,
    Source,
    UpdateRule,
)


def _build_request(include_intermediate_items: bool) -> NormalizedRequest:
    return NormalizedRequest(
        run_id='run_test',
        request_id='req_test',
        sources=[Source(source_id='src_1', content='demo')],
        constraints=Constraints(max_problem_candidates=5, max_insights=3),
        personas=[],
        persona_source=PersonaSource.DEFAULT,
        persona_catalog_version='default_personas.v4',
        context={},
        options=Options(include_intermediate_items=include_intermediate_items),
    )


def _build_claim(claim_id: str, evidence_id: str) -> ClaimItem:
    return ClaimItem(
        id=claim_id,
        statement=f'claim {claim_id}',
        epistemic_mode=EpistemicMode.OBSERVATION,
        derivation_type=DerivationType.DIRECT,
        confidence=0.9,
        evidence_refs=[evidence_id],
        update_rule=UpdateRule.RETAIN,
    )


def _build_assumption(assumption_id: str, evidence_id: str) -> AssumptionItem:
    return AssumptionItem(
        id=assumption_id,
        statement=f'assumption {assumption_id}',
        epistemic_mode=EpistemicMode.INTERPRETATION,
        derivation_type=DerivationType.INFERRED,
        confidence=0.8,
        evidence_refs=[evidence_id],
        update_rule=UpdateRule.RETAIN,
    )


def _build_limitation(limitation_id: str, evidence_id: str) -> LimitationItem:
    return LimitationItem(
        id=limitation_id,
        statement=f'limitation {limitation_id}',
        epistemic_mode=EpistemicMode.INTERPRETATION,
        derivation_type=DerivationType.INFERRED,
        confidence=0.7,
        evidence_refs=[evidence_id],
        update_rule=UpdateRule.RETAIN,
    )


def _build_candidate() -> ProblemCandidateItem:
    return ProblemCandidateItem(
        id='pb_001',
        statement='評価境界が曖昧なため、主張の一般化条件がまだ固まっていない',
        problem_type=ProblemType.EVALUATION_GAP,
        scope=ProblemScope.SYSTEM,
        epistemic_mode=EpistemicMode.HYPOTHESIS,
        derivation_type=DerivationType.INFERRED,
        confidence=0.8,
        parent_refs=['cl_keep'],
        assumption_refs=['as_keep'],
        limitation_refs=['lm_keep'],
        persona_scores=[
            PersonaScore(
                persona_id='detective',
                axis_scores={'evidence_grounding': 0.8},
                weighted_score=0.8,
                applied_weight=1.0,
                decision=Decision.NEEDS_MORE_EVIDENCE,
                reason_summary='needs more evidence',
            )
        ],
        decision=Decision.NEEDS_MORE_EVIDENCE,
        update_rule=UpdateRule.RETAIN,
    )


def _build_evidence_refs() -> list[EvidenceRef]:
    return [
        EvidenceRef(evidence_id='ev_keep', source_id='src_1', quote='keep'),
        EvidenceRef(evidence_id='ev_drop', source_id='src_1', quote='drop'),
        EvidenceRef(evidence_id='ev_as_keep', source_id='src_1', quote='assumption keep'),
        EvidenceRef(evidence_id='ev_as_drop', source_id='src_1', quote='assumption drop'),
        EvidenceRef(evidence_id='ev_lm_keep', source_id='src_1', quote='limitation keep'),
    ]


def test_build_response_compacts_intermediate_items_by_default():
    response = build_response(
        normalized_request=_build_request(include_intermediate_items=False),
        claims=[_build_claim('cl_keep', 'ev_keep'), _build_claim('cl_drop', 'ev_drop')],
        assumptions=[_build_assumption('as_keep', 'ev_as_keep'), _build_assumption('as_drop', 'ev_as_drop')],
        limitations=[_build_limitation('lm_keep', 'ev_lm_keep')],
        problem_candidates=[_build_candidate()],
        insights=[],
        open_questions=[
            OpenQuestionItem(
                question_id='oq_pb_001',
                statement='この評価設定が他のデータ条件でも維持されるかは未確認',
                confidence=0.4,
                parent_refs=['pb_001'],
                evidence_refs=[],
            )
        ],
        evidence_refs=_build_evidence_refs(),
        failures=[],
        confidence=0.7,
        status=RunStatus.PARTIAL,
    )

    assert [item.id for item in response.claims] == ['cl_keep']
    assert [item.id for item in response.assumptions] == ['as_keep']
    assert [item.id for item in response.limitations] == ['lm_keep']
    assert [item.evidence_id for item in response.evidence_refs] == ['ev_keep', 'ev_as_keep', 'ev_lm_keep']
    assert response.problem_candidates[0].persona_scores[0].axis_scores == {}
    assert response.reasoning_summary is not None
    assert response.reasoning_summary.short_text == (
        '有力な仮説: 評価境界が曖昧なため、主張の一般化条件がまだ固まっていない。'
        '残る論点: この評価設定が他のデータ条件でも維持されるかは未確認。'
    )


def test_build_response_dedupes_same_reasoning_topic():
    response = build_response(
        normalized_request=_build_request(include_intermediate_items=False),
        claims=[_build_claim('cl_keep', 'ev_keep')],
        assumptions=[_build_assumption('as_keep', 'ev_as_keep')],
        limitations=[_build_limitation('lm_keep', 'ev_lm_keep')],
        problem_candidates=[_build_candidate()],
        insights=[],
        open_questions=[
            OpenQuestionItem(
                question_id='oq_pb_001',
                statement='評価境界が曖昧なため、主張の一般化条件がまだ固まっていない - 追加の検証が必要',
                confidence=0.4,
                parent_refs=['pb_001'],
                evidence_refs=[],
            )
        ],
        evidence_refs=_build_evidence_refs(),
        failures=[],
        confidence=0.7,
        status=RunStatus.PARTIAL,
    )

    assert response.reasoning_summary is not None
    assert response.reasoning_summary.short_text == '有力な仮説: 評価境界が曖昧なため、主張の一般化条件がまだ固まっていない。'


def test_build_response_keeps_intermediate_items_when_requested():
    response = build_response(
        normalized_request=_build_request(include_intermediate_items=True),
        claims=[_build_claim('cl_keep', 'ev_keep'), _build_claim('cl_drop', 'ev_drop')],
        assumptions=[_build_assumption('as_keep', 'ev_as_keep'), _build_assumption('as_drop', 'ev_as_drop')],
        limitations=[_build_limitation('lm_keep', 'ev_lm_keep')],
        problem_candidates=[_build_candidate()],
        insights=[
            InsightItem(
                id='ins_001',
                statement='比較対象が狭いため優位性の主張は限定的である',
                epistemic_mode=EpistemicMode.HYPOTHESIS,
                derivation_type=DerivationType.INFERRED,
                confidence=0.72,
                evidence_refs=['ev_keep'],
                update_rule=UpdateRule.RETAIN,
            )
        ],
        open_questions=[],
        evidence_refs=_build_evidence_refs(),
        failures=[],
        confidence=0.7,
        status=RunStatus.PARTIAL,
    )

    assert len(response.claims) == 2
    assert len(response.assumptions) == 2
    assert len(response.evidence_refs) == 5
    assert response.problem_candidates[0].persona_scores[0].axis_scores == {'evidence_grounding': 0.8}
    assert response.reasoning_summary is not None
    assert response.reasoning_summary.short_text == '見立て: 比較対象が狭いため優位性の主張は限定的である。'


def test_build_failure_response_includes_reasoning_summary():
    response = build_failure_response(
        normalized_request=_build_request(include_intermediate_items=False),
        failures=[
            FailureItem(
                failure_id='fail_001',
                stage='extractor',
                reason='timeout',
                suggested_next_action='retry',
            )
        ],
    )

    assert response.reasoning_summary is not None
    assert response.reasoning_summary.short_text == '有力な仮説は未確定。再試行が必要です。'
