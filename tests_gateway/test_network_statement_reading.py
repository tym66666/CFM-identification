"""Source-statement projection and review lifecycle; synthetic fixtures only."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id_llm.network_statement_reading import VERSION, parse, make_request
from cfm_id_llm.network_statement_reading import SELECTION_VERSION, parse_selection, make_selection_request
from cfm_id_llm.network_policy_reading import reference_catalog, parse as legacy_parse
from examples.network_dispatch_reference import setup, candidate, approval_records
from examples.business_dispatch_reference import approve
from tests_gateway.test_fact_reading_revision import feedback, accept_changes


def to_wire(raw, entry):
    """Hand-authored fixture conversion, never used to rewrite live outputs."""
    wire=deepcopy(raw);a=wire.pop('assumptions');wire['version']=VERSION
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def stmt(value,source_ids):
        return dict(status='ADOPTED' if value is True else 'NOT_ADOPTED' if value is False else 'NOT_STATED',
            quotations=[dict(source_id=s,quote=refs['aliases'][s]['text']) for s in source_ids] if value is not None else [])
    wire['design_facts']=dict(assignment_rule_available=a['known_assignment_law'],network_fixed_before_treatment=a['fixed_pretreatment_network'])
    wire['scientific_statements']={name:stmt(a[old]['value'],a[old]['source_ids']) for name,old in (
        ('assignment_outcome_independence','full_vector_randomization'),('consistency','consistency'),('finite_conditional_means','finite_conditional_first_moments'))}
    sf=wire['mean_sufficiency'];wire['mean_sufficiency']=dict(stmt(sf['value'],sf['source_ids']),scope=sf['scope'],covered_nodes=sf['covered_nodes'])
    return wire


def modern(**kwargs):
    old,_,_,_=setup(**kwargs);s=intake.configure_network_fact_contract(old,VERSION)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    wire=to_wire(candidate(e,**kwargs),e)
    return s,e,dict(query_review=q,candidate=wire,request_sha256=e['request_sha256'])


def test_old_request_and_default_stay_legacy_and_new_wire_cannot_reuse_reviews(tmp_path):
    old,e,o,_=setup();old_request=intake.prepare_request(old)
    assert 'network_fact_contract' not in old.model_dump(mode='json')
    s=intake.configure_network_fact_contract(old,VERSION)
    assert intake.prepare_request(s)==old_request and s.candidate==old.candidate
    assert dispatch.prepare_reader(s,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    intake.save(s,tmp_path/'new.json');assert intake.restore(tmp_path/'new.json')==s
    with pytest.raises(ValueError):intake.configure_network_fact_contract(old,'invented')
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e2=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e2['request_sha256']!=e['request_sha256']
    assert dispatch.inspect_methods(s,'q1',query_review=q,candidate=o['candidate'],request_sha256=e['request_sha256'])['reason_code']=='STALE_FACT_READING_REQUEST'
    assert dispatch.inspect_methods(s,'q1',query_review=q,candidate=o['candidate'],request_sha256=e2['request_sha256'])['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('status,value',[('ADOPTED',True),('PROPOSED',True),('NOT_ADOPTED',False),('UNDECIDED',None),('NOT_STATED',None)])
def test_attitude_maps_to_unapproved_declaration_without_inference(status,value):
    s,e,o=modern();wire=o['candidate'];st=wire['scientific_statements']['assignment_outcome_independence'];st['status']=status
    if status=='NOT_STATED':st['quotations']=[]
    before=deepcopy(wire);result=parse(e['bundle'],wire,binding=e['fact_binding_sha256'])
    assert result['facts']['assumptions']['full_vector_randomization']['value'] is value
    assert wire==before and not result['statement_reading_receipt']['scientific_approval']
    assert not result['statement_reading_receipt']['semantic_entailment_verified']
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not r['backend_called'] and not r['answers']
    if value is None:assert r['state']=='NEEDS_INPUT'
    if value is False:assert r['state']=='ADAPTER_NOT_CONNECTED'


@pytest.mark.parametrize('change',['invent_quote','wrong_source','blank_quote','no_quote','absent_with_quote','invent_status','old_bool','missing_field','invent_scope'])
def test_malformed_or_uncited_statement_blocks_before_math(change):
    s,e,o=modern();wire=o['candidate'];st=wire['scientific_statements']['consistency']
    if change=='invent_quote':st['quotations'][0]['quote']='This sentence is not in these sources.'
    elif change=='wrong_source':st['quotations'][0]['source_id']='s9999'
    elif change=='blank_quote':st['quotations'][0]['quote']=' '
    elif change=='no_quote':st['quotations']=[]
    elif change=='absent_with_quote':st['status']='NOT_STATED'
    elif change=='invent_status':st['status']='VERIFIED'
    elif change=='old_bool':wire['scientific_statements']['consistency']={'value':True,'source_ids':[]}
    elif change=='missing_field':wire['scientific_statements'].pop('consistency')
    else:wire['mean_sufficiency'].update(status='NOT_STATED',quotations=[])
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_real_quote_is_not_an_entailment_or_scientific_approval():
    s,e,o=modern();refs=reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    key=next(k for k,r in refs['aliases'].items() if r['doc_id']=='assignment')
    o['candidate']['scientific_statements']['assignment_outcome_independence']['quotations']=[dict(source_id=key,quote=refs['aliases'][key]['text'])]
    # It is a real quote with the wrong meaning. No regex pretends to prove it.
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']
    assert r['statement_reading_receipt']['quotation_occurrence_verified']
    assert not r['statement_reading_receipt']['semantic_entailment_verified']


def test_conflicting_statements_block_even_if_another_route_does_not_need_them():
    s,e,o=modern(design='D1');wire=o['candidate'];sf=wire['mean_sufficiency'];refs=reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    other=next(k for k,r in refs['aliases'].items() if r['doc_id']=='science')
    sf['status']='CONFLICTING';sf['quotations'].append(dict(source_id=other,quote=refs['aliases'][other]['text']))
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and r['reason_code']=='CONFLICTING_SOURCE_SCIENCE_STATEMENTS'
    assert not r['backend_called'] and r['reading_candidate']==wire


@pytest.mark.parametrize('kwargs',[dict(design='D1',sufficiency=False),dict()])
def test_positive_source_statements_use_same_native_point_and_independent_replay(kwargs):
    old,e0,o0,p0=setup(**kwargs);baseline=dispatch.execute(old,'q1',**o0,**approval_records(p0))
    s,e,o=modern(**kwargs);p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and not p['backend_called']
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['state']=='POINT' and result['independent_replay']
    assert result['mathematical_claim']['target_fingerprint']==baseline['mathematical_claim']['target_fingerprint']


def test_explicit_reread_preserves_statement_contract_and_requires_change_review():
    from cfm_id.fact_reading_revision import prepare_recheck
    s,e,o=modern();sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    e2=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/scientific_statements/consistency',doc='science'))
    assert e2['state']=='READY_TO_READ' and e2['network_fact_contract']==VERSION
    body=json.loads(e2['request']['user'].split('\n\n本次只读取')[0]);assert body['output_schema']['properties']['version']['const']==VERSION
    fresh=to_wire(candidate(e2),e2);fresh['scientific_statements']['consistency']['status']='PROPOSED'
    opts=dict(query_review=o['query_review'],candidate=fresh,request_sha256=e2['request_sha256'],reading_revision=e2['reading_revision'])
    r=dispatch.inspect_methods(s,'q1',**opts);assert r['state']=='REVIEW_REQUIRED' and 'reading_change_worksheet' in r
    r2=dispatch.inspect_methods(s,'q1',**opts,change_review=accept_changes(r['reading_change_worksheet']))
    assert r2['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in r2 and not r2['backend_called']
    assert e2['reading_revision']['steps'][0]['candidate']==o['candidate']


def test_whole_case_keeps_experimental_contract_and_no_automatic_admission():
    s,e,o=modern();case_review=approve(business_case.prepare_case(s)['case_worksheet'])
    r=business_case.execute_case(s,{'q1':o},case_review=case_review,research_protocol_selected=True)
    assert not r['backend_called'] and not r['all_queries_identified']
    assert r['results'][0]['result']['statement_reading_receipt']['scientific_approval'] is False


def test_bounded_model_is_preserved_and_uses_existing_partial_replay():
    from examples.network_bounded_dispatch_reference import setup as bounded_setup, reference
    old,_,_,_=bounded_setup();s=intake.configure_network_fact_contract(old,VERSION)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    legacy=reference(e);wire=to_wire(legacy,e)
    decoded=parse(e['bundle'],wire,binding=e['fact_binding_sha256'])
    original=legacy_parse(e['bundle'],legacy,binding=e['fact_binding_sha256'])
    assert decoded['facts']==original['facts']
    opts=dict(query_review=q,candidate=wire,request_sha256=e['request_sha256']);p=dispatch.inspect_methods(s,'q1',**opts)
    r=dispatch.execute(s,'q1',**opts,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay']


def selected(**kwargs):
    old,_,_,_=setup(**kwargs)
    s=intake.configure_network_fact_contract(old,SELECTION_VERSION)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    wire=as_selection(to_wire(candidate(e,**kwargs),e))
    return s,e,dict(query_review=q,candidate=wire,request_sha256=e['request_sha256'])


def as_selection(wire):
    wire=deepcopy(wire);wire['version']=SELECTION_VERSION
    for st in [*wire['scientific_statements'].values(),wire['mean_sufficiency']]:
        st['source_ids']=list(dict.fromkeys(q['source_id'] for q in st.pop('quotations')))
    return wire


def test_selection_retrieves_exact_complete_source_without_model_copying_or_approval():
    s,e,o=selected();before=deepcopy(o['candidate'])
    r=parse_selection(e['bundle'],before,binding=e['fact_binding_sha256'])
    refs=reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    receipt=r['statement_reading_receipt'];assert not receipt['scientific_approval']
    assert not receipt['semantic_entailment_verified'] and not receipt['native_math_called']
    for name,st in receipt['statements'].items():
        candidate_st=before['mean_sufficiency'] if name=='mean_sufficiency' else before['scientific_statements'][name]
        assert st['quotations']==[dict(source_id=refs['aliases'][i]['source_id'],quote=refs['aliases'][i]['text']) for i in candidate_st['source_ids']]
    assert o['candidate']==before
    request=make_selection_request(e['bundle'],binding=e['fact_binding_sha256'])
    schema=json.loads(request['user'])['output_schema']
    assert 'SourceQuote' not in schema['$defs'] and 'quotations' not in request['system']
    assert schema['properties']['version']['const']==SELECTION_VERSION


@pytest.mark.parametrize('change',['invent_id','no_id','duplicate_id','absent_with_id','invented_quote','stale_context'])
def test_selection_malformed_or_stale_evidence_blocks(change):
    s,e,o=selected();wire=o['candidate'];st=wire['scientific_statements']['consistency']
    if change=='invent_id':st['source_ids']=['s9999']
    elif change=='no_id':st['source_ids']=[]
    elif change=='duplicate_id':st['source_ids']*=2
    elif change=='absent_with_id':st['status']='NOT_STATED'
    elif change=='invented_quote':st['quotations']=[dict(source_id=st['source_ids'][0],quote='invented')]
    else:wire['reference_context']='c000000000000'
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('status,value',[('ADOPTED',True),('PROPOSED',True),('NOT_ADOPTED',False),('UNDECIDED',None),('NOT_STATED',None)])
def test_selected_attitudes_remain_unapproved(status,value):
    s,e,o=selected();st=o['candidate']['scientific_statements']['assignment_outcome_independence'];st['status']=status
    if status=='NOT_STATED':st['source_ids']=[]
    r=parse_selection(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])
    assert r['facts']['assumptions']['full_vector_randomization']['value'] is value
    assert r['statement_reading_receipt']['statements']['assignment_outcome_independence']['status']==status
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']


def test_selected_conflict_in_one_paragraph_requires_recheck_before_point():
    s,e,o=selected(design='D1');st=o['candidate']['scientific_statements']['consistency']
    assert len(st['source_ids'])==1;st['status']='CONFLICTING'
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']
    assert r['statement_reading_receipt']['conflicts']==['consistency']


def test_wrong_meaning_source_selection_is_not_semantically_certified():
    s,e,o=selected();refs=reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    key=next(k for k,r in refs['aliases'].items() if r['doc_id']=='assignment')
    o['candidate']['scientific_statements']['assignment_outcome_independence']['source_ids']=[key]
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']
    assert not r['statement_reading_receipt']['semantic_entailment_verified']


@pytest.mark.parametrize('kwargs',[dict(design='D1',sufficiency=False),dict()])
def test_selection_preserves_point_target_and_certificate_replay(kwargs):
    old,_,o0,p0=setup(**kwargs);baseline=dispatch.execute(old,'q1',**o0,**approval_records(p0))
    s,e,o=selected(**kwargs);p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    assert r['mathematical_claim']['target_fingerprint']==baseline['mathematical_claim']['target_fingerprint']


def test_selection_preserves_bounded_partial():
    from examples.network_bounded_dispatch_reference import setup as bounded_setup, reference
    old,_,_,_=bounded_setup();s=intake.configure_network_fact_contract(old,SELECTION_VERSION)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=reference(e);wire=as_selection(to_wire(raw,e))
    assert parse_selection(e['bundle'],wire,binding=e['fact_binding_sha256'])['facts']==legacy_parse(e['bundle'],raw,binding=e['fact_binding_sha256'])['facts']
    o=dict(query_review=q,candidate=wire,request_sha256=e['request_sha256']);p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay']


def test_selection_switch_invalidates_old_reviews_and_reread_preserves_new_format(tmp_path):
    from cfm_id.fact_reading_revision import prepare_recheck
    old,e0,o0=modern();s=intake.configure_network_fact_contract(old,SELECTION_VERSION)
    assert dispatch.prepare_reader(s,'q1',query_review=o0['query_review'])['state']=='CHECK_BLOCKED'
    intake.save(s,tmp_path/'selection.json');assert intake.restore(tmp_path/'selection.json')==s
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert dispatch.inspect_methods(s,'q1',query_review=q,candidate=o0['candidate'],request_sha256=e0['request_sha256'])['reason_code']=='STALE_FACT_READING_REQUEST'
    assert dispatch.inspect_methods(s,'q1',query_review=q,candidate=o0['candidate'],request_sha256=e['request_sha256'])['state']=='CHECK_BLOCKED'
    o=dict(query_review=q,candidate=as_selection(to_wire(candidate(e),e)),request_sha256=e['request_sha256'])
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    e2=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/scientific_statements/consistency',doc='science'))
    assert e2['network_fact_contract']==SELECTION_VERSION
    fresh=as_selection(to_wire(candidate(e2),e2));fresh['scientific_statements']['consistency']['status']='PROPOSED'
    opts=dict(query_review=q,candidate=fresh,request_sha256=e2['request_sha256'],reading_revision=e2['reading_revision'])
    r=dispatch.inspect_methods(s,'q1',**opts);assert 'reading_change_worksheet' in r
    r2=dispatch.inspect_methods(s,'q1',**opts,change_review=accept_changes(r['reading_change_worksheet']))
    assert r2['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in r2 and not r2['backend_called']


def test_selection_in_whole_case_does_not_approve_science():
    s,e,o=selected();review=approve(business_case.prepare_case(s)['case_worksheet'])
    r=business_case.execute_case(s,{'q1':o},case_review=review,research_protocol_selected=True)
    assert not r['backend_called'] and not r['all_queries_identified']
    receipt=r['results'][0]['result']['statement_reading_receipt']
    assert receipt['version']==SELECTION_VERSION and not receipt['scientific_approval']
