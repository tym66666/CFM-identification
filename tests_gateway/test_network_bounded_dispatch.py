"""Common-intake finite bounds: exact evidence, complete model, no implicit fallback."""
from copy import deepcopy
from fractions import Fraction as F
import pytest
from examples.network_bounded_dispatch_reference import setup
from examples.network_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve
from cfm_id import business_dispatch as dispatch,business_case,business_intake as intake
from cfm_id.network_bounded_dispatch import METHOD,compile_reviewed
from cfm_id_bridge.scientific_binding import sha


def execute(s,o):
    p=dispatch.inspect_methods(s,'q1',**o)
    return dispatch.execute(s,'q1',**o,**approval_records(p)) if p['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in p else p


def forbidden(*args,**kwargs):raise AssertionError('No numerical backend allowed')


@pytest.mark.parametrize('missing_scope',[False,True])
def test_extra_condition_fixture_does_not_assert_an_uncoupled_model(missing_scope,monkeypatch):
    from cfm_id import bounded_policy_solver
    from examples.network_bounded_dispatch_reference import case
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    business,_=case(extra=True,missing_scope=missing_scope)
    docs={s.source_id:s.text for s in business.sources}
    assert '没有跨对象、跨情境的额外耦合限制' not in docs['complete_model']
    assert '固定其他网点的处理安排' in docs['extra']
    s,e,o,p=setup(extra=True,missing_scope=missing_scope)
    assert o['candidate']['bounded_model']['no_additional_coupling_constraints']['value'] is False
    result=execute(s,o)
    assert result['state']=='ADAPTER_NOT_CONNECTED' and not result['backend_called']
    assert result['facts']['additional_restrictions'] and not result['answers']


def test_same_target_and_a4_under_nested_mean_bounds():
    results=[];native=[]
    for bounds,expected in [(('1/2','1/2'),['1/2','1/2']),
        (('1/4','3/4'),['13/28','15/28']),(('0','1'),['3/7','4/7'])]:
        s,e,o,p=setup(center_bounds=bounds);raw=deepcopy(o['candidate']);r=execute(s,o)
        assert o['candidate']==raw and r['independent_replay']
        claim=r['mathematical_claim'];assert claim['interval']==expected and claim['sharp'] is True
        assert claim['kind']==('POINT' if bounds[0]==bounds[1] else 'PARTIAL')
        assert not r['production_admission'] and not r['estimation_handoff_allowed']
        assert not r['partial_fallback_performed'];results.append(claim)
        native.append(r['answers'][0]['native_evidence'])
    assert len({r['target_sha256'] for r in results})==1
    assert all(r['information']['values']==native[0]['information']['values'] for r in native)
    for a,b in zip(results,results[1:]):
        assert F(b['interval'][0])<=F(a['interval'][0])<=F(a['interval'][1])<=F(b['interval'][1])


def test_supported_target_is_numeric_point_and_single_unit_can_be_uninformative():
    s,e,o,p=setup(n=5,quota=4);r=execute(s,o)
    assert r['state']=='POINT' and r['mathematical_claim']['numeric_value']=='1/2'
    s,e,o,p=setup();o['candidate']['target']['population']=['中心'];r=execute(s,o)
    assert r['state']=='PARTIAL' and r['mathematical_claim']['interval']==['0','1']
    assert r['mathematical_claim']['sharp'] and not r['mathematical_claim']['informative']
    assert r['mathematical_claim']['target']['unit_weights']==['1','0','0','0','0','0','0']


def test_different_network_topology_uses_same_contract():
    s,e,o,p=setup(n=4,quota=2,topology='chain');r=execute(s,o)
    assert r['state']=='PARTIAL' and r['independent_replay']
    assert r['mathematical_claim']['interval']==['1/4','3/4']
    assert r['answers'][0]['native_evidence']['inquiry']['study']['undirected_edges']==o['candidate']['study']['edges']


def partition_table(raw):
    source=raw['information'][0]
    raw['information']=[dict(deepcopy(source),outcome_nodes=[v['node']],signature_cells=[deepcopy(v)])
                        for v in source['signature_cells']]


def test_one_table_partition_preserves_exact_model_without_repair():
    s,e,o,p=setup();whole=execute(s,o);partition_table(o['candidate']);raw=deepcopy(o['candidate'])
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert plan['a4_projection']['source_documents']==['information']
    assert plan['a4_projection']['original_entry_indices']==list(range(7))
    split=execute(s,o)
    assert split['state']=='PARTIAL' and split['independent_replay'] and o['candidate']==raw
    assert split['mathematical_claim']==whole['mathematical_claim']
    assert split['answers'][0]['native_evidence']['information']['values']==whole['answers'][0]['native_evidence']['information']['values']
    o['candidate']['unresolved']=[dict(text='仍有未核对的问题。',source_ids=raw['information'][0]['source_ids'])]
    r=execute(s,o);assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']


@pytest.mark.parametrize('bad',['other_document','duplicate_equal','duplicate_conflict'])
def test_partition_projection_never_merges_other_sources_or_duplicate_cells(bad):
    s,e,o,p=setup();raw=o['candidate'];partition_table(raw)
    if bad=='other_document':raw['information'][0]['source_ids']=raw['bounded_model']['source_ids']
    else:
        extra=deepcopy(raw['information'][0])
        if bad=='duplicate_conflict':extra['signature_cells'][0]['value']='1/3'
        raw['information'].append(extra)
    r=execute(s,o)
    assert r['state']==('ADAPTER_NOT_CONNECTED' if bad=='other_document' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and r['reading_candidate']==raw


@pytest.mark.parametrize('missing',['bounds','scope','kind','definition','unit','period','complete','coupling','value','sufficiency','model'])
def test_missing_bounded_contract_stays_blocked(monkeypatch,missing):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    s,e,o,p=setup();c=o['candidate'];b=c['bounded_model']
    if missing=='bounds':b['bounds'].pop()
    elif missing=='scope':b['bounds_scope']='UNKNOWN'
    elif missing=='kind':b['bounds_kind']='UNKNOWN'
    elif missing in ('definition','unit','period'):b['outcome_'+missing]=None
    elif missing=='complete':b['listed_means_are_complete_information']['value']=None
    elif missing=='coupling':b['no_additional_coupling_constraints']['value']=None
    elif missing=='value':c['information'][0]['signature_cells'][0]['value']=None
    elif missing=='sufficiency':c['mean_sufficiency']['covered_nodes'].pop()
    else:c['bounded_model']=None
    r=execute(s,o);assert r['state']=='NEEDS_INPUT' and not r['backend_called']
    assert r['mathematical_claim'] is None and not r['answers']


@pytest.mark.parametrize('extra',['full_law','coupling','incomplete_information','design','large','restriction'])
def test_stronger_or_other_models_not_downgraded(extra):
    s,e,o,p=setup(n=13 if extra=='large' else 7,extra=extra=='restriction');c=o['candidate']
    if extra=='full_law':
        v=deepcopy(c['information'][0]);v.update(operator='FULL_JOINT_LAW',signature_cells=[],availability='SYMBOLIC_POPULATION_OPERATOR')
        c['information'].append(v)
    elif extra=='coupling':c['bounded_model']['no_additional_coupling_constraints']['value']=False
    elif extra=='incomplete_information':c['bounded_model']['listed_means_are_complete_information']['value']=False
    elif extra=='design':c['assignment'].update(kind='INDEPENDENT_BERNOULLI',fixed_count=None,probabilities={n:'1/2' for n in c['study']['nodes']})
    r=execute(s,o);assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']
    assert r['reading_candidate']==c


def test_positive_support_missing_value_is_needs_input_not_partial():
    s,e,o,p=setup();source=o['candidate']['information'][0]
    source['signature_cells']=[v for v in source['signature_cells'] if v['node']!='网点1']
    source['outcome_nodes'].remove('网点1')
    r=execute(s,o)
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='SUPPORTED_TARGET_A4_MEAN_MISSING'
    assert r['mathematical_claim'] is None and not r['answers']


@pytest.mark.parametrize('error',['off_support','inconsistent','binary_outcome'])
def test_incompatible_model_has_no_verified_interval(error):
    s,e,o,p=setup(center_bounds=('1/4','3/4') if error=='binary_outcome' else ('0','1'),
                  bounds_kind='ALMOST_SURE_OUTCOME' if error=='binary_outcome' else 'CONDITIONAL_MEAN')
    if error=='off_support':o['candidate']['information'][0]['signature_cells'].append(dict(node='中心',own=1,exposure=1,value='1/2'))
    elif error=='inconsistent':o['candidate']['information'][0]['signature_cells'][0]['value']='2'
    r=execute(s,o)
    assert r['state']=='INCOMPATIBLE' and not r['independent_replay'] and not r['incompatibility_proved']
    assert r['mathematical_claim'] is None and not r['answers']


@pytest.mark.parametrize('bad',['float','bool','noncanonical','duplicate','source'])
def test_invalid_numeric_or_source_coordinates_rejected(bad):
    s,e,o,p=setup();c=o['candidate'];cell=c['information'][0]['signature_cells'][0]
    if bad=='float':cell['value']=0.5
    elif bad=='bool':cell['own']=True
    elif bad=='noncanonical':cell['value']='2/4'
    elif bad=='duplicate':c['bounded_model']['bounds'].append(deepcopy(c['bounded_model']['bounds'][0]))
    else:c['bounded_model']['bounds'][0]['source_ids']=['s9999']
    r=execute(s,o);assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('status',['PENDING','REJECTED'])
def test_separate_complete_model_review_required_before_solver(monkeypatch,status):
    from cfm_id import bounded_policy_solver
    monkeypatch.setattr(bounded_policy_solver,'solve',forbidden)
    s,e,o,p=setup();a=approval_records(p);record=a['native_reviews'][METHOD]['science_review']
    decisions=dict(record.decisions);decisions['no_additional_coupling_constraints']=status
    a['native_reviews'][METHOD]['science_review']=record.model_copy(update={'decisions':decisions})
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if status=='PENDING' else 'CHECK_BLOCKED') and not r['backend_called']


def test_changed_bounds_cannot_reuse_old_review():
    s,e,o,p=setup();a=approval_records(p)
    o['candidate']['bounded_model']['bounds'][0]['lower']='1/4'
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_existing_synthetic_scope_not_silently_promoted():
    s,e,o,p=setup()
    o['query_review']=o['query_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    e=dispatch.prepare_reader(s,'q1',query_review=o['query_review'])
    from examples.network_bounded_dispatch_reference import reference
    o.update(candidate=reference(e),request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    a['plan_review']=a['plan_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    a['native_reviews'][METHOD]={k:v.model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'}) for k,v in a['native_reviews'][METHOD].items()}
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']


@pytest.mark.parametrize('corrupt',['certificate','mutate_inputs','wrong_model'])
def test_independent_replay_binds_actual_reviewed_inputs(monkeypatch,corrupt):
    from cfm_id import bounded_policy_solver
    s,e,o,p=setup();original=bounded_policy_solver.solve
    def bad(q,info):
        cert=original(q,info)
        if corrupt=='certificate':
            cert['lower']='0';cert.pop('certificate_sha256');cert['certificate_sha256']=sha(cert)
        elif corrupt=='mutate_inputs':info.bounds.pop()
        else:
            other=info.model_copy(update={'bounds':[b.model_copy(update={'lower':'1/4'}) if b.node=='中心' else b for b in info.bounds]})
            cert=original(q,other)
        return cert
    monkeypatch.setattr(bounded_policy_solver,'solve',bad)
    r=execute(s,o);assert r['state']=='CHECK_BLOCKED' and not r['independent_replay'] and not r['answers']


def test_partial_whole_case_and_cli_are_complete_but_not_all_point(tmp_path):
    from cfm_id.business_case_cli import main
    s,e,o,p=setup();a=approval_records(p);a.pop('research_protocol_selected')
    def serial(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        return v
    intake.save(s,tmp_path/'intake.json')
    intake.write_json(tmp_path/'submissions.json',serial({'q1':dict(o,**a)}))
    intake.write_json(tmp_path/'coverage.json',serial(approve(business_case.prepare_case(s)['case_worksheet'])))
    assert main(['execute','--intake',str(tmp_path/'intake.json'),'--submissions',str(tmp_path/'submissions.json'),
        '--case-review',str(tmp_path/'coverage.json'),'--select-research-protocol','--output',str(tmp_path/'result.json')])==0
    r=intake.read_json(tmp_path/'result.json')
    assert r['state']=='ALL_QUERIES_IDENTIFIED' and r['identified_query_ids']==['q1']
    assert r['partially_identified_query_ids']==['q1'] and r['point_identified_query_ids']==[]
    assert r['all_queries_identified'] and not r['all_queries_point_identified']
