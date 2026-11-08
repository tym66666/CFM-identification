"""Shared contrast reading lifecycle, independently guarded pair semantics."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from cfm_id import business_dispatch as d,business_case,fact_source_review as source,fact_reading_revision as revision
from cfm_id import network_contrast_dispatch as native
from cfm_id_llm import fact_reading_contracts as registry,network_contrast_reading as reading
from cfm_id_llm.network_fact_protocols import network_fact_profiles,network_fact_protocol
from cfm_id_llm.fact_wire_models import model_for
from cfm_id_llm.wire_type_diagnostics import diagnose
from cfm_id_llm.compact_evidence_contract import clarify_fact_order
from examples import network_contrast_dispatch_reference as example,network_r2_contrast_reference as r2
from examples.business_dispatch_reference import approve
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback,accept_changes
from tests_gateway import test_compact_evidence_slots as compact
from tests_gateway._reading_contract_checks import validate_candidate,contrast_inputs

PROFILES=network_fact_profiles()
PROBE=(None,'network-source-selections-alignment-1')
KINDS=('point','r2','partial','cancellation')


def configured_comparison(kind,profile=None):
    from tests_gateway._reading_contract_checks import current_fixture
    s,e,o=r2.setup(profile=profile) if kind=='r2' else example.setup(kind,profile=profile)
    o['candidate']=current_fixture(e,o['candidate'])
    return s,e,o


@pytest.fixture(scope='module')
def default_comparison_inputs():
    result={}
    for kind in KINDS:
        s,e,o=configured_comparison(kind)
        result[kind]=contrast_inputs(d.inspect_methods(s,'q1',**o),o['candidate']['reference_context'])
    return result


@pytest.mark.parametrize('profile',PROFILES)
def test_registered_pair_uses_existing_config_schema_parser_and_direction_help(profile,default_comparison_inputs):
    s,e,o=example.setup('partial',profile=profile);c=registry.contract_for_entry(e)
    assert c.reader_id==native.FAMILY and c.model is model_for(e) is reading.reading_model(profile)
    assert c.make_request.func is reading.make_request and c.parse.func is reading.parse
    assert c.make_request.keywords==c.parse.keywords=={'profile':profile}
    assert c.wire_version==reading.VERSION and c.profile==profile and c.target_context is not None
    assert c.target_context.clarify_request(e['request'])==e['request']
    assert c.clarify_comparison is clarify_fact_order
    assert c.entry_metadata()==({'network_fact_contract':profile} if profile else {})
    for assignment in (None,'joint-assignment-law-1'):
        base=reading.make_request(e['bundle'],binding=e['fact_binding_sha256'],profile=profile,assignment_semantics=assignment)
        for signed in (False,True):
            actual=c.request(e['bundle'],binding=e['fact_binding_sha256'],assignment_semantics=assignment,signed_comparison=signed)
            assert actual==(clarify_fact_order(base) if signed else base)
    assert c.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])==reading.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'],profile=profile)
    assert revision._references(e)==c.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    actual_constraints=revision._public_constraints(e,[''])
    base_constraints=network_fact_protocol(profile).public_constraints([''],request=e['request'])
    from cfm_id_llm.network_mean_order_reading import PROFILES as ORDER_PROFILES
    from cfm_id_llm import mean_order_ownership as ownership
    if profile in ORDER_PROFILES:
        # The new profile appends its schema-derived rules; old protocol rules stay intact.
        assert actual_constraints[:len(base_constraints)]==base_constraints
        extra=actual_constraints[len(base_constraints):]
        schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
        claim_schema=schema['$defs']['OrderClaim']
        from cfm_id_llm.mean_order_field_contract import OUTCOME_BINDING_RULE
        assert OUTCOME_BINDING_RULE in extra and OUTCOME_BINDING_RULE in schema['x-cfm-field-contract']
        assert extra and all(r['field_path'].startswith('/mean_order_model') or
            r==OUTCOME_BINDING_RULE or
            (profile==ownership.PROFILE and r['field_path'] in ownership.ROLES) for r in extra)
        if profile==ownership.PROFILE:
            assert all(any(r['field_path']==path and r.get('description')==description for r in extra)
                       for path,description in ownership.ROLES.items())
        rule=next(r for r in extra if r.get('error_code')=='NOT_ASSUMED_HAS_NO_LICENSED_LEVEL_OR_SCOPE')
        assert rule['field_path']=='/mean_order_model/order_reading/claims/*'
        assert rule['combination']==claim_schema['allOf'][0]
        for name in ('relation','level','scope'):
            assert any(r['field_path']=='/mean_order_model/order_reading/claims/*/'+name
                and r.get('description')==claim_schema['properties'][name]['description'] for r in extra)
    else:
        assert actual_constraints==base_constraints
    fields=source.prepare(e,o['candidate'])['fields']
    assert all(path in fields for path in ('/target','/target/first','/target/second','/target/shared_outcome_and_context'))
    for kind in KINDS:
        s,e,o=configured_comparison(kind,profile)
        validate_candidate(e,o['candidate'])
        actual=contrast_inputs(d.inspect_methods(s,'q1',**o),o['candidate']['reference_context'])
        assert actual==default_comparison_inputs[kind], (profile,kind)


def test_all_registered_profiles_reuse_the_same_format_classes_on_revisit():
    models={p:registry.registered_contract(native.FAMILY,profile=p).model for p in PROFILES}
    for p in PROFILES:
        assert registry.registered_contract(native.FAMILY,profile=p).model is models[p] is reading.reading_model(p)


@pytest.mark.parametrize('kind,expected',[('point','POINT'),('r2','POINT'),('partial','PARTIAL'),('cancellation','POINT')])
@pytest.mark.parametrize('profile',PROBE)
def test_registered_comparison_executes_real_joint_or_signed_proofs(kind,expected,profile):
    s,e,o=(r2.setup(profile=profile) if kind=='r2' else example.setup(kind,profile=profile))
    before=deepcopy(o['candidate']);o['source_review']=record(source.prepare(e,before))
    p=d.inspect_methods(s,'q1',**o)
    pending=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    a=example.approval_records(p);r=d.execute(s,'q1',**o,**a)
    assert r['state']==expected and r['independent_replay'] and o['candidate']==before
    assert not r['partial_fallback_performed'] and not r['production_admission']
    if kind=='partial':assert r['mathematical_claim']['interval']==['-1','1'] and r['mathematical_claim']['sharp']
    if kind=='cancellation':assert r['mathematical_claim']['interval']==['1/5','1/5']
    if kind in ('point','r2'):assert r['primary_method']==(native.R2_METHOD if kind=='r2' else native.POINT_METHOD)
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert len(whole['results'])==1 and whole['results'][0]['result']==r




@pytest.mark.parametrize('decision',native.PAIR_DECISIONS)
@pytest.mark.parametrize('status,expected',[('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED'),('OMITTED','CHECK_BLOCKED')])
def test_independent_pair_review_cannot_be_replaced_by_component_registration(decision,status,expected):
    s,e,o=example.setup('partial');p=d.inspect_methods(s,'q1',**o);a=example.approval_records(p)
    decisions=a['native_reviews'][native.BOUNDED_METHOD]['reading_review'].decisions
    if status=='OMITTED':decisions.pop(decision)
    else:decisions[decision]=status
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['backend_called']




@pytest.mark.parametrize('kind',['point','partial'])
@pytest.mark.parametrize('profile',(None,'network-source-selections-information-4','network-source-selections-alignment-1'))
def test_recheck_uses_same_pair_contract_and_invalidates_all_old_approvals(kind,profile):
    s,e,o=example.setup(kind,profile=profile);old_source=record(source.prepare(e,o['candidate']))
    old_reviews=example.approval_records(d.inspect_methods(s,'q1',**dict(o,source_review=old_source)))
    bad=deepcopy(o['candidate']);bad['target']['operation']='INVALID_OPERATION'
    assert any(row['field_path']=='/target/operation' for row in diagnose(e,bad))
    args=dict(o,candidate=bad);w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    revised=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/target/operation',kind='WIRE_FORMAT_ERROR',doc='__question__'))
    assert revised['state']=='READY_TO_READ' and registry.contract_for_entry(revised).model is model_for(e)
    _,data=example.material(kind);raw=example.fact_reference(revised,data)
    options=dict(query_review=o['query_review'],candidate=raw,request_sha256=revised['request_sha256'],reading_revision=revised['reading_revision'])
    assert d.execute(s,'q1',**dict(options,candidate=o['candidate']),research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    p=d.inspect_methods(s,'q1',**options);options['change_review']=accept_changes(p['reading_change_worksheet'])
    assert d.execute(s,'q1',**dict(options,source_review=old_source),research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    options['source_review']=record(source.prepare(revised,raw))
    assert d.execute(s,'q1',**options,**old_reviews)['state']=='CHECK_BLOCKED'
    plan=d.inspect_methods(s,'q1',**options);r=d.execute(s,'q1',**options,**example.approval_records(plan))
    assert r['state']==('POINT' if kind=='point' else 'PARTIAL') and r['independent_replay']


@pytest.mark.parametrize('operation',['INTERVENTION_MINUS_COMPARATOR','COMPARATOR_MINUS_INTERVENTION'])
def test_a0_direction_decoration_is_registered_and_retained_by_recheck(operation):
    b,_,raw=compact.contrast_raw(operation=operation);s=compact.received(b,raw)
    q=compact.submit(s,compact.record(compact.sheet(s)))['query_review'];e=d.prepare_reader(s,'q1',query_review=q)
    _,data=example.material('point');candidate=example.fact_reference(e,data)
    base=reading.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    assert e['request']['system']==clarify_fact_order(base)['system']
    args=dict(query_review=q,candidate=candidate,request_sha256=e['request_sha256'])
    w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    new=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/target',doc='__question__'))
    assert new['state']=='READY_TO_READ' and new['request']['system'].startswith(e['request']['system'])
    assert new['request']['system'].count('first/second不是主方案/基准')==1
    from cfm_id.fact_reading_revision import apply_revision
    # Old callers retain their default signature, but their unclarified request
    # must not authenticate a candidate under the corrected intake protocol.
    legacy=apply_revision(e,new['reading_revision'],contexts=[])
    assert legacy['request_sha256']!=new['request_sha256']
    fresh=example.fact_reference(new,data)
    revised_args=dict(query_review=q,candidate=fresh,request_sha256=new['request_sha256'],reading_revision=new['reading_revision'])
    stale=dict(revised_args,request_sha256=legacy['request_sha256'])
    blocked=d.execute(s,'q1',**stale,research_protocol_selected=True)
    assert blocked['state']=='CHECK_BLOCKED' and not blocked['backend_called']
    w2=revision.prepare_recheck(s,'q1',**revised_args)['feedback_worksheet']
    twice=revision.prepare_recheck(s,'q1',**revised_args,feedback=feedback(w2,path='/target',doc='__question__'))
    assert twice['state']=='READY_TO_READ' and twice['reading_revision_receipt']['rounds']==2
    assert twice['request']['system'].startswith(e['request']['system'])
    assert twice['request']['system'].count('first/second不是主方案/基准')==1


@pytest.mark.parametrize('patch',[{'reader_id':'NETWORK_FIXED_POLICY_FACTS'},{'reference_format':'source_hash'},
    {'network_fact_contract':'foreign'},{'network_fact_contract':reading.VERSION}])
def test_wrong_family_format_or_profile_cannot_reach_contrast_checks(patch):
    s,e,o=example.setup('point');p=native.inspect_methods(dict(e,**patch),o['candidate'])
    assert p['state']=='CHECK_BLOCKED' and not p['backend_called'] and not p['methods']


def test_native_consumer_uses_registered_parser_without_a_private_fallback(monkeypatch):
    s,e,o=example.setup('point');rows=registry.registrations();calls=[]
    def fail(*args,**kwargs):calls.append(True);raise ValueError('Synthetic parser rejection')
    monkeypatch.setattr(registry,'registrations',lambda:tuple(replace(c,parse=fail) if c.reader_id==native.FAMILY else c for c in rows))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert calls and r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_comparison_hook_is_validated_and_consumed_by_shared_request_builder(monkeypatch):
    s,e,o=example.setup('point');c=registry.contract_for_entry(e)
    with pytest.raises(registry.ReadingContractError):replace(c,clarify_comparison=False)
    rows=registry.registrations();calls=[]
    def watch(request):calls.append(True);return clarify_fact_order(request)
    monkeypatch.setattr(registry,'registrations',lambda:tuple(replace(row,clarify_comparison=watch) if row.reader_id==native.FAMILY else row for row in rows))
    d._fact_request(e['bundle'],e['fact_binding_sha256'],e['reader_id'],e['reference_format'],e['selected_query'],[],signed_comparison=True)
    assert calls==[True]
