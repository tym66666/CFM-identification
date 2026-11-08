"""R3 signature entry: explicit admission, unchanged native proof, old wire.

Hand-authored readings exercise contracts. These are not LLM evaluations.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as d, business_intake as intake, business_case
from cfm_id import network_observational_policy_dispatch as r3, method_diagnostics as diagnostic
from cfm_id import fact_source_review as source, fact_reading_revision as revision
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import network_observational_signature_reading as reader, fact_reading_contracts as registry
from cfm_id_llm import network_observational_policy_reading as legacy_reader
from cfm_id_llm.wire_type_diagnostics import diagnose
from examples.network_observational_signature_reference import setup, fact_reference, material, approval_records, approve
from examples.network_observational_policy_reference import setup as legacy_setup
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback, accept_changes


def execute(s,o):
    plan=d.inspect_methods(s,'q1',**o)
    reviews=approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
    result=d.execute(s,'q1',**o,**reviews)
    return plan,reviews,result


def forbidden(*args,**kwargs):
    pytest.fail('Blocked or read-only path called the mathematical backend')


@pytest.mark.parametrize('grouping,subset',[
    ('STRICT_MAJORITY_TIES_LOW',False),('THREE_LEVEL_TREATED_NEIGHBOR_FRACTION',False),
    ('PRETREATMENT_CORE_COLLABORATOR_MAJORITY',False),('EXACT_TREATED_NEIGHBOR_COUNT',True),
    ('ANY_TREATED_NEIGHBOR',False)])
def test_registered_signature_groupings_keep_target_and_native_replay(grouping,subset):
    s,e,o=setup(grouping=grouping,subset=subset);raw=deepcopy(o['candidate'])
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    Draft202012Validator(schema).validate(raw)
    o['source_review']=record(source.prepare(e,raw))
    p,a,r=execute(s,o)
    assert r['state']=='POINT' and r['primary_method']==r3.SIGNATURE_METHOD and r['independent_replay']
    assert o['candidate']==raw and not r['production_admission'] and not r['estimation_handoff_allowed']
    certificate=r['certificate'];native=r['answers'][0]['native_evidence']
    assert certificate['target_observational_probability']=='0'
    assert all(Fraction(row['support'])>0 for row in certificate['classes'])
    assert [row['node'] for row in certificate['classes']]==raw['target']['population']
    assert native['target']['policy_assignment']==[1]*5
    assert native['sufficiency']['covered_nodes']==raw['mean_sufficiency']['covered_nodes']
    assert json.loads(native['target']['context'])['fixed_pretreatment_W']==raw['conditioning']['definition']
    view=diagnostic.describe(p,result=r,plan_review=a['plan_review'],native_reviews=a['native_reviews'])
    item=next(x for x in view['methods'] if x['method']==r3.SIGNATURE_METHOD)
    assert item['signature_support']['state']=='NATIVE_POSITIVE_SUPPORT_REPORTED'
    assert item['joint_policy_support']['probability']=='0' and not item['signature_support']['checked_here']
    assert not view['is_certificate'] and not view['independent_replay']
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']==r


@pytest.mark.parametrize('value',[None,False,True])
def test_supported_full_policy_does_not_require_signature_license(value):
    s,e,o=setup(full_support=True,sufficiency=value)
    p,a,r=execute(s,o)
    assert r['state']=='POINT' and r['primary_method']==r3.METHOD
    assert p['facts']['mean_sufficiency']['value'] is value
    assert not set(r3.SIGNATURE_SCIENCE_DECISIONS)&set(p['methods'][0]['science_worksheet']['decisions'])
    assert r['answers'][0]['native_evidence']['sufficiency'] is None
    assert 'mean_signature_sufficiency' not in r['certificate']['assumptions_used']


@pytest.mark.parametrize('defect,expected',[
    ('undecided','NEEDS_INPUT'),('refused','ADAPTER_NOT_CONNECTED'),('exchangeability','NEEDS_INPUT'),
    ('sample','NEEDS_INPUT'),('scope','ADAPTER_NOT_CONNECTED'),('population','NEEDS_INPUT'),
    ('exposure','NEEDS_INPUT'),('cores','NEEDS_INPUT'),('policy','NEEDS_INPUT'),
    ('context','NEEDS_INPUT'),('extra','ADAPTER_NOT_CONNECTED'),('citation','CHECK_BLOCKED')])
def test_missing_refused_or_incompatible_conditions_never_call_core(monkeypatch,defect,expected):
    kwargs=({'undecided':dict(sufficiency=None),'refused':dict(sufficiency=False),
             'exchangeability':dict(exchangeability=None),'sample':dict(sample_only=True)}).get(defect,{})
    s,e,o=setup(**kwargs);raw=o['candidate']
    if defect=='scope':raw['mean_sufficiency']['scope']='OTHER'
    if defect=='population':raw['mean_sufficiency']['covered_nodes']=raw['study']['nodes'][1:]
    if defect=='exposure':raw['exposure'].update(kind='UNKNOWN',source_ids=[])
    if defect=='cores':raw['exposure'].update(kind='PRETREATMENT_CORE_COLLABORATOR_MAJORITY',core_collaborators=None)
    if defect=='policy':raw['target']['assignment'].pop(raw['study']['nodes'][0])
    if defect=='context':raw['conditioning']['definition']=None
    if defect=='extra':raw['additional_restrictions']=[dict(text='另有跨门店均值相等约束',source_ids=raw['mean_sufficiency']['source_ids'])]
    if defect=='citation':raw['mean_sufficiency']['source_ids']=[]
    monkeypatch.setattr(r3,'_compile',forbidden)
    p,a,r=execute(s,o)
    assert r['state']==expected and not r['backend_called'] and not r['independent_replay']
    assert r['mathematical_claim'] is None


@pytest.mark.parametrize('layer,key',[
    ('reading',r3.SIGNATURE_READING_DECISIONS[0]),('science',r3.SIGNATURE_SCIENCE_DECISIONS[0]),
    ('science','full_vector_conditional_exchangeability')])
@pytest.mark.parametrize('state',['PENDING','REJECTED'])
def test_declarations_cannot_approve_themselves(monkeypatch,layer,key,state):
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    a['native_reviews'][r3.SIGNATURE_METHOD][layer+'_review'].decisions[key]=state
    monkeypatch.setattr(r3,'_compile',forbidden)
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if state=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and not r['answers']


def test_signature_zero_support_is_no_nonidentification_proof():
    s,e,o=setup(zero_signature=True);p,a,r=execute(s,o)
    assert r['state']=='UNSUPPORTED' and r['reason_code']=='ZERO_OBSERVATIONAL_SIGNATURE_SUPPORT'
    assert not r['nonidentification_proved'] and not r['partial_fallback_performed']
    view=diagnostic.describe(p,result=r,plan_review=a['plan_review'],native_reviews=a['native_reviews'])
    assert next(x for x in view['methods'] if x['method']==r3.SIGNATURE_METHOD)['signature_support']['state']=='NATIVE_ZERO_SUPPORT_REPORTED'


@pytest.mark.parametrize('defect',['replay','sufficiency_scope','fixed_context','exposure'])
def test_native_evidence_cannot_change_reviewed_problem(monkeypatch,defect):
    from pfn_pipeline import identification_business as core
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    if defect=='replay':monkeypatch.setattr(core,'replay_verified_business_outcome',lambda r:False)
    else:
        original=core.identify_network_business_query
        def changed(inquiry):
            result=original(inquiry);r=result.result
            if defect=='sufficiency_scope':r=replace(r,sufficiency=replace(r.sufficiency,covered_nodes=r.sufficiency.covered_nodes[1:]))
            elif defect=='fixed_context':r=replace(r,target=replace(r.target,context='different W'))
            else:r=replace(r,signature=replace(r.signature,grouping='any_treated_neighbor',signature_fingerprint=''))
            return replace(result,result=r)
        monkeypatch.setattr(core,'identify_network_business_query',changed)
    result=d.execute(s,'q1',**o,**a)
    assert result['state']=='CHECK_BLOCKED' and not result['answers'] and not result['independent_replay']


def test_legacy_schema_and_profile_restore_and_unknown_profile_reject(tmp_path):
    s,e,o=legacy_setup();assert 'observational_fact_profile' not in s.model_dump(mode='json')
    c=registry.contract_for_entry(e)
    assert c.model is legacy_reader.ObservationalPolicyReading
    assert 'exposure' not in json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']['properties']
    assert execute(s,o)[2]['primary_method']==r3.METHOD
    s,e,o=setup();path=tmp_path/'intake.json';intake.save(s,path)
    restored=intake.restore(path)
    assert d.prepare_reader(restored,'q1',query_review=o['query_review'])==e
    assert execute(restored,o)[2]['independent_replay']
    with pytest.raises(ValueError):ReadingConfig(observational_fact_profile='unregistered')
    with pytest.raises(ValueError):ReadingConfig(observational_fact_profile=reader.PROFILE,fact_format='source_hash')
    assert 'observational_fact_profile' not in ReadingConfig().model_dump(mode='json')


def test_explicit_recheck_keeps_profile_and_invalidates_prior_reviews():
    s,e,o=setup();old=d.inspect_methods(s,'q1',**o);old_reviews=approval_records(old)
    bad=deepcopy(o['candidate']);bad['mean_sufficiency']['scope']='INVALID'
    assert any(x['field_path']=='/mean_sufficiency/scope' for x in diagnose(e,bad))
    args=dict(o,candidate=bad);w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    new=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/mean_sufficiency/scope',kind='WIRE_FORMAT_ERROR',doc='sufficiency'))
    assert new['state']=='READY_TO_READ' and new['observational_fact_profile']==reader.PROFILE
    assert reader.SUFFICIENCY_DESCRIPTION in new['request']['user']
    _,data=material();fresh=fact_reference(new,data)
    args=dict(query_review=o['query_review'],candidate=fresh,request_sha256=new['request_sha256'],reading_revision=new['reading_revision'])
    plan=d.inspect_methods(s,'q1',**args)
    args['change_review']=accept_changes(plan['reading_change_worksheet'])
    assert d.execute(s,'q1',**args,**old_reviews)['state']=='CHECK_BLOCKED'
    assert execute(s,args)[2]['independent_replay']


def test_signature_profile_retains_reviewed_background_handoff():
    from cfm_id_llm import query_conditioning_contract as conditioning
    from cfm_id_llm.evidence_refs import build_catalog
    from tests_gateway.test_inline_evidence_slots import wire, receive
    from tests_gateway.test_business_field_review import sheet, record as field_record, submit
    from examples.network_observational_signature_reference import a0_reference
    case,data=material();raw=wire(a0_reference(case,data))
    refs=[r['ref'] for r in build_catalog(case) if r['source_id']=='conditioning']
    raw['queries'][0]['semantics'][conditioning.FIELD]=dict(state='STATED',value=data['conditioning'],refs=refs)
    s=receive(case,raw,profile=conditioning.CONTRACT)
    s=intake._checked(s.model_copy(update=dict(observational_fact_profile=reader.PROFILE)))
    review=submit(s,field_record(sheet(s)))['query_review']
    e=d.prepare_reader(s,'q1',query_review=review)
    o=dict(query_review=review,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p,a,r=execute(s,o)
    assert r['state']=='POINT' and r['primary_method']==r3.SIGNATURE_METHOD
    assert conditioning.MATCH_DECISION in p['methods'][0]['reading_worksheet']['decisions']
    a['native_reviews'][r3.SIGNATURE_METHOD]['reading_review'].decisions[conditioning.MATCH_DECISION]='REJECTED'
    assert not d.execute(s,'q1',**o,**a)['backend_called']


def test_source_review_rejects_semantically_wrong_citation_and_diagnostic_never_reexecutes(monkeypatch):
    s,e,o=setup();review=record(source.prepare(e,o['candidate']))
    review['decisions']['/mean_sufficiency']['source_coverage']='REJECTED'
    r=d.execute(s,'q1',**dict(o,source_review=review),research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']
    p,a,r=execute(s,o)
    monkeypatch.setattr(r3,'_compile',forbidden)
    view=diagnostic.describe(p,result=r,plan_review=a['plan_review'],native_reviews=a['native_reviews'])
    assert not view['is_certificate']
    broken=deepcopy(r);broken['answers'][0]['certificate']['signature']='wrong_mapping'
    with pytest.raises(ValueError):diagnostic.describe(p,result=broken)


def test_initial_request_review_and_recheck_share_source_rules():
    from cfm_id_llm.fact_source_contract import EVIDENCE_RULE, role_for
    s,e,o=setup();body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    contract=body['source_review_contract'];sheet=source.prepare(e,o['candidate'])
    assert contract['evidence_rule']==sheet['evidence_rule']==EVIDENCE_RULE
    assert not contract['definition_refs_supported'] and not contract['automatic_repair']
    path='/information/0/assignment_masses/0'
    assert contract['field_roles']['/information/*/assignment_masses/*']==sheet['fields'][path]['role']==role_for(path)
    assert contract['field_roles']['/additional_restrictions']==role_for('/additional_restrictions')
    assert legacy_reader.LEGACY_REMAINDER_SYSTEM not in e['request']['system']
    assert 'source_review_contract' not in legacy_setup()[1]['request']['user']
    constraints=registry.contract_for_entry(e).public_constraints(e,[path+'/source_ids'])
    assert any(x['field_path']=='/information/*/assignment_masses/*' and x['evidence_rule']==EVIDENCE_RULE for x in constraints)
    assert not any(x['field_path']=='/target' for x in constraints)
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    revised=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path=path+'/source_ids',doc='table'))
    assert EVIDENCE_RULE in revised['request']['user']
    assert json.JSONDecoder().raw_decode(revised['request']['user'])[0]['source_review_contract']==contract
    assert not revised['reading_revision_receipt']['candidate_modified']


def test_parent_table_citation_does_not_repair_row_or_bypass_review(monkeypatch):
    s,e,o=setup();raw=o['candidate'];path='/information/0/assignment_masses/0'
    catalog=reader.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])['aliases']
    table=[k for k,v in catalog.items() if v['doc_id']=='table']
    raw['information'][0]['source_ids']=table
    raw['information'][0]['assignment_masses'][0]['source_ids']=[table[-1]]
    before=deepcopy(raw)
    parsed=reader.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert len(parsed['facts']['information'][0]['assignment_masses'][0]['source_ids'])==1
    w=source.prepare(e,raw)
    assert w['fields'][path]['scope']=='RECORD_LOCAL_CITATIONS_ONLY'
    review=record(w);review['decisions'][path]['source_coverage']='REJECTED'
    monkeypatch.setattr(r3,'_compile',forbidden)
    result=d.execute(s,'q1',**dict(o,source_review=review),research_protocol_selected=True)
    assert result['state']=='READING_RECHECK_REQUIRED' and not result['backend_called']
    assert raw==before


def test_published_roles_do_not_strip_duplicate_or_real_extra_condition(monkeypatch):
    s,e,o=setup();raw=o['candidate']
    raw['additional_restrictions']=[dict(text='另采用跨门店的均值相等条件',source_ids=raw['mean_sufficiency']['source_ids'])]
    before=deepcopy(raw)
    # Fixture acceptance below tests control flow, not whether the synthetic
    # text is entailed. Genuine extra conditions must reach the coverage gate.
    accepted=record(source.prepare(e,raw))
    monkeypatch.setattr(r3,'_compile',forbidden)
    result=d.execute(s,'q1',**dict(o,source_review=accepted),research_protocol_selected=True)
    assert result['state']=='ADAPTER_NOT_CONNECTED' and not result['backend_called']
    rejected=deepcopy(accepted);rejected['decisions']['/additional_restrictions/0']['field_role']='REJECTED'
    result=d.execute(s,'q1',**dict(o,source_review=rejected),research_protocol_selected=True)
    assert result['state']=='READING_RECHECK_REQUIRED' and raw==before


@pytest.mark.parametrize('sufficiency,expected',[(True,'POINT'),(None,'NEEDS_INPUT'),(False,'ADAPTER_NOT_CONNECTED')])
def test_explicit_definitions_preserve_r3_science_and_replay(sufficiency,expected):
    from cfm_id_llm import network_observational_definitions as defined
    s,e,o=setup(profile=defined.PROFILE,sufficiency=sufficiency);raw=deepcopy(o['candidate'])
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    Draft202012Validator(schema).validate(raw)
    w=source.prepare(e,raw);row=w['fields']['/information/0/assignment_masses/0']
    assert row['explicit_definitions']['table_coordinates']['resolved_path']=='/information/0/coordinates/source_ids'
    assert len(row['citation_groups']['source_ids'])==1
    o['source_review']=record(w);p,a,r=execute(s,o)
    assert r['state']==expected and r['independent_replay']==(expected=='POINT')
    assert raw==o['candidate'] and p['evidence_dependencies']['raw_candidate_modified'] is False
    assert p['facts']['version']==reader.VERSION
    assert p['facts']['information'][0]['assignment_masses'][0]['source_ids']==[reader.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])['aliases'][raw['information'][0]['assignment_masses'][0]['source_ids'][0]]['source_id']]
    if expected=='POINT':
        assert r['certificate']['target_observational_probability']=='0'
        assert all(Fraction(c['support'])>0 for c in r['certificate']['classes'])


@pytest.mark.parametrize('defect',['missing_link','missing_direct','missing_header','wrong_nodes','foreign_source','duplicate_link','wrong_coding'])
def test_explicit_definition_errors_stop_before_core(monkeypatch,defect):
    from cfm_id_llm import network_observational_definitions as defined
    s,e,o=setup(profile=defined.PROFILE);info=o['candidate']['information'][0];row=info['assignment_masses'][0]
    if defect=='missing_link':row['definition_refs']=[]
    elif defect=='missing_direct':row['source_ids']=[]
    elif defect=='missing_header':info['coordinates']['source_ids']=[]
    elif defect=='wrong_nodes':info['coordinates']['node_order']=['foreign unit']
    elif defect=='foreign_source':info['coordinates']['source_ids']=['s9999']
    elif defect=='duplicate_link':row['definition_refs']*=2
    else:info['coordinates']['treated_value']=0
    monkeypatch.setattr(r3,'_compile',forbidden)
    p,a,r=execute(s,o)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    if defect in ('missing_link','missing_direct','missing_header','foreign_source','duplicate_link','wrong_coding'):
        assert list(Draft202012Validator(schema).iter_errors(o['candidate']))
    if defect!='foreign_source':
        assert diagnose(e,o['candidate'])


def test_table_definitions_cannot_leak_across_tables_or_authorize_sources(monkeypatch):
    from cfm_id_llm import network_observational_definitions as defined
    from cfm_id_llm.source_reference_wire import definition_evidence
    s,e,o=setup(profile=defined.PROFILE);raw=o['candidate'];second=deepcopy(raw['information'][0])
    second['coordinates']['source_ids']=raw['study']['source_ids'][:1]
    raw['information'].append(second);w=source.prepare(e,raw)
    first=w['fields']['/information/0/assignment_masses/0']['explicit_definitions']['table_coordinates']
    other=w['fields']['/information/1/assignment_masses/0']['explicit_definitions']['table_coordinates']
    assert first['source_ids']!=other['source_ids'] and other['resolved_path']=='/information/1/coordinates/source_ids'
    refs=defined.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    with pytest.raises(ValueError,match='DEFINITION_OUTSIDE_RECORD_SCOPE'):
        definition_evidence(raw,defined.DEFINITIONS,['table_coordinates'],record_path='/target',aliases=refs['aliases'])
    # An existing source ID can still be semantically the wrong header.
    review=record(w);review['decisions']['/information/1/coordinates']['source_coverage']='REJECTED'
    monkeypatch.setattr(r3,'_compile',forbidden)
    assert d.execute(s,'q1',**dict(o,source_review=review),research_protocol_selected=True)['state']=='READING_RECHECK_REQUIRED'


def test_definition_recheck_restore_and_old_review_rejection(tmp_path):
    from cfm_id_llm import network_observational_definitions as defined
    s,e,o=setup(profile=defined.PROFILE);saved=tmp_path/'defined.json';intake.save(s,saved)
    assert d.prepare_reader(intake.restore(saved),'q1',query_review=o['query_review'])==e
    good_review=record(source.prepare(e,o['candidate']));old_plan,old_approvals,old_result=execute(s,dict(o,source_review=good_review))
    assert old_result['independent_replay']
    o['candidate']['information'][0]['coordinates']['source_ids']=o['candidate']['study']['source_ids'][:1]
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    new=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/information/0/coordinates',doc='table'))
    assert defined.COORDINATES_RULE in new['request']['user']
    _,data=material();fresh=fact_reference(new,data)
    options=dict(query_review=o['query_review'],candidate=fresh,request_sha256=new['request_sha256'],reading_revision=new['reading_revision'])
    p=d.inspect_methods(s,'q1',**options);options['change_review']=accept_changes(p['reading_change_worksheet'])
    assert not d.execute(s,'q1',**dict(options,source_review=good_review),**old_approvals)['backend_called']
    options['source_review']=record(source.prepare(new,fresh))
    assert execute(s,options)[2]['independent_replay']
