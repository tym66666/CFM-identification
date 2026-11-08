"""Public source-referenced intake contracts. Offline fixtures, not LLM scores."""
from copy import deepcopy
import json
import pytest

from cfm_id import business_intake as work, business_dispatch as dispatch
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.compact_formulator import make_compact_request
from examples.business_dispatch_reference import from_case, approve, approvals
from examples.dag_business_reference import cases


def scenario():
    legacy, facts = from_case(cases()[0])
    case = legacy.case
    catalog = build_catalog(case)
    def claim(value, source='business_question'):
        return dict(state='STATED', value=value,
                    refs=[r['ref'] for r in catalog if r['source_id'] == source])
    raw = dict(common=dict(analysis_unit=claim(facts['target']['context'], 'context'),
        treatment=claim(facts['target']['treatment']), outcome=claim(facts['target']['outcome']),
        variable_causal_graph=claim(case.source_map()['relations'], 'relations')),
        queries=[dict(goal=claim(case.business_question), kind='INTERVENTIONAL_DISTRIBUTION',
            semantics=dict(target_population=claim(facts['target']['context'], 'context'),
                           intervention=claim(case.business_question),
                           time_horizon=claim(facts['target']['context'], 'context')))])
    return case, raw, facts


def receive(case, raw):
    s = work.start(case)
    return work.receive_candidate(s, raw, request_sha256=s.request_sha256)


