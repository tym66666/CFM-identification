"""A signed business target must match the native linear proof, not display negation."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import pytest
from cfm_id import business_dispatch as d,business_intake as intake,business_case,network_effect_dispatch as effects
from cfm_id_llm.schemas import BusinessCase
from examples.network_effect_dispatch_reference import material,a0_reference,fact_reference,approval_records
from examples.business_dispatch_reference import approve
from pfn_pipeline import identification_composition as native


def setup(population='all',exposure=1,**kwargs):
    case,data=material(population=population,**kwargs)
    old=data['questions']['q1']
    data['questions']['q1']=('合作对象'+('过半' if exposure else '至多一半')+'启用时，自己未启用与自己'+data['treatment']+
        '相比，'+data['outcome']+'相差多少？按未启用减启用计算。')
    payload=case.model_dump(mode='json');payload['business_question']=payload['business_question'].replace(old,data['questions']['q1'])
    s=intake.start(BusinessCase.model_validate(payload),reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,a0_reference(s.case,data),request_sha256=s.request_sha256)
    q=approve(d.prepare_reader(s,'q1')['query_worksheet']);e=d.prepare_reader(s,'q1',query_review=q)
    raw=fact_reference(e,data)
    raw['target']['first'].update(own=0,exposure=exposure);raw['target']['second'].update(own=1,exposure=exposure)
    opts=dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])
    return s,e,opts,d.inspect_methods(s,'q1',**opts)


@pytest.mark.parametrize('population',['all','subset','single'])
@pytest.mark.parametrize('exposure',[0,1])
def test_reversed_direct_matches_exhaustive_assignments_and_whole_case(population,exposure):
    s,e,o,p=setup(population,exposure);before=deepcopy(o['candidate'])
    approvals=approval_records(p);r=d.execute(s,'q1',**o,**approvals)
    assert r['state']=='POINT' and r['independent_replay'] and o['candidate']==before
    assert r['certificate']['contract_version']=='network-local-effect-linear-evidence-1'
    raw=o['candidate'];nodes=raw['study']['nodes'];rates=raw['assignment']['probabilities'];members=raw['target']['population']
    def mean(node,a):
        i=nodes.index(node);neighbors={nodes.index(v) for edge in raw['study']['edges'] if node in edge for v in edge if v!=node}
        num=F(0);den=F(0)
        for z in product((0,1),repeat=len(nodes)):
            if z[i]!=a or int(2*sum(z[j] for j in neighbors)>len(neighbors))!=exposure:continue
            mass=F(1)
            for name,v in zip(nodes,z):mass*=F(rates[name]) if v else 1-F(rates[name])
            # Allows different outcomes within the same exposure group.
            y=(i+1)+3*z[i]+sum((j+1)*v for j,v in enumerate(z))+7*z[0]*z[-1]
            num+=mass*y;den+=mass
        return num/den,den
    expected=sum((mean(n,0)[0]-mean(n,1)[0] for n in members),F(0))/len(members)
    actual=F(0);seen=set()
    for arm in r['certificate']['results'][0]['constituent_arms']:
        n=arm['node_id'];a=arm['own_treatment'];value,support=mean(n,a)
        assert F(arm['coefficient'])==F(1 if a==0 else -1,len(members))
        assert arm['exposure_state']==exposure and F(arm['joint_support'])==support
        seen.add((n,a));actual+=F(arm['coefficient'])*value
    assert actual==expected and seen=={(n,a) for n in members for a in (0,1)}
    assert r['mathematical_claim']['target']['first']==[0,exposure] and r['mathematical_claim']['numeric_value'] is None
    sub=dict(o,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})
    whole=business_case.execute_case(s,{'q1':sub},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']['independent_replay'] and whole['state']=='CASE_INCOMPLETE'
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


@pytest.mark.parametrize('mutation,expected',[
    ('sample','NEEDS_INPUT'),('undecided','NEEDS_INPUT'),('refused','ADAPTER_NOT_CONNECTED'),
    ('a4_missing','NEEDS_INPUT'),('missing_population','NEEDS_INPUT'),('post_assignment','ADAPTER_NOT_CONNECTED'),
    ('missing_remaining','NEEDS_INPUT'),('source_rejected','CHECK_BLOCKED'),('science_pending','REVIEW_REQUIRED')])
def test_reversed_target_does_not_bypass_admission(monkeypatch,mutation,expected):
    s,e,o,_=setup();raw=o['candidate']
    if mutation=='sample':raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    elif mutation in ('undecided','refused'):raw['scientific_statements']['consistency']['status']='UNDECIDED' if mutation=='undecided' else 'NOT_ADOPTED'
    elif mutation=='a4_missing':raw['information'][0]['arm_cells']=[a for a in raw['information'][0]['arm_cells'] if a['own']==0]
    elif mutation=='missing_population':raw['target']['population']=None
    elif mutation=='post_assignment':raw['target']['population_fixed_before_assignment']['value']=False
    elif mutation=='missing_remaining':raw['target']['remaining_assignment']='UNKNOWN'
    p=d.inspect_methods(s,'q1',**o);a=dict(research_protocol_selected=True)
    if mutation in ('source_rejected','science_pending'):
        a=approval_records(p)
        rec=a['native_reviews'][effects.METHOD]['reading_review' if mutation=='source_rejected' else 'science_review']
        rec.decisions['source_entailment' if mutation=='source_rejected' else 'full_vector_randomization']='REJECTED' if mutation=='source_rejected' else 'PENDING'
    monkeypatch.setattr(effects,'_compile',lambda *args:pytest.fail('Unreviewed native compilation'))
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['backend_called'] and r['certificate'] is None


@pytest.mark.parametrize('operator',['NODE_ARM_MEANS','NODE_FULL_LAW','FULL_JOINT_LAW'])
def test_reversed_target_keeps_original_a4_operator(operator):
    s,e,o,_=setup();o['candidate']['information'][0]['operator']=operator
    if operator!='NODE_ARM_MEANS':o['candidate']['information'][0]['arm_cells']=[]
    p=d.inspect_methods(s,'q1',**o);r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['answers'][0]['native_evidence']['a4_source']['operator']==operator


@pytest.mark.parametrize('probability',['0','1'])
def test_zero_support_on_either_side_has_no_formula_or_fallback(probability):
    s,e,o,_=setup();o['candidate']['assignment']['probabilities']['甲店']=probability
    p=d.inspect_methods(s,'q1',**o);r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='UNSUPPORTED' and r['reason_code']=='ZERO_ARM_SUPPORT' and r['backend_called']
    assert not r['independent_replay'] and r['certificate'] is None and not r['partial_fallback_performed']


@pytest.mark.parametrize('tamper',['sign','subset','source','formula','replay_false','replay_mutation','input_mutation'])
def test_wrong_native_proof_or_replay_cannot_publish(monkeypatch,tamper):
    s,e,o,p=setup();original=native.identify_verified_linear_target
    def bad(batch,source,terms):
        if tamper=='sign':return original(batch,source,tuple(replace(t,coefficient=-t.coefficient) for t in terms))
        if tamper=='subset':return original(batch,source,terms[:2])
        if tamper=='source':return original(batch,replace(source,source_id=source.source_id+'_different'),terms)
        result=original(batch,source,terms)
        if tamper=='formula':return replace(result,identified_functional='0')
        if tamper=='input_mutation':batch.template.outcome_kind='binary'
        return result
    monkeypatch.setattr(native,'identify_verified_linear_target',bad)
    if tamper=='replay_false':monkeypatch.setattr(native,'replay_verified_composition',lambda proof:False)
    if tamper=='replay_mutation':
        def mutate(proof):
            object.__setattr__(proof,'identified_functional','0');return proof
        monkeypatch.setattr(native,'replay_verified_composition',mutate)
    r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='CHECK_BLOCKED' and not r['independent_replay'] and r['certificate'] is None


def test_direction_change_invalidates_old_review_and_changes_target_fingerprint():
    s,e,o,p=setup();old=approval_records(p);r=d.execute(s,'q1',**o,**old)
    t=o['candidate']['target'];t['first'],t['second']=t['second'],t['first']
    blocked=d.execute(s,'q1',**o,**old);assert blocked['state']=='CHECK_BLOCKED' and not blocked['backend_called']
    new=d.inspect_methods(s,'q1',**o);f=d.execute(s,'q1',**o,**approval_records(new))
    assert f['state']=='POINT' and r['mathematical_claim']['target_fingerprint']!=f['mathematical_claim']['target_fingerprint']


def test_registry_lists_the_actual_linear_producer_and_replayer():
    from cfm_id.capability_registry import business_binding
    row=business_binding(effects.FAMILY).methods[0]
    assert native.identify_verified_linear_target in row.producers and native.replay_verified_composition in row.replayers
