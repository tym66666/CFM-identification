"""Offline ordered comparison diagnostics with explicit synthetic reviews.

Uses existing native solvers/replayers. Fault-injected readings are labelled and
never repaired or treated as LLM accuracy measurements.
"""
from pathlib import Path
from cfm_id import business_dispatch as dispatch, business_intake as intake, method_diagnostics
from cfm_id.network_contrast_dispatch import R2_METHOD
from .network_contrast_dispatch_reference import setup, approval_records
from .network_r2_contrast_reference import setup as r2_setup


def scenarios():
    yield 'r1b_difference', setup(), None
    yield 'r1b_off_support_r2_point', r2_setup(information='full'), None
    yield 'joint_partial', setup('partial', bounds=('1/4','3/4')), None
    yield 'joint_cancellation_point', setup('cancellation'), None
    yield 'reversed_joint_cancellation', setup('cancellation', reverse=True), None
    yield 'one_endpoint_fails', r2_setup(quota=1), None
    s, e, o = setup()
    o['candidate']['target']['second']['assignment'] = None
    yield 'missing_second_reading', (s, e, o), 'READING_MISSING_SECOND'
    s, e, o = setup()
    o['candidate']['target']['second']['population'] = ['甲店']
    yield 'different_population_reading', (s, e, o), 'READING_DIFFERENT_POPULATION'
    yield 'r2_review_pending', r2_setup(information='full'), 'R2_REVIEW_PENDING'


def run(output):
    path = Path(output); path.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, (session, entry, options), fault in scenarios():
        plan = dispatch.inspect_methods(session, 'q1', **options)
        approvals = approval_records(plan) if 'plan_worksheet' in plan else dict(research_protocol_selected=True)
        if fault == 'R2_REVIEW_PENDING':
            review = approvals['native_reviews'][R2_METHOD]['science_review']
            review.decisions[next(iter(review.decisions))] = 'PENDING'
        reviews = {k:v for k,v in approvals.items() if k != 'research_protocol_selected'}
        before = method_diagnostics.describe(plan, **reviews)
        result = dispatch.execute(session, 'q1', **options, **approvals)
        after = method_diagnostics.describe(plan, result=result, **reviews) if 'plan_worksheet' in plan else before
        intake.write_json(path/(name+'.json'), dict(original_business=session.case.model_dump(mode='json'),
            hand_authored_reading=options['candidate'], deliberate_test_fault=fault,
            plan=plan, result=result, before=before, after=after))
        rows.append(dict(case=name, state=result['state'], backend_called=result['backend_called'],
            independent_replay=result['independent_replay'], reason=result.get('reason_code'),
            interval=(result.get('mathematical_claim') or {}).get('interval'),
            methods=[dict(method=m['method'], mathematics=m['mathematical_applicability'],
                execution=m['execution'], calculation=m['calculation_contract'],
                certificate=m['certificate']['state']) for m in after['methods']]))
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
