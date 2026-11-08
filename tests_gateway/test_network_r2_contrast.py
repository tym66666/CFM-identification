"""R2 connection tests: external target, scientific review and native replay."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import combinations
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as d,business_case,capability_registry as registry
from cfm_id import network_contrast_dispatch as contrast
from cfm_id.workflows import policy_difference as composition
from cfm_id_bridge.scientific_binding import sha
from tests_gateway._reading_contract_checks import NATIVE_PROFILES
from examples.network_r2_contrast_reference import setup,approval_records
from examples.business_dispatch_reference import approve


def execute(s,o):
    p=d.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED'
    return p,d.execute(s,'q1',**o,**approval_records(p))


@pytest.mark.parametrize('profile',NATIVE_PROFILES)
def test_representative_fact_protocols_reach_r2_without_new_prompt(profile):
    s,e,o=setup(profile=profile);raw=deepcopy(o['candidate'])
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(raw)
    p,r=execute(s,o)
    assert e['reader_id']=='NETWORK_POLICY_CONTRAST_FACTS'
    assert [m['method'] for m in p['methods']]==[contrast.R2_METHOD]
    assert r['state']=='POINT' and r['independent_replay'] and o['candidate']==raw
    assert r['certificate']['new_core_theorem'] is False
    assert not r['production_admission'] and not r['estimation_handoff_allowed']
    assert r['primary_method'] in {m.method_id for m in registry.business_binding(e['reader_id']).methods}


def enumerated_value(study,assignment,weights):
    nodes=study['nodes'];edges=study['edges']
    def exposure(node,z):
        neighbors=[b if a==node else a for a,b in edges if node in (a,b)]
        return int(2*sum(z[nodes.index(n)] for n in neighbors)>len(neighbors))
    # Bounded [0,1] means, hence also feasible Bernoulli potential outcomes.
    mean=lambda i,z:F(1,10)+F(i+1,10*len(nodes))+F(z[i],5)+F(exposure(nodes[i],z),4)
    q=[]
    for selected in combinations(range(len(nodes)),len(nodes)//2):
        z=[int(i in selected) for i in range(len(nodes))];q.append(z)
    truth=sum(F(w)*mean(i,assignment) for i,w in enumerate(weights))
    observed=F(0)
    for i,w in enumerate(weights):
        if not F(w):continue
        arm=(assignment[i],exposure(nodes[i],assignment))
        compatible=[z for z in q if (z[i],exposure(nodes[i],z))==arm]
        assert compatible
        observed+=F(w)*sum(mean(i,z) for z in compatible)/len(compatible)
    assert truth==observed
    return truth


@pytest.mark.parametrize('scene',['clinics','warehouses'])
@pytest.mark.parametrize('reverse',[False,True])
def test_off_support_full_policies_same_target_and_signed_formula(scene,reverse):
    s,e,o=setup(scene,reverse=reverse);p,r=execute(s,o)
    assert r['state']=='POINT' and r['independent_replay']
    native=r['answers'][0]['native_evidence']['endpoints']
    for endpoint in native.values():
        # The Core supports node classes even though each full policy has q=0.
        assert endpoint['identification']['full_assignment_probability']=='0'
        assert all(F(x['joint_support'])>0 for x in endpoint['identification']['node_classes'])
    target=p['proposed_target'];raw=o['candidate']
    a=enumerated_value(raw['study'],target['first'],target['unit_weights'])
    b=enumerated_value(raw['study'],target['second'],target['unit_weights'])
    assert (a-b>0) is (not reverse)
    cert=r['certificate'];assert len(cert['terms'])==2*len(raw['target']['first']['population'])
    assert all((F(t['coefficient'])>0)==(t['side']=='first') for t in cert['terms'])
    full=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in approval_records(p).items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert len(full['results'])==1 and full['results'][0]['result']['independent_replay']


@pytest.mark.parametrize('layer',['plan','reading','science'])
@pytest.mark.parametrize('status',['PENDING','REJECTED'])
@pytest.mark.parametrize('information',['signature','full'])
def test_all_planned_reviews_precede_any_backend(monkeypatch,layer,status,information):
    s,e,o=setup(information=information);p=d.inspect_methods(s,'q1',**o);reviews=approval_records(p)
    review=reviews['plan_review'] if layer=='plan' else reviews['native_reviews'][contrast.R2_METHOD][layer+'_review']
    key='mean_sufficiency_all_assignments_and_weighted_nodes' if layer=='science' else next(iter(review.decisions))
    review.decisions[key]=status
    monkeypatch.setattr(contrast,'_compile_pair',lambda *a,**k:pytest.fail('review must precede native compilation'))
    r=d.execute(s,'q1',**o,**reviews)
    assert r['state']==('REVIEW_REQUIRED' if status=='PENDING' else 'CHECK_BLOCKED') and not r['backend_called']


@pytest.mark.parametrize('defect,expected',[
    ('unknown_sufficiency','NEEDS_INPUT'),('refused_sufficiency','NEEDS_INPUT'),
    ('sample_only','NEEDS_INPUT'),('missing_policy','NEEDS_INPUT'),('missing_population','NEEDS_INPUT'),
    ('different_population','ADAPTER_NOT_CONNECTED'),('extra_restriction','ADAPTER_NOT_CONNECTED'),
    ('sufficiency_scope_unknown','NEEDS_INPUT'),('sufficiency_nodes_missing','NEEDS_INPUT'),
    ('wrong_reference_context','CHECK_BLOCKED'),('unknown_source','CHECK_BLOCKED')])
def test_input_gaps_do_not_call_math(monkeypatch,defect,expected):
    s,e,o=setup();raw=o['candidate']
    if defect=='unknown_sufficiency':raw['mean_sufficiency']['value']=None
    elif defect=='refused_sufficiency':raw['mean_sufficiency']['value']=False
    elif defect=='sample_only':raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    elif defect=='missing_policy':raw['target']['second']['assignment']=None
    elif defect=='missing_population':raw['target']['second']['population']=None
    elif defect=='different_population':raw['target']['second']['population']=raw['study']['nodes'][:1]
    elif defect=='extra_restriction':raw['additional_restrictions']=[dict(text='另有两个对象在每种安排下的潜在结果均值相等。',source_ids=raw['study']['source_ids'])]
    elif defect=='sufficiency_scope_unknown':raw['mean_sufficiency']['scope']='UNKNOWN'
    elif defect=='sufficiency_nodes_missing':raw['mean_sufficiency']['covered_nodes']=raw['study']['nodes'][:1]
    elif defect=='wrong_reference_context':raw['reference_context']='c000000000000'
    else:raw['target']['source_ids']=['s9999']
    before=deepcopy(raw);monkeypatch.setattr(contrast,'_compile_pair',lambda *a,**k:pytest.fail('not ready'))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==expected and not r['backend_called'] and raw==before


@pytest.mark.parametrize('defect',['missing_signature_cell','zero_support'])
def test_one_endpoint_failure_never_certifies_difference_or_calls_partial(monkeypatch,defect):
    from cfm_id import bounded_contrast_solver
    monkeypatch.setattr(bounded_contrast_solver,'solve',lambda *a,**k:pytest.fail('no bounds fallback'))
    s,e,o=setup(**(dict(quota=1) if defect=='zero_support' else {}))
    if defect=='missing_signature_cell':o['candidate']['information'][0]['signature_cells'].pop()
    p,r=execute(s,o)
    assert r['state']==('NEEDS_INPUT' if defect=='missing_signature_cell' else 'UNSUPPORTED')
    assert r['backend_called'] and not r['independent_replay'] and not r['nonidentification_proved']
    assert r['mathematical_claim'] is None and r['certificate'] is None and not r['partial_fallback_performed']
    assert any(x['state']=='POINT' for x in r['attempts'])


def test_explicit_two_method_plan_and_actual_failure_telemetry():
    s,e,o=setup(information='full');p,r=execute(s,o)
    assert [x['method'] for x in p['methods']]==[contrast.POINT_METHOD,contrast.R2_METHOD]
    assert r['state']=='POINT' and r['primary_method']==contrast.R2_METHOD
    assert any(x['method']==contrast.POINT_METHOD and x['state']!='POINT' for x in r['attempts'])
    assert all(x['method']==contrast.R2_METHOD for x in r['answers'])


@pytest.mark.parametrize('information',['signature','full'])
@pytest.mark.parametrize('bad',['wrong_target','different_source','replay_false'])
def test_valid_other_proof_or_failed_replay_blocks_without_hiding_backend(monkeypatch,information,bad):
    from pfn_pipeline import identification_business as core
    from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
    s,e,o=setup(information=information);p=d.inspect_methods(s,'q1',**o);original=core.identify_network_business_query
    def changed(q):
        if q.r2_sources:
            if bad=='wrong_target':q=replace(q,target=fixed_policy_target_from_context(q.study,tuple(1-x for x in q.target.policy_assignment),unit_weights=q.target.unit_weights,authority='TRUSTED_FIXTURE'))
            elif bad=='different_source':q=replace(q,r2_sources=tuple(replace(x,provenance=x.provenance+' different evidence') for x in q.r2_sources))
        return original(q)
    monkeypatch.setattr(core,'identify_network_business_query',changed)
    if bad=='replay_false':monkeypatch.setattr(core,'replay_verified_business_outcome',lambda *a:False)
    r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='CHECK_BLOCKED' and r['backend_called'] and not r['independent_replay'] and r['mathematical_claim'] is None


@pytest.mark.parametrize('field',['coefficient','formula','assignment','signature','target','binding','endpoint','scope'])
def test_rehashed_composition_tampering_is_rejected(monkeypatch,field):
    original=composition.compose
    def corrupt(*a,**kw):
        r=original(*a,**kw)
        if field=='coefficient':r['terms'][0]['coefficient']='99'
        elif field=='formula':r['identified_functional']='0'
        elif field=='assignment':r['terms'][0]['assignment'][0]=1-r['terms'][0]['assignment'][0]
        elif field=='signature':r['terms'][0]['exposure']=1-r['terms'][0]['exposure']
        elif field=='target':r['target']['first'],r['target']['second']=r['target']['second'],r['target']['first']
        elif field=='binding':r['binding']['query_id']='q99'
        elif field=='endpoint':r['endpoint_sha256']['second']='0'*64
        else:r['estimation_handoff_allowed']=True
        r.pop('receipt_sha256');r['receipt_sha256']=sha(r);return r
    monkeypatch.setattr(composition,'compose',corrupt)
    s,e,o=setup();p,r=execute(s,o)
    assert r['state']=='CHECK_BLOCKED' and not r['independent_replay'] and r['backend_called']


def test_source_or_direction_change_invalidates_old_approval():
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);old=approval_records(p)
    t=o['candidate']['target'];t['first'],t['second']=t['second'],t['first']
    r=d.execute(s,'q1',**o,**old);assert r['state']=='CHECK_BLOCKED' and not r['backend_called']
