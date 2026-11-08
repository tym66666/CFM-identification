"""Business connection acceptance; no new mathematical implementation."""
from copy import deepcopy
from fractions import Fraction
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, business_case, mean_order, mean_order_verify
from cfm_id import network_mean_order_dispatch as orders, method_diagnostics
from cfm_id.mean_order_contract import MeanOrderProblem
from cfm_id_llm import network_contrast_reading as reading
from cfm_id_llm.network_mean_order_reading import PROFILE
from examples.network_mean_order_dispatch_reference import setup
from examples.network_contrast_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve


def execute(options=None, **kwargs):
    s,e,o=setup(**kwargs)
    if options: options(o['candidate'])
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert 'plan_worksheet' in plan, (plan['state'],plan.get('reason_code'))
    approvals=approval_records(plan)
    result=dispatch.execute(s,'q1',**o,**approvals)
    return s,e,o,plan,approvals,result


def test_same_target_a4_and_bounds_assumption_ladder_and_native_replay():
    expected={'BOTH':['1/5','1'],'OWN':['-1/5','1'],'NONE':['-1','1']}
    targets=[];values=[];widths=[]
    for mode,interval in expected.items():
        s,e,o,p,a,r=execute(mode=mode)
        Draft202012Validator(json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']).validate(o['candidate'])
        assert r['state']=='PARTIAL' and r['independent_replay']
        claim=r['mathematical_claim'];answer=r['answers'][0]
        assert claim['interval']==interval and claim['sharp']
        assert not r['production_admission'] and not r['estimation_handoff_allowed']
        assert not r['partial_fallback_performed']
        problem=MeanOrderProblem.model_validate(answer['native_evidence']['problem'])
        assert mean_order_verify.replay(answer['certificate'],problem=problem) is True
        targets.append(claim['target_sha256']);values.append(problem.values);widths.append(Fraction(claim['width']))
        diagnostic=method_diagnostics.describe(p,plan_review=a['plan_review'],native_reviews=a['native_reviews'],result=r)
        row=next(x for x in diagnostic['methods'] if x['method']==orders.METHOD)
        assert row['certificate']['conclusion']=='PARTIAL'
        assert row['certificate']['separate_interval_subtraction'] is False
        assert len([k for k in p['methods'][0]['science_worksheet']['decisions'] if k.startswith('mean_order_axis:')])==8
    assert len(set(targets))==1 and values[0]==values[1]==values[2]
    assert widths==sorted(widths)


@pytest.mark.parametrize('kwargs,expected',[(dict(supported=True),['1/5','1/5']),(dict(cancellation=True),['0','0'])])
def test_point_and_whole_case_reuse_the_same_reviews_and_verifier(kwargs,expected):
    s,e,o,p,a,r=execute(**kwargs)
    assert r['state']=='POINT' and r['mathematical_claim']['interval']==expected
    row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    result=business_case.execute_case(s,{'q1':row},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert result['state']=='ALL_QUERIES_IDENTIFIED' and result['identified_query_ids']==['q1']


@pytest.mark.parametrize('mutation,state',[
    ('missing_axis','NEEDS_INPUT'),('unadopted_unknown','NEEDS_INPUT'),('missing_level','NEEDS_INPUT'),
    ('observed_pattern','NEEDS_INPUT'),('historical_scope','NEEDS_INPUT'),('pathwise','ADAPTER_NOT_CONNECTED'),
    ('no_effect','ADAPTER_NOT_CONNECTED'),('rejected_complete_model','ADAPTER_NOT_CONNECTED'),
    ('unknown_complete_model','NEEDS_INPUT'),('coupling_conflict','READING_RECHECK_REQUIRED'),
    ('duplicate_axis','CHECK_BLOCKED'),('bad_reference','CHECK_BLOCKED'),
    ('sample_a4','NEEDS_INPUT'),('missing_population','NEEDS_INPUT'),
    ('different_population','ADAPTER_NOT_CONNECTED'),('different_context','ADAPTER_NOT_CONNECTED'),
    ('unknown_direction','NEEDS_INPUT'),('extra_restriction','ADAPTER_NOT_CONNECTED'),
    ('other_design','ADAPTER_NOT_CONNECTED'),('other_exposure','ADAPTER_NOT_CONNECTED'),
])
def test_missing_conflicting_and_uncovered_models_never_call_backend(monkeypatch,mutation,state):
    s,e,o=setup();c=o['candidate'];m=c['mean_order_model'];r=m['order_reading'];claim=r['claims'][0]
    if mutation=='missing_axis':r['claims'].pop()
    elif mutation=='unadopted_unknown':claim['relation']='UNKNOWN'
    elif mutation=='missing_level':claim['level']='UNKNOWN'
    elif mutation=='observed_pattern':claim['basis']='OBSERVED_PATTERN'
    elif mutation=='historical_scope':claim['scope']='HISTORICAL_SUPPORT'
    elif mutation=='pathwise':claim['level']='EACH_OUTCOME'
    elif mutation=='no_effect':claim['relation']='NO_EFFECT'
    elif mutation=='rejected_complete_model':m['no_additional_constraints_beyond_declared_orders']['value']=False
    elif mutation=='unknown_complete_model':m['no_additional_constraints_beyond_declared_orders']['value']=None
    elif mutation=='coupling_conflict':c['bounded_model']['no_additional_coupling_constraints']['value']=True
    elif mutation=='duplicate_axis':r['claims'].append(deepcopy(claim))
    elif mutation=='bad_reference':claim['source_ids']=['s9999']
    elif mutation=='sample_a4':c['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    elif mutation=='missing_population':c['target']['second']['population']=None
    elif mutation=='different_population':c['target']['second']['population']=['甲店']
    elif mutation=='different_context':c['target']['shared_outcome_and_context']['value']=False
    elif mutation=='unknown_direction':c['target']['operation']='UNKNOWN'
    elif mutation=='extra_restriction':c['additional_restrictions']=[dict(text='另有未接入的跨对象等式。',source_ids=claim['source_ids'])]
    elif mutation=='other_design':c['assignment'].update(kind='INDEPENDENT_BERNOULLI',fixed_count=None,probabilities={n:'1/2' for n in c['study']['nodes']})
    elif mutation=='other_exposure':c['exposure']['kind']='ANY_TREATED_NEIGHBOR'
    monkeypatch.setattr(mean_order,'submit',lambda *a,**k:pytest.fail('No reviewed model'))
    before=deepcopy(c);result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']==state, result.get('reason_code')
    assert not result['backend_called'] and result['mathematical_claim'] is None and c==before


@pytest.mark.parametrize('stage',['plan','reading','science_axis'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_each_review_layer_remains_required(monkeypatch,stage,decision):
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    if stage=='plan':record=a['plan_review'];key=next(iter(record.decisions))
    else:
        record=a['native_reviews'][orders.METHOD]['science_review' if stage=='science_axis' else 'reading_review']
        key=next(k for k in record.decisions if k.startswith('mean_order_axis:')) if stage=='science_axis' else 'source_entailment'
    record.decisions[key]=decision
    monkeypatch.setattr(mean_order,'submit',lambda *a,**k:pytest.fail('Review not accepted'))
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if decision=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called']


def test_new_assumptions_and_reverse_direction_cannot_reuse_old_reviews():
    s,e,o,p,a,r=execute()
    changed=deepcopy(o)
    claim=changed['candidate']['mean_order_model']['order_reading']['claims'][1]
    claim.update(relation='NOT_ASSUMED',level=None,scope=None)
    blocked=dispatch.execute(s,'q1',**changed,**a)
    assert blocked['state']=='CHECK_BLOCKED' and not blocked['backend_called']
    _,_,_,_,_,reverse=execute(reverse=True)
    assert reverse['mathematical_claim']['interval']==['-1','-1/5']
    changed=deepcopy(o);t=changed['candidate']['target'];t['first'],t['second']=t['second'],t['first']
    assert dispatch.execute(s,'q1',**changed,**a)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('mutation',['bound','primal','dual','other_target','mutated_problem'])
def test_native_certificate_or_problem_tampering_never_reports_success(monkeypatch,mutation):
    original=mean_order.solve
    def tampered(problem):
        result=original(problem)
        if mutation=='bound':result['lower']='99'
        elif mutation=='primal':result['cells'][0]['lower_world']='99'
        elif mutation=='dual':result['lower_dual']={}
        elif mutation=='other_target':
            other=problem.model_copy(update={'first':problem.second,'second':problem.first})
            result=original(other)
        else:problem.first[0]=1-problem.first[0]
        return result
    monkeypatch.setattr(mean_order,'solve',tampered)
    *_,r=execute()
    assert r['state']=='CHECK_BLOCKED' and r['mathematical_claim'] is None and not r['independent_replay']


def test_incompatible_model_has_farkas_replay_and_no_interval():
    def inconsistent(c):c['bounded_model']['bounds'][0].update(lower='0',upper='1/4')
    *_,r=execute(options=inconsistent)
    assert r['state']=='INCOMPATIBLE' and r['incompatibility_proved'] and r['independent_replay']
    assert r['mathematical_claim'] is None and r['answers']==[]
    p=MeanOrderProblem.model_validate(r['native_evidence']['problem'])
    assert mean_order_verify.replay(r['incompatibility_certificate'],problem=p)


def test_extension_is_source_reviewable_and_legacy_profiles_remain_strict():
    from cfm_id.fact_source_review import prepare
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    s,e,o=setup();sheet=prepare(e,o['candidate'])
    assert '/mean_order_model/order_reading/claims/0' in sheet['fields']
    contract=contract_for_entry(e)
    assert contract.profile==PROFILE and contract.model==reading.reading_model(PROFILE)
    decoded=contract.parse_candidate(e,o['candidate'])
    refs=reading.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    assert decoded['mean_order_model']['order_reading']['claims'][0]['source_ids']==[
        refs['aliases'][key]['source_id'] for key in o['candidate']['mean_order_model']['order_reading']['claims'][0]['source_ids']]
    for profile in (None,'network-source-selections-alignment-1'):
        with pytest.raises(ValueError):reading.reading_model(profile).model_validate(o['candidate'])
    legacy=reading.make_request(e['bundle'],binding=e['fact_binding_sha256'],profile='network-source-selections-alignment-1')
    assert 'mean_order_model' not in json.loads(legacy['user'])['output_schema']['properties']
    assert legacy['system']==e['request']['system']


def test_missing_supported_a4_is_not_filled_by_order_constraints():
    def missing(c):
        c['information'][0]['signature_cells']=[v for v in c['information'][0]['signature_cells']
            if not (v['node']=='甲店' and v['own']==1)]
    *_,r=execute(options=missing,supported=True)
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='SUPPORTED_NONZERO_TARGET_A4_MEAN_MISSING'
    assert not r['backend_called'] and r['mathematical_claim'] is None


def test_recheck_keeps_order_fields_and_invalidates_sources_and_science():
    from cfm_id import fact_source_review as source, fact_reading_revision as revision
    from cfm_id_llm.wire_type_diagnostics import diagnose
    from tests_gateway.test_fact_source_review import record
    from tests_gateway.test_fact_reading_revision import feedback,accept_changes
    s,e,o=setup();old_source=record(source.prepare(e,o['candidate']))
    old_reviews=approval_records(dispatch.inspect_methods(s,'q1',**dict(o,source_review=old_source)))
    bad=deepcopy(o['candidate'])
    bad['mean_order_model']['order_reading']['claims'][0]['relation']='INVALID'
    path='/mean_order_model/order_reading/claims/0/relation'
    assert any(row['field_path']==path for row in diagnose(e,bad))
    w=revision.prepare_recheck(s,'q1',**dict(o,candidate=bad))['feedback_worksheet']
    revised=revision.prepare_recheck(s,'q1',**dict(o,candidate=bad),
        feedback=feedback(w,path=path,kind='WIRE_FORMAT_ERROR',doc='orders'))
    raw=deepcopy(o['candidate'])
    raw['reference_context']=reading.reference_catalog(revised['bundle'],binding=revised['fact_binding_sha256'])['context']
    options=dict(query_review=o['query_review'],candidate=raw,request_sha256=revised['request_sha256'],
                 reading_revision=revised['reading_revision'])
    p=dispatch.inspect_methods(s,'q1',**options)
    options['change_review']=accept_changes(p['reading_change_worksheet'])
    assert dispatch.execute(s,'q1',**dict(options,source_review=old_source),research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    options['source_review']=record(source.prepare(revised,raw))
    assert dispatch.execute(s,'q1',**options,**old_reviews)['state']=='CHECK_BLOCKED'
    p=dispatch.inspect_methods(s,'q1',**options)
    r=dispatch.execute(s,'q1',**options,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay']
    options['source_review']['decisions']['/mean_order_model/order_reading/claims/0']['source_coverage']='REJECTED'
    blocked=dispatch.execute(s,'q1',**options,**approval_records(p))
    assert blocked['state']=='READING_RECHECK_REQUIRED' and not blocked['backend_called']
