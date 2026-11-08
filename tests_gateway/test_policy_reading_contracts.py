"""Configured mean readers share wiring, not causal licenses or contrast targets."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as d,business_case
from cfm_id import fact_source_review as source,fact_reading_revision as revision,network_policy_dispatch as native
from cfm_id_llm import fact_reading_contracts as registry,network_contrast_reading as contrast_reading
from cfm_id_llm import network_policy_reading as reading,network_statement_reading as statements
from cfm_id_llm.network_fact_protocols import network_fact_profiles,network_fact_protocol
from cfm_id_llm.fact_wire_models import model_for
from cfm_id_llm.wire_type_diagnostics import diagnose
from examples import network_dispatch_reference as mean,network_bounded_dispatch_reference as bounded,network_contrast_dispatch_reference as contrast
from examples.business_dispatch_reference import approve
from tests_gateway.test_network_statement_reading import to_wire,as_selection
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback,accept_changes
from tests_gateway._reading_contract_checks import NATIVE_PROFILES,validate_candidate,policy_inputs

PROFILES=network_fact_profiles()
PROBE_PROFILES=(None,'network-source-selections-information-4','network-source-selections-alignment-1')
KINDS=('r1b','r2','partial','bounded_point')


def candidate(entry,kind):
    kw=dict(design='D1',sufficiency=False) if kind=='r1b' else dict(center_bounds=('1/2','1/2')) if kind=='bounded_point' else {}
    raw=(mean.candidate if kind in ('r1b','r2') else bounded.reference)(entry,**kw)
    profile=entry.get('network_fact_contract')
    if profile is not None:
        raw=to_wire(raw,entry)
        if profile!=statements.VERSION:raw=as_selection(raw)
    if profile in ('network-policy-definition-refs-1', 'network-policy-record-definitions-1', 'network-policy-scopes-1', 'network-policy-scopes-2'):
        raw['version']=profile
        raw['assignment']['definition_refs']=['study'] if raw['assignment']['probabilities'] else []
        raw['target']['definition_refs']=['study']
        for info in raw['information']:info['definition_refs']=['study']
        if profile in ('network-policy-record-definitions-1','network-policy-scopes-1','network-policy-scopes-2'):
            raw['mean_sufficiency']['definition_refs']=['study'] if raw['mean_sufficiency']['covered_nodes'] else []
    if profile in ('network-policy-scopes-1','network-policy-scopes-2'):
        for info in raw['information']:info.update(scope_status='DECLARED' if info['outcome_nodes'] else 'UNSPECIFIED',scope_source_ids=list(info['source_ids']) if info['outcome_nodes'] else [])
    from tests_gateway._reading_contract_checks import current_fixture
    return current_fixture(entry,raw)


def setup(kind='partial',profile=None):
    kw=dict(design='D1',sufficiency=False) if kind=='r1b' else dict(center_bounds=('1/2','1/2')) if kind=='bounded_point' else {}
    s,_,_,_=(mean if kind in ('r1b','r2') else bounded).setup(**kw)
    if profile is not None:s=intake.configure_network_fact_contract(s,profile)
    q=approve(d.prepare_reader(s,'q1')['query_worksheet']);e=d.prepare_reader(s,'q1',query_review=q)
    return s,e,dict(query_review=q,candidate=candidate(e,kind),request_sha256=e['request_sha256'])


@pytest.fixture(scope='module')
def default_policy_inputs():
    result={}
    for kind in KINDS:
        s,e,o=setup(kind)
        result[kind]=policy_inputs(d.inspect_methods(s,'q1',**o),o['candidate']['reference_context'])
    return result


@pytest.mark.parametrize('profile',PROFILES)
def test_configured_registry_preserves_single_protocol_owner(profile,default_policy_inputs):
    s,e,o=setup(profile=profile);c=registry.contract_for_entry(e);p=network_fact_protocol(profile)
    assert c.make_request is p.make_request and c.parse is p.parse and c.model is p.model
    assert c.profile==profile and c.profile_field=='network_fact_contract' and c.version_field is None
    assert c.wire_version==p.wire_version and c.target_context is not None
    assert c.target_context.clarify_request.__name__=='preserve_contrast_request'
    assert c.documents is reading.documents and c.reference_catalog is reading.reference_catalog
    assert c.model is model_for(e)
    assert c.entry_metadata()==({'network_fact_contract':profile} if profile else {})
    request=c.request(e['bundle'],binding=e['fact_binding_sha256'],assignment_semantics=e.get('assignment_semantics'))
    assert request==p.make_request(e['bundle'],binding=e['fact_binding_sha256'],assignment_semantics=e.get('assignment_semantics'))
    body=json.loads(request['user']);assert 'conditioning' not in body['output_schema']['properties']
    assert body['output_schema']['properties']['version']['const']==c.wire_version
    assert c.public_constraints(e,[''])==p.public_constraints([''],request=e['request'])
    assert c.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])==p.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])
    # Every historical profile retains schema AND complete mathematical-input
    # compatibility for all four paths; only native execution is sampled below.
    for kind in KINDS:
        s,e,o=setup(kind,profile)
        validate_candidate(e,o['candidate'])
        actual=policy_inputs(d.inspect_methods(s,'q1',**o),o['candidate']['reference_context'])
        assert actual==default_policy_inputs[kind], (profile,kind)


@pytest.mark.parametrize('profile',NATIVE_PROFILES)
@pytest.mark.parametrize('kind,expected',[('r1b','POINT'),('r2','POINT'),('partial','PARTIAL'),('bounded_point','POINT')])
def test_representative_profiles_use_real_point_or_sharp_partial_with_same_whole_case(profile,kind,expected):
    s,e,o=setup(kind,profile);raw=deepcopy(o['candidate'])
    o['source_review']=record(source.prepare(e,raw));p=d.inspect_methods(s,'q1',**o)
    pending=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    a=mean.approval_records(p);result=d.execute(s,'q1',**o,**a)
    assert result['state']==expected and result['independent_replay'] and raw==o['candidate']
    assert not result['production_admission']
    if kind in ('r1b','r2'):
        assert {a['method'] for a in result['answers']}=={native.R1B if kind=='r1b' else native.R2}
    else:
        assert result['partial_fallback_performed'] is False
    if kind=='partial':assert result['mathematical_claim']['interval']==['3/7','4/7'] and result['mathematical_claim']['sharp']
    if kind=='bounded_point':assert result['mathematical_claim']['interval']==['1/2','1/2']
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']==result


@pytest.mark.parametrize('profile',['foreign',statements.SELECTION_VERSION+'-typo','network-policy-reading-1',False,[],{}])
def test_unknown_profile_never_falls_back_to_default(profile):
    with pytest.raises(registry.ReadingContractError):registry.registered_contract(native.FAMILY,profile=profile)


def test_request_profile_is_not_output_version_and_cannot_reuse_old_receipt():
    s,e,o=setup(profile='network-source-selections-information-4')
    other='network-source-selections-remainder-1';p=registry.contract_for_entry(e)
    q=registry.registered_contract(native.FAMILY,profile=other)
    assert p.wire_version==q.wire_version and p.profile!=q.profile
    with pytest.raises(registry.ReadingContractError):p.check_entry(dict(e,network_fact_contract=other))
    changed=intake.configure_network_fact_contract(s,other)
    assert d.prepare_reader(changed,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    new_q=approve(d.prepare_reader(changed,'q1')['query_worksheet'])
    entry=d.prepare_reader(changed,'q1',query_review=new_q)
    assert entry['request_sha256']!=e['request_sha256']
    assert d.execute(changed,'q1',query_review=new_q,candidate=o['candidate'],request_sha256=entry['request_sha256'],research_protocol_selected=True)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('profile',PROBE_PROFILES)
@pytest.mark.parametrize('defect,expected',[('sample','NEEDS_INPUT'),('incomplete_model','NEEDS_INPUT'),('refused_science','ADAPTER_NOT_CONNECTED'),('extra_coupling','ADAPTER_NOT_CONNECTED')])
def test_information_and_science_gates_are_not_registration_permissions(profile,defect,expected):
    s,e,o=setup(profile=profile);raw=o['candidate']
    if defect=='sample':raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    elif defect=='incomplete_model':raw['bounded_model']['listed_means_are_complete_information']['value']=None
    elif defect=='extra_coupling':raw['bounded_model']['no_additional_coupling_constraints']['value']=False
    elif profile is None:raw['assumptions']['consistency']['value']=False
    else:raw['scientific_statements']['consistency']['status']='NOT_ADOPTED'
    result=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']==expected and not result['backend_called'] and result['mathematical_claim'] is None


@pytest.mark.parametrize('status,expected',[('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED'),('OMITTED','CHECK_BLOCKED')])
def test_registered_bounded_reader_still_needs_every_native_approval(status,expected):
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=mean.approval_records(p)
    decisions=next(iter(a['native_reviews'].values()))['science_review'].decisions
    key=next(iter(decisions))
    if status=='OMITTED':decisions.pop(key)
    else:decisions[key]=status
    result=d.execute(s,'q1',**o,**a)
    assert result['state']==expected and not result['backend_called']


@pytest.mark.parametrize('profile',PROBE_PROFILES)
def test_explicit_recheck_retains_profile_rules_and_requires_new_full_reviews(profile):
    s,e,o=setup(profile=profile);old_reviews=mean.approval_records(d.inspect_methods(s,'q1',**o))
    bad=deepcopy(o['candidate']);bad['study']['outcome_kind']='UNKNOWN_ENUM'
    assert any(r['field_path']=='/study/outcome_kind' for r in diagnose(e,bad))
    args=dict(o,candidate=bad);w=revision.prepare_recheck(s,'q1',**args)['feedback_worksheet']
    new=revision.prepare_recheck(s,'q1',**args,feedback=feedback(w,path='/study/outcome_kind',kind='WIRE_FORMAT_ERROR',doc='study'))
    assert new['state']=='READY_TO_READ' and new.get('network_fact_contract')==profile
    assert registry.contract_for_entry(new).model is model_for(e)
    raw=candidate(new,'partial');options=dict(query_review=o['query_review'],candidate=raw,request_sha256=new['request_sha256'],reading_revision=new['reading_revision'])
    assert d.execute(s,'q1',**dict(options,candidate=o['candidate']),research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    p=d.inspect_methods(s,'q1',**options);options['change_review']=accept_changes(p['reading_change_worksheet'])
    assert d.execute(s,'q1',**options,**old_reviews)['state']=='CHECK_BLOCKED'
    p=d.inspect_methods(s,'q1',**options);r=d.execute(s,'q1',**options,**mean.approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay']


def test_policy_consumer_uses_registered_parser_without_legacy_fallback(monkeypatch):
    s,e,o=setup();rows=registry.registrations();calls=[]
    def fail(*args,**kwargs):calls.append(True);raise ValueError('synthetic parser failure')
    monkeypatch.setattr(registry,'registrations',lambda:tuple(replace(c,parse=fail) if c.reader_id==native.FAMILY else c for c in rows))
    result=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert calls and result['state']=='CHECK_BLOCKED' and not result['backend_called']


@pytest.mark.parametrize('profile',PROFILES)
def test_contrast_reuses_common_wire_but_keeps_its_own_target_and_receipts(profile):
    s,e,o=contrast.setup('cancellation',profile=profile);raw=deepcopy(o['candidate'])
    assert registry.contract_for_entry(e).reader_id=='NETWORK_POLICY_CONTRAST_FACTS'
    assert model_for(e) is contrast_reading.reading_model(profile)
    assert model_for(e) is not registry.registered_contract(native.FAMILY,profile=profile).model
    # Format/endpoint ownership here; actual cancellation and replay have one
    # owner in test_network_contrast_dispatch; configured mathematical inputs
    # are compared exhaustively in test_contrast_reading_contracts.
    p=d.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and not p['backend_called']
    assert raw==o['candidate'] and p['proposed_target']['operation']=='first_minus_second'
    assert all(p['endpoint_plans'][side]['proposed_target']['assignment']==list(raw['target'][side]['assignment'].values()) for side in ('first','second'))




def test_ambiguous_selector_and_unmarked_contrast_projection_are_rejected(monkeypatch):
    c=registry.registered_contract(native.FAMILY)
    monkeypatch.setattr(registry,'registrations',lambda:(c,replace(c,profile='another',profile_field='another_field')))
    with pytest.raises(registry.ReadingContractError):registry.registered_contract(native.FAMILY)
    monkeypatch.undo()
    s,e,o=setup();p=native.inspect_methods(dict(e,reader_id='NETWORK_POLICY_CONTRAST_FACTS'),o['candidate'])
    assert p['state']=='CHECK_BLOCKED' and not p['backend_called']
