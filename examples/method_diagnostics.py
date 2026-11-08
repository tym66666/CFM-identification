"""Offline route explanations from native plans/results; explicit synthetic reviews."""
from pathlib import Path
from cfm_id import business_dispatch as dispatch, business_intake as intake, method_diagnostics as diagnostics
from .network_dispatch_reference import setup, approval_records
from .network_bounded_dispatch_reference import setup as bounded


def scenarios():
    yield 'r1b_and_r2', setup(design='D1'), None
    yield 'r1b_zero_support_r2_point', setup(), None
    s,e,o,p=setup()
    o['candidate']['mean_sufficiency'].update(value=None,scope='UNKNOWN',covered_nodes=[],source_ids=[])
    yield 'r2_not_declared', (s,e,o,dispatch.inspect_methods(s,'q1',**o)), None
    yield 'finite_partial', bounded(center_bounds=('1/4','3/4')), None
    yield 'finite_model_missing', bounded(missing_scope=True), None
    yield 'r2_pending_blocks_all', setup(design='D1'), 'PENDING'
    yield 'additional_constraint_preserved', bounded(extra=True), None


def run(output):
    path=Path(output);path.mkdir(parents=True,exist_ok=False);rows=[]
    for name,(s,e,o,plan),decision in scenarios():
        before=diagnostics.describe(plan)
        approvals=approval_records(plan) if 'plan_worksheet' in plan else {}
        if decision:
            from cfm_id.network_policy_dispatch import R2,R2_SCIENCE_DECISIONS
            record=approvals['native_reviews'][R2]['science_review']
            decisions=dict(record.decisions);decisions[R2_SCIENCE_DECISIONS[0]]=decision
            approvals['native_reviews'][R2]['science_review']=record.model_copy(update={'decisions':decisions})
        result=dispatch.execute(s,'q1',**o,**approvals)
        after=(diagnostics.describe(plan,result=result,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})
               if 'plan_worksheet' in plan else diagnostics.describe(plan))
        intake.write_json(path/(name+'.json'),dict(original_business=s.case.model_dump(mode='json'),
            plan=plan,result=result,before=before,after=after))
        rows.append(dict(case=name,state=result['state'],reason=result.get('reason_code'),
            backend_called=result['backend_called'],independent_replay=result['independent_replay'],
            methods=[dict(method=r['method'],planning=r['planning_state'],mathematics=r['mathematical_applicability'],
                science_review=r['science_review']['state'],certificate=r['certificate']['state']) for r in after['methods']]))
    summary=dict(api_calls=0,synthetic_reviews_only=True,diagnostics_not_certificates=True,cases=rows)
    intake.write_json(path/'SUMMARY.json',summary)
    return summary


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true')
    args=p.parse_args()
    if not args.allow_synthetic_reviews:p.error('Explicit synthetic review selection required')
    print(json.dumps(run(args.output),ensure_ascii=False))
