"""No-route network bridge: same target, distinct requirements, no fallback."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from cfm_id import business_dispatch as dispatch,business_case,business_intake as intake
from cfm_id.network_policy_dispatch import R1B,R2
from examples.network_dispatch_reference import setup,approval_records,candidate
from examples.business_dispatch_reference import approve


def run(s,options):
    plan=dispatch.inspect_methods(s,'q1',**options)
    return dispatch.execute(s,'q1',**options,**approval_records(plan)) if plan['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in plan else plan


def forbidden(*a,**kw): raise AssertionError('premature native mathematical call')


@pytest.mark.parametrize('kwargs,expected',[
    (dict(design='D1',sufficiency=False),[R1B]),({},[R2]),(dict(design='D1'),[R1B,R2])])
def test_same_policy_methods_checked_without_user_route_choice(kwargs,expected):
    s,e,o,p=setup(**kwargs)
    assert e['reader_id']=='NETWORK_FIXED_POLICY_FACTS' and p['state']=='REVIEW_REQUIRED'
    assert not p['backend_called'] and p['mathematical_claim'] is None
    r=run(s,o)
    assert r['state']=='POINT' and r['independent_replay']
    assert [a['method'] for a in r['answers']]==expected
    assert len({a['mathematical_claim']['target_fingerprint'] for a in r['answers']})==1
    assert all(a['mathematical_claim']['numeric_value'] is None for a in r['answers'])
    if kwargs=={}:
        assert r['attempts'][0]['reason_code']=='OFF_SUPPORT_ALTERNATE_THEOREM'
        assert r['certificate']['full_assignment_probability']=='0'
        assert [x['joint_support'] for x in r['certificate']['node_classes']]==['4/5','3/5','3/5','3/5','3/5']
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


def test_target_identity_does_not_depend_on_assignment_law_or_science_version():
    results=[run(s,o) for s,e,o,p in [setup(design='D1',sufficiency=False),setup(design='D1'),setup()]]
    assert len({r['mathematical_claim']['target_fingerprint'] for r in results})==1
    assert len({r['certificate']['certificate_sha256'] for r in results})==3


@pytest.mark.parametrize('field',['population','assignment'])
def test_missing_target_coordinate_is_not_filled_from_other_fields(monkeypatch,field):
    s,e,o,p=setup();o['candidate']['target'][field]=None
    from pfn_pipeline import identification_policy_r1b as r1b,identification_policy_r2 as r2
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',forbidden);monkeypatch.setattr(r2,'identify_verified_signature_policy',forbidden)
    r=run(s,o);assert r['state']=='NEEDS_INPUT' and not r['backend_called']


@pytest.mark.parametrize('name',['known_assignment_law','full_vector_randomization','consistency',
    'fixed_pretreatment_network','finite_conditional_first_moments'])
def test_design_does_not_invent_missing_scientific_declaration(name):
    s,e,o,p=setup();o['candidate']['assumptions'][name]['value']=None
    r=run(s,o);assert r['state']=='NEEDS_INPUT' and not r['backend_called']


def test_exposure_definition_is_not_mean_sufficiency_and_no_automatic_partial():
    s,e,o,p=setup();o['candidate']['mean_sufficiency'].update(value=None,scope='UNKNOWN',covered_nodes=[])
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert [r['method'] for r in plan['methods']]==[R1B]
    result=run(s,o)
    assert result['state']=='NEEDS_INPUT' and result['mathematical_claim'] is None
    assert result['partial_fallback_performed'] is False and result['nonidentification_proved'] is False
    s,e,o,p=setup(n=7,quota=3);result=run(s,o)
    assert result['state']=='UNSUPPORTED' and not result['partial_fallback_performed']
    assert [a['reason_code'] for a in result['attempts']]==['OFF_SUPPORT_ALTERNATE_THEOREM','ZERO_POLICY_SIGNATURE_SUPPORT']


def test_r1b_does_not_need_an_exposure_or_sufficiency_definition():
    s,e,o,p=setup(design='D1',sufficiency=False)
    o['candidate']['exposure'].update(kind='UNKNOWN',source_ids=[])
    o['candidate']['mean_sufficiency'].update(value=None,scope='UNKNOWN',covered_nodes=[],source_ids=[])
    r=run(s,o);assert r['state']=='POINT' and r['primary_method']==R1B


def test_finite_samples_are_not_population_laws():
    s,e,o,p=setup();o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    r=run(s,o);assert r['state']=='NEEDS_INPUT' and not r['backend_called']


@pytest.mark.parametrize('note',['仅有有限样本，样本估计不是精确总体信息。','此外还假定结果对处理单调。'])
def test_sample_only_gap_precedes_but_preserves_extra_restrictions(monkeypatch,note):
    s,e,o,p=setup();raw=o['candidate'];population_source=deepcopy(raw['information'][0])
    raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    raw['additional_restrictions']=[dict(text=note,source_ids=population_source['source_ids'])]
    raw['unresolved']=[dict(text='未声明总体信息。',source_ids=population_source['source_ids'])]
    from pfn_pipeline import identification_policy_r1b as r1b,identification_policy_r2 as r2
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',forbidden)
    monkeypatch.setattr(r2,'identify_verified_signature_policy',forbidden)
    r=dispatch.execute(s,'q1',**o)
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='POPULATION_INFORMATION_NOT_DECLARED'
    assert r['reading_candidate']==raw and r['facts']['additional_restrictions'][0]['text']==note
    assert r['unsupported_reasons']==['ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER']
    assert not r['backend_called'] and not r['answers'] and r['mathematical_claim'] is None
    coverage=approve(business_case.prepare_case(s)['case_worksheet'])
    whole=business_case.execute_case(s,{'q1':o},case_review=coverage,research_protocol_selected=True)
    assert whole['state']=='CASE_INCOMPLETE' and whole['results'][0]['result']['state']=='NEEDS_INPUT'
    # Adding real population information must not remove a still-unreviewed restriction.
    raw['information'].append(population_source);raw['unresolved']=[]
    r=dispatch.execute(s,'q1',**o)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert r['facts']['additional_restrictions'][0]['text']==note


def test_incomplete_a4_nodes_not_silently_completed():
    s,e,o,p=setup();o['candidate']['information'][0]['outcome_nodes'].pop()
    r=run(s,o);assert r['state']=='NEEDS_INPUT' and not r['answers']


def test_single_evaluation_unit_does_not_become_whole_network_average():
    s,e,o,p=setup(n=7,quota=3)
    o['candidate']['target']['population']=['网点1']
    r=run(s,o)
    assert r['state']=='POINT' and r['primary_method']==R2
    target=r['mathematical_claim']['target']
    assert target['unit_weights']==['0','1','0','0','0','0','0']
    assert [x['node'] for x in r['certificate']['node_classes']]==['网点1']
    assert r['answers'][0]['native_evidence']['target']['unit_weights']==target['unit_weights']


def test_signature_cells_are_used_without_promoting_them_to_full_assignment_information():
    s,e,o,p=setup()
    source=o['candidate']['information'][0]
    source.update(operator='NODE_SIGNATURE_MEANS',signature_cells=[dict(node=n,own=1,exposure=1) for n in source['outcome_nodes']])
    p=dispatch.inspect_methods(s,'q1',**o)
    assert [row['method'] for row in p['methods']]==[R2]
    r=run(s,o);assert r['state']=='POINT' and r['primary_method']==R2
    source['signature_cells'].pop()
    r=run(s,o);assert r['state']=='NEEDS_INPUT' and not r['answers']


def test_numeric_bounds_or_extra_restrictions_preserved_not_dropped():
    s,e,o,p=setup();o['candidate']['additional_restrictions']=[dict(text='结果均值有额外界限，需独立处理。',source_ids=o['candidate']['target']['source_ids'])]
    r=run(s,o);assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert r['facts']['additional_restrictions']


@pytest.mark.parametrize('corruption',['source','context','bool','probability','edge','approval'])
def test_malformed_or_cross_request_facts_blocked(corruption):
    s,e,o,p=setup(design='D1');raw=o['candidate']
    if corruption=='source':raw['study']['source_ids']=['s9999']
    elif corruption=='context':raw['reference_context']='c000000000000'
    elif corruption=='bool':raw['target']['assignment']['中心']=True
    elif corruption=='probability':raw['assignment']['probabilities']['中心']='2'
    elif corruption=='edge':raw['study']['edges'].append(list(reversed(raw['study']['edges'][0])))
    else:raw['approved']=True
    r=run(s,o);assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('status',['PENDING','REJECTED'])
def test_every_method_review_checked_before_any_solver(monkeypatch,status):
    s,e,o,p=setup(design='D1');a=approval_records(p)
    record=a['native_reviews'][R2]['science_review']
    decisions=dict(record.decisions);decisions['mean_sufficiency_all_assignments_and_weighted_nodes']=status
    a['native_reviews'][R2]['science_review']=record.model_copy(update={'decisions':decisions})
    from pfn_pipeline import identification_policy_r1b as r1b
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',forbidden)
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if status=='PENDING' else 'CHECK_BLOCKED') and not r['backend_called']


@pytest.mark.parametrize('change',['population','quota','source_scope','science','authority'])
def test_changed_scope_or_authority_cannot_reuse_approval(change):
    s,e,o,p=setup();a=approval_records(p)
    if change=='population':o['candidate']['target']['population']=['中心']
    elif change=='quota':o['candidate']['assignment']['fixed_count']=3
    elif change=='source_scope':o['candidate']['information'][0]['outcome_nodes']=['中心']
    elif change=='science':o['candidate']['mean_sufficiency']['covered_nodes']=['中心']
    else:a['native_reviews'][R2]['science_review']=a['native_reviews'][R2]['science_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_returned_native_proof_must_match_reviewed_policy(monkeypatch):
    s,e,o,p=setup(design='D1',sufficiency=False)
    from pfn_pipeline import identification_policy_r1b as r1b
    original=r1b.identify_verified_fixed_policy
    def wrong(st,target,sources,**kw):
        return original(st,replace(target,policy_assignment=(0,)*len(st.node_order)),sources,**kw)
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',wrong)
    r=run(s,o);assert r['state']=='CHECK_BLOCKED' and not r['answers'] and not r['independent_replay']


def test_whole_case_and_cli_accept_explicit_network_reviews(tmp_path):
    from cfm_id.business_case_cli import main
    s,e,o,p=setup();a=approval_records(p);a.pop('research_protocol_selected')
    row=dict(o,**a);coverage=approve(business_case.prepare_case(s)['case_worksheet'])
    def serial(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        return v
    intake.save(s,tmp_path/'intake.json');intake.write_json(tmp_path/'submissions.json',serial({'q1':row}))
    intake.write_json(tmp_path/'coverage.json',serial(coverage))
    assert main(['execute','--intake',str(tmp_path/'intake.json'),'--submissions',str(tmp_path/'submissions.json'),
        '--case-review',str(tmp_path/'coverage.json'),'--select-research-protocol','--output',str(tmp_path/'result.json')])==0
    r=intake.read_json(tmp_path/'result.json')
    assert r['state']=='ALL_QUERIES_IDENTIFIED' and r['identified_query_ids']==['q1']
    assert r['results'][0]['result']['primary_method']==R2


def test_dag_short_reference_request_compatibility():
    from cfm_id_llm.dag_query_reading import reference_catalog as dag_refs
    from cfm_id.source_locations import build_catalog
    from cfm_id_llm.dag_reading import documents
    b=dict(case_id='same',documents={'d':'原文'},question='问题')
    old=dict(version='dag-query-reading-1',bundle=b,binding='binding',catalog=build_catalog(documents(b)))
    r=dag_refs(b,binding='binding')
    assert r['context_sha256']==intake._sha(old) and r['context']=='c'+intake._sha(old)[:12]
