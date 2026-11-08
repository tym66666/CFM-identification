"""Offline cross-route reference and gate acceptance through the explicit entry."""
from pathlib import Path
from collections import Counter
import argparse,json
from cfm_id.research_route_catalog import inventory
from cfm_id.research_route_entry import run_registered_route

def require(condition,case):
    if not condition:raise ValueError('REFERENCE_ACCEPTANCE_FAILED: '+case)

def evaluate_references():
    # Gold factories are confined to this explicitly selected offline acceptance.
    from examples.dag_backdoor_reference import cases as backdoor_cases,synthetic_review as backdoor_review,make_problem as backdoor_problem
    from examples.dag_adjustment_reference import cases as adjustment_cases,synthetic_review as adjustment_review,make_problem as adjustment_problem
    from examples.mean_order_fixture import make_problem as mean_problem,synthetic_review as mean_review
    from examples.dag_frontdoor_reference import cases as frontdoor_cases,synthetic_review as frontdoor_review,make_problem as frontdoor_problem
    from cfm_id.mean_order_contract import MeanOrderProblem
    rows=[]
    def record(route,name,problem,review,state,expected=None,selected=True,gate=False):
        payload=problem.model_dump() if hasattr(problem,'model_dump') else problem
        approval=review.model_dump() if hasattr(review,'model_dump') else review
        result=run_registered_route(route,payload,review=approval,research_protocol_selected=selected)
        label=str(route)+':'+name
        require(result['state']==state,label)
        proved=state in ('POINT','PARTIAL','INCOMPATIBLE')
        if proved:
            require(result['independent_replay'] and result['certificate'] is not None,label)
            if expected is not None:
                actual=(result['mathematical_claim'] if route=='MEAN_ORDER_D2_E1' else
                        result['certificate']['frontdoor_variable'] if route=='DAG_CLASSICAL_FRONTDOOR' else
                        result['certificate']['adjustment'])
                require(actual==expected,label)
        else:
            require(result['mathematical_claim'] is None and result['certificate'] is None,label)
            if expected is not None:require(result['reason_code']==expected,label)
        if gate:require(not result['backend_called'],label)
        require(result['production_admission'] is False and result['estimation_handoff_allowed'] is False,label)
        rows.append(dict(case=label,route_id=route,input=payload,review=approval,selected=selected,
                         expected_state=state,expected=expected,gate=gate,result=result))
    for route,cases,reviewer in [
        ('DAG_CLASSICAL_BACKDOOR',backdoor_cases(),backdoor_review),
        ('DAG_ADJUSTMENT',adjustment_cases(),adjustment_review),
        ('DAG_CLASSICAL_FRONTDOOR',frontdoor_cases(),frontdoor_review)]:
        for name,p,state,expected in cases:record(route,name,p,reviewer(p),state,expected)
    p=mean_problem();single=p.model_copy(update={'first':p.second})
    data=p.model_dump();data['values'][0]['value']='-1/10';incompatible=MeanOrderProblem.model_validate(data)
    # Expectations predate this integration: test_mean_order's four-node example.
    # With both monotonicities, m(1,1)>=3/5 and m(0,0)<=2/5, giving [1/5,1].
    for name,problem,state,expected in [
        ('network_partial',p,'PARTIAL',dict(kind='PARTIAL',representation='EXACT_IDENTIFIED_INTERVAL',interval=['1/5','1'],sharp=True)),
        ('network_point',single,'POINT',dict(kind='POINT',representation='EXACT_IDENTIFIED_INTERVAL',interval=['0','0'],sharp=True)),
        ('network_incompatible',incompatible,'INCOMPATIBLE',dict(kind='INCOMPATIBLE',representation='CONSTRAINT_CONTRADICTION',identified_set=None))]:
        record('MEAN_ORDER_D2_E1',name,problem,mean_review(problem),state,expected)
    bases=[
        ('DAG_CLASSICAL_BACKDOOR',backdoor_problem(),backdoor_review),
        ('DAG_ADJUSTMENT',adjustment_problem(),adjustment_review),
        ('MEAN_ORDER_D2_E1',p,mean_review),
        ('DAG_CLASSICAL_FRONTDOOR',frontdoor_problem(),frontdoor_review)]
    for i,(route,problem,reviewer) in enumerate(bases):
        review=reviewer(problem);wrong=bases[(i+1)%len(bases)]
        record(route,'review_missing',problem,None,'REVIEW_REQUIRED',gate=True)
        record(route,'selection_missing',problem,review,'REVIEW_REQUIRED',selected=False,gate=True)
        record(route,'selection_not_boolean',problem,review,'REVIEW_REQUIRED',selected=1,gate=True)
        changed=problem.model_dump();changed['context']+=' Revised target context.'
        record(route,'stale_review',changed,review,'CHECK_BLOCKED',gate=True)
        record(route,'wrong_family_problem',wrong[1],review,'CHECK_BLOCKED',gate=True)
        record(route,'wrong_family_review',problem,wrong[2](wrong[1]),'CHECK_BLOCKED',gate=True)
        malformed=problem.model_dump();malformed['approved_by_llm']=True
        record(route,'injected_approval',malformed,review,'CHECK_BLOCKED',gate=True)
        if route.startswith('DAG_'):
            for decision,state in [('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED')]:
                r=review.model_dump();r['decisions'][next(iter(r['decisions']))]=decision
                record(route,'science_'+decision.lower(),problem,r,state,gate=True)
            for positive,state in [(None,'NEEDS_INPUT'),(False,'UNSUPPORTED')]:
                pp=problem.model_dump();pp['information']['strictly_positive_joint']=positive
                record(route,'positivity_'+str(positive),pp,None,state,gate=True)
        else:
            r=review.model_dump();r['synthetic_fixture']=False
            record(route,'no_external_promotion',problem,r,'CHECK_BLOCKED',gate=True)
            pp=problem.model_dump();pp['first']=[1,1,0,0]
            pp['values']=[v for v in pp['values'] if (v['node'],v['own'],v['exposure'])!=('A',1,0)]
            incomplete=MeanOrderProblem.model_validate(pp)
            record(route,'missing_supported_target_mean',incomplete,mean_review(incomplete),'NEEDS_INPUT',gate=True)
    for route,state in [('GENERAL_GRAPHICAL_ID','CHECK_BLOCKED'),('IV','CHECK_BLOCKED'),
                        ('BOUNDED_POLICY_MEAN_D2_E1','UNSUPPORTED'),('R2_MEAN_SIGNATURE','UNSUPPORTED')]:
        record(route,'not_executable_here',{},None,state,gate=True)
    require(len({r['case'] for r in rows})==len(rows),'unique case IDs')
    return dict(version='research-route-acceptance-3',passed=True,cases=len(rows),catalog=inventory(),
        states=dict(Counter(r['result']['state'] for r in rows)),
        routes={route:dict(cases=sum(r['route_id']==route for r in rows),
                          states=dict(Counter(r['result']['state'] for r in rows if r['route_id']==route)))
                for route,_,_ in bases},
        rows=rows,http_calls=0,llm_accuracy_measured=False,default_core_modified=False,
        scope='Offline explicit synthetic references; mathematical entry only, no automatic business approval or route inference.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-synthetic-reviews',action='store_true');parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    if not args.allow_synthetic_reviews:parser.error('Explicit --allow-synthetic-reviews is required.')
    path=Path(args.output)
    if path.exists():parser.error('Output already exists; preserve prior evidence.')
    report=evaluate_references()
    with path.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','http_calls','llm_accuracy_measured')}))

if __name__=='__main__':main()
