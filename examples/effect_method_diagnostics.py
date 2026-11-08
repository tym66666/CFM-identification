"""Offline direct/spillover diagnostics using actual native solvers and replay.

Hand-authored readings and explicit synthetic reviews, never LLM measurements.
The missing-design/sample/post-assignment cases have matching original materials.
"""
from pathlib import Path
from cfm_id import business_dispatch as dispatch, business_intake as intake, method_diagnostics
from cfm_id.network_effect_dispatch import METHOD
from .network_effect_dispatch_reference import setup, approval_records
from .network_design_exposure_reference import setup as design_setup


def scenarios():
    yield 'direct_all', setup(), None
    yield 'direct_subset', setup(population='subset'), None
    yield 'spillover_single', setup('q2', population='single'), None
    yield 'reversed_direct', design_setup('D2','E4',reverse=True), None
    yield 'd6_spillover_count_exposure', design_setup('D6','E4','spillover'), None
    yield 'remaining_design_missing', setup(missing_remaining=True), None
    yield 'finite_sample_only', setup(sample_only=True), None
    yield 'population_selected_after_assignment', setup(post_assignment=True), None
    session, entry, options, plan = setup()
    options['candidate']['assignment']['probabilities']['甲店'] = '1'
    plan = dispatch.inspect_methods(session, 'q1', **options)
    yield 'anchor_point_but_effect_zero_support', (session,entry,options,plan), 'READING_PROBABILITY_CHANGED_FOR_SUPPORT_TEST'
    yield 'science_pending', setup(), 'SCIENCE_REVIEW_PENDING'


def run(output):
    path = Path(output); path.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, (session, entry, options, plan), fault in scenarios():
        approvals = approval_records(plan) if 'plan_worksheet' in plan else dict(research_protocol_selected=True)
        if fault == 'SCIENCE_REVIEW_PENDING':
            approvals['native_reviews'][METHOD]['science_review'].decisions['full_vector_randomization'] = 'PENDING'
        reviews = {k:v for k,v in approvals.items() if k != 'research_protocol_selected'}
        before = method_diagnostics.describe(plan, **reviews)
        result = dispatch.execute(session, plan['query_id'], **options, **approvals)
        after = method_diagnostics.describe(plan, result=result, **reviews) if 'plan_worksheet' in plan else before
        intake.write_json(path/(name+'.json'), dict(original_business=session.case.model_dump(mode='json'),
            hand_authored_reading=options['candidate'], deliberate_test_fault=fault,
            plan=plan, result=result, before=before, after=after))
        method = after['methods'][0]
        rows.append(dict(case=name, query_id=plan['query_id'], state=result['state'],
            backend_called=result['backend_called'], independent_replay=result['independent_replay'],
            reason=result.get('reason_code'), target=after['effect']['ordered_target'],
            mathematics=method['mathematical_applicability'], execution=method['execution'],
            certificate=method['certificate']['state'],
            calculation=method['certificate'].get('calculation_reported')))
    summary = dict(api_calls=0, hand_authored_readings=True, synthetic_reviews_only=True,
                   diagnostics_not_certificates=True, cases=rows)
    intake.write_json(path/'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-synthetic-reviews', action='store_true')
    args = parser.parse_args()
    if not args.allow_synthetic_reviews:
        parser.error('Explicit synthetic review selection required')
    print(json.dumps(run(args.output), ensure_ascii=False))
