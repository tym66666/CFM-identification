"""A4 guidance preserves existing semantics, review bindings and math."""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from itertools import product
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm.information_semantics import with_information_scope
from cfm_id_llm.network_statement_reading import INFORMATION_SCOPE_CONTRACT,make_selection_request,make_information_request,parse_selection
from examples.network_dispatch_reference import setup,candidate,approval_records
from examples.business_dispatch_reference import approve
from tests_gateway.test_network_statement_reading import to_wire,as_selection


def scoped(**kwargs):
    s,_,_,_=setup(**kwargs);s=intake.configure_network_fact_contract(s,INFORMATION_SCOPE_CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    o=dict(query_review=q,candidate=as_selection(to_wire(candidate(e,**kwargs),e)),request_sha256=e['request_sha256'])
    return s,e,o


def without_descriptions(value):
    if isinstance(value,dict):return {k:without_descriptions(v) for k,v in value.items() if k!='description'}
    if isinstance(value,list):return [without_descriptions(v) for v in value]
    return value


def test_guidance_changes_only_explanations_not_source_data_or_wire_schema():
    _,e,_=scoped();old=make_selection_request(e['bundle'],binding=e['fact_binding_sha256']);before=deepcopy(old)
    new=with_information_scope(old)
    assert old==before and new!=old
    assert without_descriptions(json.loads(old['user']))==without_descriptions(json.loads(new['user']))
    assert new==make_information_request(e['bundle'],binding=e['fact_binding_sha256'])
    assert 'NODE_FULL_LAW' in new['system'] and 'FULL_JOINT_LAW' in new['system']


def test_each_single_outcome_full_assignment_law_does_not_determine_joint_outcomes():
    # Exact counterexample: same (Y_i,T) marginals for every i, different joint Y.
    # Nothing here changes or calls the identification solver.
    same={(y,y,t):Fraction(1,8) for y in (0,1) for t in product((0,1),repeat=2)}
    opposite={(y,1-y,t):Fraction(1,8) for y in (0,1) for t in product((0,1),repeat=2)}
    def marginal(law,i):
        result=defaultdict(Fraction)
        for (y0,y1,t),p in law.items():result[((y0,y1)[i],t)]+=p
        return dict(result)
    assert sum(same.values())==sum(opposite.values())==1
    assert all(marginal(same,i)==marginal(opposite,i) for i in (0,1))
    assert sum(p for (a,b,_),p in same.items() if a==b)==1
    assert sum(p for (a,b,_),p in opposite.items() if a==b)==0


@pytest.mark.parametrize('operator',['NODE_FULL_LAW','FULL_JOINT_LAW','ASSIGNMENT_NODE_MEANS','NODE_SIGNATURE_MEANS','FINITE_SAMPLE','UNKNOWN'])
def test_reader_preserves_declared_information_type_without_upgrading_or_downgrading(operator):
    s,e,o=scoped(design='D1',sufficiency=False);raw=o['candidate'];info=raw['information'][0]
    info['operator']=operator
    if operator=='ASSIGNMENT_NODE_MEANS':info['assignment_cells']=[[1]*len(raw['study']['nodes'])]
    if operator=='NODE_SIGNATURE_MEANS':info['signature_cells']=[dict(node=raw['study']['nodes'][0],own=1,exposure=1,value=None)]
    if operator in ('FINITE_SAMPLE','UNKNOWN'):info['availability']=operator
    before=deepcopy(raw);facts=parse_selection(e['bundle'],raw,binding=e['fact_binding_sha256'])['facts']
    assert raw==before and facts['information'][0]['operator']==operator
    assert facts['information'][0]['assignment_cells']==info['assignment_cells']
    assert facts['information'][0]['signature_cells']==info['signature_cells']
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not result['backend_called']
    if operator=='FINITE_SAMPLE':assert result['state']=='NEEDS_INPUT'


@pytest.mark.parametrize('operator',['NODE_FULL_LAW','FULL_JOINT_LAW','ASSIGNMENT_NODE_MEANS'])
def test_same_point_target_under_independently_reviewed_supported_a4(operator):
    s,e,o=scoped(design='D1',sufficiency=False);raw=o['candidate'];info=raw['information'][0];info['operator']=operator
    if operator=='ASSIGNMENT_NODE_MEANS':info['assignment_cells']=[[1]*len(raw['study']['nodes'])]
    plan=dispatch.inspect_methods(s,'q1',**o);assert not plan['backend_called']
    result=dispatch.execute(s,'q1',**o,**approval_records(plan))
    assert result['state']=='POINT' and result['independent_replay']
    old,_,oldopts,oldplan=setup(design='D1',sufficiency=False)
    baseline=dispatch.execute(old,'q1',**oldopts,**approval_records(oldplan))
    assert result['mathematical_claim']['target_fingerprint']==baseline['mathematical_claim']['target_fingerprint']


def test_scope_instruction_change_invalidates_reviews_and_survives_explicit_reread(tmp_path):
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_network_statement_reading import selected
    from tests_gateway.test_fact_reading_revision import feedback,accept_changes
    old,e0,o0=selected();s=intake.configure_network_fact_contract(old,INFORMATION_SCOPE_CONTRACT)
    assert intake.prepare_request(s)==intake.prepare_request(old)
    assert dispatch.prepare_reader(s,'q1',query_review=o0['query_review'])['state']=='CHECK_BLOCKED'
    intake.save(s,tmp_path/'scope.json');assert intake.restore(tmp_path/'scope.json')==s
    s,e,o=scoped();sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    e2=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/information/0/operator',doc='information'))
    assert e2['network_fact_contract']==INFORMATION_SCOPE_CONTRACT
    assert '区别不在T是否完整' in e2['request']['system']
    fresh=as_selection(to_wire(candidate(e2),e2));fresh['information'][0]['operator']='FULL_JOINT_LAW'
    opts=dict(query_review=o['query_review'],candidate=fresh,request_sha256=e2['request_sha256'],reading_revision=e2['reading_revision'])
    r=dispatch.inspect_methods(s,'q1',**opts);assert 'reading_change_worksheet' in r
    r2=dispatch.inspect_methods(s,'q1',**opts,change_review=accept_changes(r['reading_change_worksheet']))
    assert r2['state']=='REVIEW_REQUIRED' and not r2['backend_called']


def test_bounded_partial_remains_on_existing_math_contract():
    from examples.network_bounded_dispatch_reference import setup as bounded_setup,reference
    old,_,_,_=bounded_setup();s=intake.configure_network_fact_contract(old,INFORMATION_SCOPE_CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    o=dict(query_review=q,candidate=as_selection(to_wire(reference(e),e)),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay']


@pytest.mark.parametrize('format',['legacy','scoped'])
@pytest.mark.parametrize('gap',['operator','availability','both'])
def test_unknown_information_requires_clarification_not_a_coverage_gap(format,gap,monkeypatch):
    from pfn_pipeline import identification_policy_r1b as r1b,identification_policy_r2 as r2
    from tests_gateway.test_network_dispatch import forbidden
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',forbidden)
    monkeypatch.setattr(r2,'identify_verified_signature_policy',forbidden)
    if format=='legacy':s,e,o,_=setup()
    else:s,e,o=scoped()
    info=o['candidate']['information'][0]
    if gap in ('operator','both'):info['operator']='UNKNOWN'
    if gap in ('availability','both'):info['availability']='UNKNOWN'
    before=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='POPULATION_INFORMATION_SCOPE_UNRESOLVED'
    assert r['unresolved_information_indices']==[0] and r['clarification_questions']
    assert not r['backend_called'] and not r['methods'] and not r['answers']
    assert r['reading_candidate']==before and o['candidate']==before
    assert r['evidence_status']=='CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE'


@pytest.mark.parametrize('kind',['symbolic','bounded'])
def test_known_source_cannot_hide_an_additional_unknown_source(kind):
    if kind=='symbolic':s,e,o,_=setup()
    else:
        from examples.network_bounded_dispatch_reference import setup as bounded_setup
        s,e,o,_=bounded_setup()
    extra=deepcopy(o['candidate']['information'][0]);extra.update(operator='UNKNOWN',availability='UNKNOWN',assignment_cells=[],signature_cells=[])
    o['candidate']['information'].append(extra)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and r['unresolved_information_indices']==[1]
    assert not r['backend_called'] and len(r['facts']['information'])==2


@pytest.mark.parametrize('extra_note',['材料未说明结果和处理的联合范围。','研究另行要求潜在结果随处理单调不减。'])
def test_clarifying_unknown_information_preserves_other_restrictions(extra_note):
    s,e,o,_=setup();raw=o['candidate'];source=deepcopy(raw['information'][0])
    raw['information'][0].update(operator='UNKNOWN',availability='UNKNOWN')
    raw['additional_restrictions']=[dict(text=extra_note,source_ids=source['source_ids'])]
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='POPULATION_INFORMATION_SCOPE_UNRESOLVED'
    assert r['facts']['additional_restrictions'][0]['text']==extra_note
    assert r['unsupported_reasons']==['ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER']
    raw['information'][0]=source
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert r['facts']['additional_restrictions'][0]['text']==extra_note


def test_known_other_information_remains_a_coverage_gap():
    s,e,o=scoped();o['candidate']['information'][0]['operator']='OTHER'
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and r['reason_code']=='INFORMATION_OPERATOR_NOT_CONNECTED'
    assert not r['backend_called']


def test_note_release_and_whole_case_cannot_approve_unknown_information():
    from tests_gateway.test_reading_note_review import with_note,review
    from cfm_id import business_case
    s,e,o,_=with_note(kind='r1b');o['candidate']['information'][0]['operator']='UNKNOWN'
    p=dispatch.inspect_methods(s,'q1',**o);o['note_review']=review(p)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called']
    assert r['note_review_receipt'] and not r['note_review_receipt']['scientific_approval']
    case_review=approve(business_case.prepare_case(s)['case_worksheet'])
    whole=business_case.execute_case(s,{'q1':o},case_review=case_review,research_protocol_selected=True)
    assert whole['state']=='CASE_INCOMPLETE' and not whole['backend_called']
    assert whole['results'][0]['result']['state']=='NEEDS_INPUT'


@pytest.mark.parametrize('kind',['r1b','r2','partial'])
def test_scope_contract_note_review_and_whole_case_replay_preserve_every_boundary(kind):
    """Offline composition test, not a replay of a repaired live LLM answer."""
    from cfm_id import business_case
    from tests_gateway.test_reading_note_review import review
    if kind=='partial':
        from examples.network_bounded_dispatch_reference import setup as bounded_setup,reference
        old,_,_,_=bounded_setup()
        note='材料只列出部分总体均值；目标是否还能获得严格界限，应交数学检查。'
    else:
        kwargs=dict(design='D1',sufficiency=False) if kind=='r1b' else {}
        old,_,_,_=setup(**kwargs)
        note='材料给的是符号总体信息，没有列数值；是否可以给出识别式，应交数学检查。'
    s=intake.configure_network_fact_contract(old,INFORMATION_SCOPE_CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e) if kind=='partial' else candidate(e,**kwargs),e))
    raw['unresolved']=[dict(text=note,source_ids=raw['information'][0]['source_ids'])]
    before=deepcopy(raw);o=dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])
    pending=dispatch.inspect_methods(s,'q1',**o)
    assert pending['state']=='REVIEW_REQUIRED' and 'plan_worksheet' not in pending
    o['note_review']=review(pending)
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert dispatch.execute(s,'q1',**o,research_protocol_selected=True)['state']=='REVIEW_REQUIRED'
    a=approval_records(plan);row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    whole=business_case.execute_case(s,{'q1':row},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    result=whole['results'][0]['result']
    assert whole['state']=='ALL_QUERIES_IDENTIFIED' and result['independent_replay']
    assert result['state']==('PARTIAL' if kind=='partial' else 'POINT')
    assert raw==before and result['note_review_receipt']['original_notes']
    assert not result['note_review_receipt']['candidate_modified']
    assert not result['statement_reading_receipt']['scientific_approval']
    assert not result['note_review_receipt']['scientific_approval']
    assert not whole['production_admission'] and not whole['estimation_handoff_allowed']
    if kind=='partial':
        assert result['mathematical_claim']['interval']==['3/7','4/7']
        assert result['mathematical_claim']['sharp'] and not whole['all_queries_point_identified']


def test_scope_note_release_cannot_discard_a_genuine_extra_model_constraint():
    from examples.network_bounded_dispatch_reference import setup as bounded_setup,reference
    from tests_gateway.test_reading_note_review import review
    old,_,_,_=bounded_setup(extra=True)
    s=intake.configure_network_fact_contract(old,INFORMATION_SCOPE_CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=as_selection(to_wire(reference(e,extra=True),e))
    raw['unresolved']=[dict(text='是否仍能给界限需要数学判断。',source_ids=raw['target']['source_ids'])]
    before=deepcopy(raw);o=dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);o['note_review']=review(p)
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='ADAPTER_NOT_CONNECTED' and not result['backend_called']
    assert raw==before and result['facts']['additional_restrictions']
    assert result['facts']['bounded_model']['no_additional_coupling_constraints']['value'] is False
