"""Ordered comparison bridge, real native certificates and fail-closed cases."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id import network_contrast_dispatch as contrast
from cfm_id_llm import network_contrast_reading as reading
from tests_gateway._reading_contract_checks import NATIVE_PROFILES
from examples.network_contrast_dispatch_reference import setup, material, a0_reference, fact_reference, approval_records
from examples.business_dispatch_reference import approve


def plan_and_execute(s, options):
    plan=dispatch.inspect_methods(s,'q1',**options)
    assert plan['state']=='REVIEW_REQUIRED', plan.get('reason_code')
    result=dispatch.execute(s,'q1',**options,**approval_records(plan))
    return plan,result


@pytest.mark.parametrize('profile',NATIVE_PROFILES)
@pytest.mark.parametrize('kind,expected', [('point','POINT'),('partial','PARTIAL'),('cancellation','POINT')])
def test_representative_protocols_keep_sources_and_native_certificates(profile,kind,expected):
    s,e,o=setup(kind,profile=profile,bounds=('1/4','3/4') if kind=='partial' else ('0','1'))
    before=deepcopy(o['candidate'])
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(before)
    assert e['reader_id']==contrast.FAMILY
    assert 'NETWORK_FIXED_POLICY_FACTS' not in body['source_catalog']
    waiting=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert waiting['state']=='REVIEW_REQUIRED' and not waiting['backend_called']
    p,r=plan_and_execute(s,o)
    assert r['state']==expected and r['independent_replay'] and r['answers']
    assert not r['production_admission'] and not r['estimation_handoff_allowed']
    assert not r['partial_fallback_performed'] and o['candidate']==before
    assert all(v=='PENDING' for v in p['plan_worksheet']['decisions'].values())
    if kind=='partial':assert r['mathematical_claim']['interval']==['-1/2','1/2']
    if kind=='cancellation':assert r['mathematical_claim']['interval']==['1/5','1/5']
    if kind=='point':assert r['certificate']['verification']=='TWO_CORE_REPLAYS_AND_SIGNED_COMPOSITION'


@pytest.mark.parametrize('profile,mutation,state',[(None,*case) for case in [
    ('missing_first','NEEDS_INPUT'),('missing_second','NEEDS_INPUT'),('partial_assignment','NEEDS_INPUT'),
    ('missing_population','NEEDS_INPUT'),('different_population','ADAPTER_NOT_CONNECTED'),
    ('unknown_direction','NEEDS_INPUT'),('different_context','ADAPTER_NOT_CONNECTED'),
    ('unknown_context','NEEDS_INPUT'),('weighted_target','ADAPTER_NOT_CONNECTED'),
    ('other_target','ADAPTER_NOT_CONNECTED'),('missing_direction_source','NEEDS_INPUT'),
    ('unknown_source','CHECK_BLOCKED'),('wrong_context_binding','CHECK_BLOCKED'),
    ('assumption_unknown','NEEDS_INPUT'),('assumption_denied','ADAPTER_NOT_CONNECTED'),
    ('sample_only','NEEDS_INPUT'),('extra_model','ADAPTER_NOT_CONNECTED'),
    ('unconfirmed_model','NEEDS_INPUT'),('missing_bounds','NEEDS_INPUT'),('incomplete_information','NEEDS_INPUT'),
]]+[( 'network-source-selections-alignment-1',*case) for case in [
    ('different_population','ADAPTER_NOT_CONNECTED'),('unknown_direction','NEEDS_INPUT'),('different_context','ADAPTER_NOT_CONNECTED'),
]])
def test_missing_conflicting_or_unsupported_comparison_blocks_before_compilation(monkeypatch,profile,mutation,state):
    s,e,o=setup('partial',profile=profile);c=o['candidate'];t=c['target']
    if mutation=='missing_first':t['first']['assignment']=None
    elif mutation=='missing_second':t['second']['assignment']=None
    elif mutation=='partial_assignment':t['second']['assignment'].pop('丁店')
    elif mutation=='missing_population':t['second']['population']=None
    elif mutation=='different_population':t['second']['population']=['甲店']
    elif mutation=='unknown_direction':t['operation']='UNKNOWN'
    elif mutation=='different_context':t['shared_outcome_and_context']['value']=False
    elif mutation=='unknown_context':t['shared_outcome_and_context']['value']=None
    elif mutation=='weighted_target':t['first']['aggregation']='OTHER'
    elif mutation=='other_target':t['kind']='OTHER'
    elif mutation=='missing_direction_source':t['source_ids']=[]
    elif mutation=='unknown_source':t['source_ids']=['s9999']
    elif mutation=='wrong_context_binding':c['reference_context']='c000000000000'
    elif mutation=='assumption_unknown':c['assumptions']['consistency']['value']=None
    elif mutation=='assumption_denied':c['assumptions']['consistency']['value']=False
    elif mutation=='sample_only':c['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    elif mutation=='extra_model':c['additional_restrictions']=[dict(text='另有跨对象均值相等的条件需要保留。',source_ids=t['source_ids'])]
    elif mutation=='unconfirmed_model':c['bounded_model']['no_additional_coupling_constraints']['value']=None
    elif mutation=='missing_bounds':c['bounded_model']['bounds'].pop()
    elif mutation=='incomplete_information':c['bounded_model']['listed_means_are_complete_information']['value']=None
    monkeypatch.setattr(contrast,'_compile_pair',lambda *a,**kw:pytest.fail('blocked before native compilation'))
    before=deepcopy(c)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==state, r.get('reason_code')
    assert not r['backend_called'] and r['mathematical_claim'] is None and c==before


@pytest.mark.parametrize('layer',['plan','reading','science'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_each_independent_review_layer_blocks_all_math(monkeypatch,layer,decision):
    s,e,o=setup('point');p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    key=p['methods'][0]['method']
    r=a['plan_review'] if layer=='plan' else a['native_reviews'][key][layer+'_review']
    r.decisions[next(iter(r.decisions))]=decision
    monkeypatch.setattr(contrast,'_compile_pair',lambda *a,**kw:pytest.fail('unreviewed'))
    result=dispatch.execute(s,'q1',**o,**a)
    assert result['state']==('REVIEW_REQUIRED' if decision=='PENDING' else 'CHECK_BLOCKED')
    assert not result['backend_called']


def test_reversed_direction_requires_new_reviews_and_negates_the_joint_answer():
    s,e,o=setup('cancellation');p,r=plan_and_execute(s,o);a=approval_records(p)
    changed=deepcopy(o);t=changed['candidate']['target'];t['first'],t['second']=t['second'],t['first']
    blocked=dispatch.execute(s,'q1',**changed,**a)
    assert blocked['state']=='CHECK_BLOCKED' and not blocked['backend_called']
    # Same-session resubmission is distinct from opening a fresh reversed case.
    _,reapproved=plan_and_execute(s,changed)
    assert reapproved['independent_replay'] and reapproved['mathematical_claim']['interval']==['-1/5','-1/5']
    assert reapproved['mathematical_claim']['target_sha256']!=r['mathematical_claim']['target_sha256']
    s2,e2,o2=setup('cancellation',reverse=True);_,opposite=plan_and_execute(s2,o2)
    assert r['mathematical_claim']['interval']==['1/5','1/5']
    assert opposite['mathematical_claim']['interval']==['-1/5','-1/5']
    assert r['independent_replay'] and opposite['independent_replay']
    assert r['certificate']['target_sha256']!=opposite['certificate']['target_sha256']


def test_cancellation_is_joint_not_subtraction_of_separate_bounds(monkeypatch):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',lambda *a,**kw:pytest.fail('no endpoint interval solving'))
    s,_,o=setup('cancellation');_,r=plan_and_execute(s,o)
    assert r['mathematical_claim']['interval']==['1/5','1/5']
    # The two individual ranges would yield the strictly wider [-3/10,7/10].
    assert r['mathematical_claim']['interval']!=['-3/10','7/10']


def test_cancelled_supported_cell_does_not_create_a_spurious_a4_gap():
    s,_,o=setup('partial');t=o['candidate']['target']
    for side in ('first','second'):t[side]['assignment']=dict(zip(t[side]['assignment'],[1,1,0,0]))
    o['candidate']['information'][0]['signature_cells'].pop(0)
    _,r=plan_and_execute(s,o)
    assert r['state']=='POINT' and r['mathematical_claim']['interval']==['0','0']


def test_all_a4_is_checked_even_if_the_contrast_cancels():
    s,_,o=setup('partial');t=o['candidate']['target'];t['second']=deepcopy(t['first'])
    o['candidate']['bounded_model']['bounds'][0].update(lower='3/4',upper='1')
    _,r=plan_and_execute(s,o)
    assert r['state']=='INCOMPATIBLE' and r['mathematical_claim'] is None
    assert not r['independent_replay'] and not r['incompatibility_proved']


def test_no_automatic_bounds_after_r1b_support_failure(monkeypatch):
    from cfm_id import bounded_contrast_solver
    monkeypatch.setattr(bounded_contrast_solver,'solve',lambda *a,**kw:pytest.fail('no fallback'))
    s,_,o=setup('point')
    o['candidate']['target']['first']['assignment']={k:1 for k in o['candidate']['study']['nodes']}
    _,r=plan_and_execute(s,o)
    assert r['state']=='UNSUPPORTED' and not r['nonidentification_proved']
    assert not r['partial_fallback_performed'] and r['mathematical_claim'] is None


@pytest.mark.parametrize('kind',['point','partial'])
def test_external_review_cannot_expand_existing_synthetic_comparison_scope(kind):
    s,e,o=setup(kind)
    query=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']).model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    e=dispatch.prepare_reader(s,'q1',query_review=query)
    _,data=material(kind)
    o=dict(query_review=query,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    a['plan_review']=a['plan_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    for pair in a['native_reviews'].values():
        for k,v in pair.items():pair[k]=v.model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']


@pytest.mark.parametrize('kind',['point','partial'])
def test_tampered_native_proof_or_other_target_is_rejected(monkeypatch,kind):
    if kind=='point':
        from cfm_id import fixed_comparison as producer
        original=producer.compose
        def changed(*a,**kw):
            r=original(*a,**kw);r['terms'][0]['coefficient']='99';return r
        monkeypatch.setattr(producer,'compose',changed)
    else:
        from cfm_id import bounded_contrast_solver as producer
        original=producer.solve
        def changed(*a,**kw):
            r=original(*a,**kw);r['upper']='99';return r
        monkeypatch.setattr(producer,'solve',changed)
    s,_,o=setup(kind);_,r=plan_and_execute(s,o)
    assert r['state']=='CHECK_BLOCKED' and r['mathematical_claim'] is None and not r['independent_replay']


def test_wrong_native_point_target_does_not_pass_its_own_valid_certificate(monkeypatch):
    from dataclasses import replace
    from pfn_pipeline import identification_business as core
    from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
    original=core.identify_network_business_query
    def other(inquiry):
        # Return a real, valid proof for the other supported two-store policy.
        target=fixed_policy_target_from_context(inquiry.study,
            tuple(1-x for x in inquiry.target.policy_assignment),
            unit_weights=inquiry.target.unit_weights,authority='TRUSTED_FIXTURE')
        return original(replace(inquiry,target=target))
    monkeypatch.setattr(core,'identify_network_business_query',other)
    s,_,o=setup();_,r=plan_and_execute(s,o)
    assert r['state']=='CHECK_BLOCKED' and r['reason_code']=='CONTRAST_ENDPOINT_INPUT_MISMATCH'


def test_whole_case_does_not_count_a_single_comparison_as_two_queries(tmp_path):
    s,e,o=setup('cancellation');p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    r=business_case.execute_case(s,{'q1':row},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert r['state']=='ALL_QUERIES_IDENTIFIED' and r['identified_query_ids']==['q1']
    assert len(r['results'])==1 and r['all_queries_point_identified']
    intake.save(s,tmp_path/'comparison.json')
    restored=intake.restore(tmp_path/'comparison.json')
    assert dispatch.prepare_reader(restored,'q1',query_review=o['query_review'])==e


def test_short_reference_recheck_keeps_contrast_target_and_requires_change_review():
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback
    s,e,o=setup('point');w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    assert '/target/second/assignment' in w['field_paths']
    revised=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/target/second/assignment',doc='__question__'))
    assert revised['reader_id']==contrast.FAMILY and revised['request_sha256']!=e['request_sha256']
    _,data=material('point')
    raw=fact_reference(revised,data);raw['target']['second']['assignment']=None
    r=dispatch.inspect_methods(s,'q1',query_review=o['query_review'],candidate=raw,
        request_sha256=revised['request_sha256'],reading_revision=revised['reading_revision'])
    assert 'reading_change_worksheet' in r and not r['backend_called']


def test_source_statement_conflict_still_requires_recheck():
    s,e,o=setup('partial',profile='network-source-selections-information-1')
    o['candidate']['scientific_statements']['consistency']['status']='CONFLICTING'
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']


def test_valid_joint_certificate_for_reversed_pair_is_rejected(monkeypatch):
    from cfm_id import bounded_contrast_solver as producer
    original=producer.solve
    def wrong(inquiries,information):
        return original({s:inquiries['second' if s=='first' else 'first'] for s in reading.SIDES},
                        {s:information['second' if s=='first' else 'first'] for s in reading.SIDES})
    monkeypatch.setattr(producer,'solve',wrong)
    s,_,o=setup('cancellation');_,r=plan_and_execute(s,o)
    assert r['state']=='CHECK_BLOCKED' and r['reason_code']=='JOINT_CONTRAST_INPUT_OR_REPLAY_MISMATCH'


def test_endpoint_note_reviews_preserve_notes_and_cannot_grant_science():
    s,e,o=setup('point')
    o['candidate']['unresolved']=[dict(text='支持问题应由数学模块核对。',source_ids=o['candidate']['target']['source_ids'])]
    before=deepcopy(o['candidate'])
    p=dispatch.inspect_methods(s,'q1',**o)
    reviews={}
    for side,endpoint in p['endpoint_plans'].items():
        w=endpoint['note_review_worksheet']
        assert w is not None
        reviews[side]=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',
            reviewer='Independent synthetic reviewer',evidence='Compared the original source and the full current candidate.',
            decisions={n:dict(disposition='DEFER_TO_MATHEMATICS',reason='The source explicitly defines the policies; support is a mathematical check.',
                source_ids=list(w['source_catalog'])) for n in w['notes']})
    o['note_review']=reviews
    p=dispatch.inspect_methods(s,'q1',**o)
    assert 'plan_worksheet' in p and not p['backend_called']
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']
    assert o['candidate']==before
    reviews['second']['decisions']['n0001']['disposition']='MATERIAL_GAP'
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called']
