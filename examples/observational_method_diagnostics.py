"""Offline R3 diagnostics with existing solvers/replay and synthetic reviews.

Readings are hand-authored fixtures, not LLM quality measurements. Original
materials already distinguish missing/refused exchangeability, samples and zero
joint support. Other interventions below are explicitly marked test faults.
"""
from pathlib import Path
from cfm_id import business_dispatch as dispatch, business_intake as intake, method_diagnostics
from cfm_id.network_observational_policy_dispatch import METHOD
from .network_observational_policy_reference import setup, approval_records


def scenarios():
    yield 'care_all', setup(), None
    yield 'depots_subset', setup('depots'), None
    yield 'unknown_exchangeability', setup(exchangeability=None), None
    yield 'refused_exchangeability', setup(exchangeability=False), None
    yield 'finite_sample_only', setup(sample_only=True), None
    yield 'zero_joint_support', setup(zero_support=True), None
    yield 'exchangeability_review_pending', setup(), 'EXCHANGEABILITY_REVIEW_PENDING'
    yield 'same_context_review_rejected', setup(), 'SAME_CONTEXT_REVIEW_REJECTED'
    s,e,o = setup()
    o['candidate']['information'][0]['outcome_nodes'] = o['candidate']['study']['nodes'][:1]
    yield 'information_missing_evaluation_nodes', (s,e,o), 'READING_SCOPE_REMOVED_FOR_NEGATIVE_TEST'


def run(output):
    path = Path(output); path.mkdir(parents=True, exist_ok=False); rows = []
    for name, (s,e,o), fault in scenarios():
        plan = dispatch.inspect_methods(s,'q1',**o)
        approvals = approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
        if fault == 'EXCHANGEABILITY_REVIEW_PENDING':
            approvals['native_reviews'][METHOD]['science_review'].decisions['full_vector_conditional_exchangeability'] = 'PENDING'
        elif fault == 'SAME_CONTEXT_REVIEW_REJECTED':
            approvals['native_reviews'][METHOD]['science_review'].decisions['same_study_and_conditioning'] = 'REJECTED'
        reviews = {k:v for k,v in approvals.items() if k != 'research_protocol_selected'}
        before = method_diagnostics.describe(plan,**reviews)
        result = dispatch.execute(s,'q1',**o,**approvals)
        after = method_diagnostics.describe(plan,result=result,**reviews) if plan.get('plan_sha256') else before
        intake.write_json(path/(name+'.json'),dict(original_business=s.case.model_dump(mode='json'),
            hand_authored_reading=o['candidate'],deliberate_test_fault=fault,
            plan=plan,result=result,before=before,after=after))
        method = after['methods'][0]
        rows.append(dict(case=name,state=result['state'],reason=result.get('reason_code'),
            backend_called=result['backend_called'],independent_replay=result['independent_replay'],
            target=after['observational']['prepared_target'],
            joint_support=method['joint_policy_support']['state'],certificate=method['certificate']['state']))
    summary = dict(api_calls=0,hand_authored_readings=True,synthetic_reviews_only=True,
                   diagnostics_not_certificates=True,cases=rows)
    intake.write_json(path/'SUMMARY.json',summary)
    return summary


if __name__ == '__main__':
    import argparse,json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--allow-synthetic-reviews',action='store_true')
    args = parser.parse_args()
    if not args.allow_synthetic_reviews:
        parser.error('Explicit synthetic review selection required')
    print(json.dumps(run(args.output),ensure_ascii=False))