def test_default_compact_binds_source_without_writing_raw_or_approving_science():
    case, raw, _ = scenario()
    before = deepcopy(raw)
    s = receive(case, raw)
    request = work.prepare_request(s)
    system, user, _ = make_compact_request(case, assignment_semantics=s.assignment_semantics)
    assert (request['system_prompt'], request['user_prompt']) == (system, user)
    report = work.inspect(s)
    assert report['state'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert raw == s.candidate == before
    draft = report['report']['draft']
    assert draft['shared_draft']['target'] == draft['queries'][0]['target']
    assert draft['shared_draft']['assumptions'] == []
    assert draft['shared_draft']['information_design']['population_information_level'] == 'UNRESOLVED'
    for quote in draft['shared_draft']['structure']['variable_causal_graph']['evidence']:
        assert quote['quote'] in case.source_map()[quote['source_id']]
    assert not report['core_called'] and report['certificate'] is None
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'REVIEW_REQUIRED'


@pytest.mark.parametrize('regime', ['UNRESOLVED', 'OBSERVATIONAL'])
def test_compact_to_actual_dag_dispatch_and_independent_replay(regime):
    case, raw, facts = scenario()
    raw['common']['assignment_family'] = regime
    s = receive(case, raw)
    reading = work.inspect(s)
    info = reading['report']['draft']['shared_draft']['information_design']
    assert info['assignment_law']['basis'] == 'UNRESOLVED'
    assert not reading['core_called'] and reading['scientific_review_required']
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'REVIEW_REQUIRED'
    s = work.configure_fact_format(s, 'source_hash')  # Legacy fact-wire compatibility.
    review = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    entry = dispatch.prepare_reader(s, 'q1', query_review=review)
    assert entry['state'] == 'READY_TO_READ'
    options = dict(query_review=review, candidate=facts, request_sha256=entry['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **options)
    result = dispatch.execute(s, 'q1', **options, **approvals(plan))
    assert result['state'] == 'POINT' and result['independent_replay'] is True
    assert not result['production_admission'] and not result['estimation_handoff_allowed']


@pytest.mark.parametrize('change', ['unknown_with_value', 'false_ref', 'cross_case_ref', 'nested', 'approval'])
def test_bad_wire_blocked_before_query_review(change):
    case, raw, _ = scenario()
    if change == 'unknown_with_value':
        raw['queries'][0]['semantics']['intervention']['state'] = 'UNKNOWN'
    elif change == 'false_ref':
        raw['queries'][0]['goal']['refs'] = ['fabricated']
    elif change == 'cross_case_ref':
        other = case.model_copy(update={'case_id': 'another'})
        raw['queries'][0]['goal']['refs'] = [build_catalog(other)[0]['ref']]
    elif change == 'nested':
        raw['queries'][0]['semantics']['intervention']['comparator'] = 'UNKNOWN'
    else:
        raw['science_review'] = dict(status='ACCEPTED')
    s = receive(case, raw)
    assert s.candidate == raw
    reading = work.inspect(s)
    assert reading['state'] == 'READING_RECHECK_REQUIRED' and not reading['core_called']
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'READING_RECHECK_REQUIRED'


def test_false_meaning_with_valid_ref_still_needs_independent_review():
    case, raw, _ = scenario()
    raw['queries'][0]['semantics']['time_horizon']['value'] = '五十年后'
    result = work.inspect(receive(case, raw))
    assert result['report']['draft']['queries'][0]['semantics']['time_horizon']['value'] == '五十年后'
    assert result['state'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert not result['wire_gate']['semantic_correctness_verified']


def test_available_population_information_is_not_a_sample_or_target_weight():
    case, raw, _ = scenario()
    refs = [r['ref'] for r in build_catalog(case) if r['source_id'] == 'information']
    raw['common']['available_information'] = dict(state='STATED',
        value=case.source_map()['information'], refs=refs)
    result = work.inspect(receive(case, raw))
    draft = result['report']['draft']
    info = draft['shared_draft']['information_design']
    assert info['population_observable_operator']['value'] == case.source_map()['information']
    assert info['population_information_level'] == 'UNRESOLVED'
    assert info['sample_data_description']['value'] is None
    assert draft['queries'][0]['semantics']['standardization_distribution']['value'] is None
    assert result['scientific_review_required'] and not result['core_called']


@pytest.mark.parametrize('count',[9,16,64])
def test_multiline_information_preserves_every_citation_without_admission(count):
    from cfm_id_llm.schemas import SourceDocument,MAX_CLAIM_EVIDENCE,SemanticClaim
    case,raw,_=scenario()
    text='\n'.join(f'研究资料第{i+1}项的总体均值声明。' for i in range(count))
    case=case.model_copy(update={'sources':[s for s in case.sources if s.source_id!='information']+
                               [SourceDocument(source_id='information',text=text)]})
    # Rebuild every original citation against the current case, without changing claims.
    old_case,old_raw,_=scenario();old={r['ref']:r for r in build_catalog(old_case)}
    new=build_catalog(case)
    by_quote={(r['source_id'],r['quote']):r['ref'] for r in new}
    def remap(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k=='refs':v[k]=[by_quote[(old[r]['source_id'],old[r]['quote'])] for r in x]
                else:remap(x)
        elif isinstance(v,list):
            for x in v:remap(x)
    remap(raw)
    refs=[r['ref'] for r in new if r['source_id']=='information']
    raw['common']['available_information']=dict(state='STATED',value=text,refs=refs)
    r=work.inspect(receive(case,raw))
    evidence=r['report']['draft']['shared_draft']['information_design']['population_observable_operator']['evidence']
    assert len(evidence)==count and [x['quote'] for x in evidence]==text.splitlines()
    assert not r['core_called'] and r['scientific_review_required']
    _,prompt,_=make_compact_request(case)
    schema=json.loads(prompt.split('\n\n输出 Schema：\n')[1])
    assert schema['$defs']['CompactClaim']['properties']['refs']['maxItems']==MAX_CLAIM_EVIDENCE
    assert SemanticClaim.model_json_schema()['properties']['evidence']['maxItems']==MAX_CLAIM_EVIDENCE
    # Extra capacity does not admit duplicated or fabricated citations.
    for invalid in ([*refs,refs[0]],[*refs[:-1],'fabricated']):
        bad=deepcopy(raw);bad['common']['available_information']['refs']=invalid
        assert work.inspect(receive(case,bad))['state']=='READING_RECHECK_REQUIRED'


def test_reference_capacity_remains_bounded_in_both_contracts():
    from pydantic import ValidationError
    from cfm_id_llm.compact_formulator import CompactClaim
    from cfm_id_llm.schemas import SemanticClaim,MAX_CLAIM_EVIDENCE
    with pytest.raises(ValidationError):
        CompactClaim(state='STATED',value='A sourced summary',refs=[f'r{i}' for i in range(MAX_CLAIM_EVIDENCE+1)])
    with pytest.raises(ValidationError):
        SemanticClaim(value='A sourced summary',basis='EXPLICIT_TEXT',evidence=[
            dict(source_id='information',quote=f'Original sentence {i}') for i in range(MAX_CLAIM_EVIDENCE+1)])


def test_request_schema_restricts_inapplicability_to_two_semantic_slots():
    case, _, _ = scenario()
    _, user, _ = make_compact_request(case)
    schema = json.loads(user.split('\n\n输出 Schema：\n')[1])
    defs = schema['$defs']
    assert 'NOT_APPLICABLE' not in defs['GroundedOrUnknownClaim']['properties']['state']['enum']
    for model in ('CompactCommon', 'CompactSemantics'):
        for field, prop in defs[model]['properties'].items():
            if field in {'assignment_family', 'covariates', 'comparator', 'policy_assignment'}:
                continue
            assert prop['anyOf'] == [{'$ref': '#/$defs/GroundedOrUnknownClaim'},
                                    {'type': 'string', 'const': 'UNKNOWN'}]


@pytest.mark.parametrize('field', ['target_population', 'intervention', 'time_horizon'])
def test_missing_coordinates_block_even_when_canonical_audit_is_ready(field):
    case, raw, _ = scenario()
    raw['queries'][0]['semantics'].pop(field)
    s = receive(case, raw)
    result = work.inspect(s)
    assert result['report']['query_quality'][0]['business_status'] == 'FORMALIZATION_READY'
    assert result['state'] == 'BUSINESS_CLARIFICATION_REQUIRED'
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'NEEDS_INPUT'
    plan = work.clarification_plan(s)
    item = next(q for q in plan['questions'] if q['field_path'].endswith(field))
    revised = work.append_reply(s, plan, item['clarification_id'], '尚未决定。')
    assert revised.candidate is None and revised.reading_format == 'compact'
    assert revised.request_sha256 != s.request_sha256
    assert revised.case.sources[-1].text == '尚未决定。'
    assert item['question'] not in revised.case.sources[-1].text


def test_network_and_variable_graph_preserved_together():
    case, raw, _ = scenario()
    raw['common']['unit_network'] = deepcopy(raw['common']['variable_causal_graph'])
    s = receive(case, raw)
    review = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    result = dispatch.prepare_reader(s, 'q1', query_review=review)
    assert result['state'] == 'ADAPTER_NOT_CONNECTED'
    assert result['reason_code'] == 'COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS'


def test_wire_recheck_cannot_be_bypassed_by_canonical_projection():
    case, raw, _ = scenario()
    raw['queries'][0]['semantics']['neighbor_exposure'] = 'NOT_APPLICABLE'
    s = receive(case, raw)
    assert work.inspect(s)['report']['query_quality'][0]['business_status'] == 'FORMALIZATION_READY'
    result = dispatch.prepare_reader(s, 'q1')
    assert result['state'] == 'READING_RECHECK_REQUIRED' and result['query_worksheet'] is None


def test_grounded_interpretation_requires_review_without_an_unresolvable_reread_loop():
    case, raw, _ = scenario()
    raw['queries'][0]['semantics']['time_horizon']['state'] = 'INTERPRETED'
    s = receive(case, raw)
    reading = work.inspect(s)
    assert reading['state'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert reading['wire_gate']['issues'][0]['code'] == 'INTERPRETATION_REQUIRES_REVIEW'
    pending = dispatch.prepare_reader(s, 'q1')
    assert pending['state'] == 'REVIEW_REQUIRED' and pending['request'] is None
    review = approve(pending['query_worksheet'])
    assert dispatch.prepare_reader(s, 'q1', query_review=review)['state'] == 'READY_TO_READ'
    rejected = review.model_copy(update={'decisions': {k:'REJECTED' for k in review.decisions}})
    assert dispatch.prepare_reader(s, 'q1', query_review=rejected)['state'] == 'CHECK_BLOCKED'
    assert s.candidate == raw and not reading['core_called']


def test_wrong_wire_format_and_mutated_format_rejected():
    legacy, _ = from_case(cases()[0])
    compact = receive(legacy.case, legacy.candidate)
    assert work.inspect(compact)['state'] == 'READING_RECHECK_REQUIRED'
    changed = legacy.model_dump(mode='json')
    changed['reading_format'] = 'compact'
    with pytest.raises(work.IntakeError, match='MATERIAL_OR_PROMPT_CHANGED'):
        work.inspect(changed)


def test_checkpoint_preserves_wire_and_old_checkpoints_keep_old_contract(tmp_path):
    case, raw, _ = scenario()
    s = receive(case, raw)
    path = tmp_path / 'compact.json'
    work.save(s, path)
    assert work.inspect(work.restore(path)) == work.inspect(s)
    assert work.restore(path).candidate == raw
    old, _ = from_case(cases()[0])
    payload = old.model_dump(mode='json')
    del payload['reading_format']
    path = tmp_path / 'old.json'
    work.write_json(path, dict(kind='BUSINESS_INTAKE_CHECKPOINT', payload=payload, sha256=work._sha(payload)))
    restored = work.restore(path)
    assert restored.reading_format == 'canonical'
    assert work.inspect(restored)['state'] == 'SEMANTIC_REVIEW_REQUIRED'


def test_multiple_queries_kept_and_missing_second_does_not_block_ready_first():
    case, raw, _ = scenario()
    raw['queries'].append(deepcopy(raw['queries'][0]))
    raw['queries'][0]['goal']['value'] = '培训设为0时的达标分布'
    raw['queries'][1]['goal']['value'] = '培训设为1时的达标分布'
    raw['queries'][1]['semantics']['target_population'] = 'UNKNOWN'
    s = receive(case, raw)
    assert [q['query_id'] for q in work.inspect(s)['report']['draft']['queries']] == ['q1', 'q2']
    assert dispatch.prepare_reader(s, 'q1')['state'] == 'REVIEW_REQUIRED'
    assert dispatch.prepare_reader(s, 'q2')['state'] == 'NEEDS_INPUT'
