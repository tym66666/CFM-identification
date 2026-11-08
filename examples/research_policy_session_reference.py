"""Offline synthetic policy-session acceptance; never imported by runtime."""
from pathlib import Path
import argparse
import json
from cfm_id import research_session as work, session_policy_routes as routes
from .research_item_review_reference import approve_items, decide


def policy(name='star5', *, bounded=False, population=None):
    from . import bounded_policy_fixture as fixture
    lane = routes.BOUNDED_POLICY if bounded else routes.POLICY
    native = fixture.reviews(name, population)
    return lane, fixture.public_bundle(name, population), fixture.reference(name, population), {
        key: native[key] for key in routes.fields(lane)}


def comparison(only=('q1', 'q2')):
    from . import fixed_comparison_fixture as fixture
    bundle = fixture.public_bundle(only=list(only))
    candidate = fixture.reference(bundle)
    native = fixture.reviews(bundle, candidate)
    return routes.COMPARISON, bundle, candidate, {key: native[key] for key in routes.fields(routes.COMPARISON)}


def contrast(*, first=None, second=None, payload=None):
    from .bounded_contrast_fixture import make_case, reviews
    from .partial_contrast_reference import joint_review
    if payload is None:
        nodes = list('ABCD')
        payload = make_case(nodes, list(zip(nodes[:-1], nodes[1:])), 2,
            [1]*4 if first is None else first, [0]*4 if second is None else second, nodes, serial=125)
    native = reviews(payload)
    native.pop('synthetic_protocol_selected')
    native.update(query_id='q1', information=payload['information'], joint_review=joint_review(payload, native))
    return routes.BOUNDED_COMPARISON, payload['bundle'], payload['raw'], native


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    cases = [
        ('policy_formula', lambda: policy(), 'POINT'),
        ('comparison_formula', comparison, 'POINT'),
        ('policy_partial', lambda: policy('star7', bounded=True), 'PARTIAL'),
        ('policy_finite_point', lambda: policy('star5', bounded=True), 'POINT'),
        ('contrast_partial', contrast, 'PARTIAL'),
        ('contrast_finite_point', lambda: contrast(first=[1,1,0,0], second=[0,0,1,1]), 'POINT'),
        ('unknown_policy_cancels', lambda: contrast(second=[1]*4), 'POINT'),
        ('point_lane_support_gap', lambda: policy('star7'), 'UNSUPPORTED'),
    ]
    for name, factory, expected in cases:
        lane, bundle, candidate, native = factory()
        folder = output / name
        s = work.receive_candidate(work.start(lane, bundle), candidate)
        s = work.begin_item_review(s, native_submission=native)
        work.write_json(folder / 'worksheet.json', work.item_review_worksheet(s))
        s = approve_items(s)
        work.save(s, folder / 'reviewed.json')
        restored = work.restore(folder / 'reviewed.json')
        missing = work.execute(restored, research_protocol_selected=True)
        assert missing['mathematical_claim'] is None and not missing['backend_called']
        result = work.execute(restored, native_submission=native, research_protocol_selected=True)
        assert result['state'] == expected, (name, result['state'], result['reason_code'])
        assert result['independent_replay'] == (expected != 'UNSUPPORTED')
        if name == 'unknown_policy_cancels':
            assert result['mathematical_claim']['interval'] == ['0','0']
        work.write_json(folder / 'result.json', result)
        item = next(r for r in restored.item_review.items if r.category == 'A5')
        withdrawn = decide(restored, item.item_id, 'WITHDRAWN')
        work.save(withdrawn, folder / 'withdrawn.json')
        stop = work.execute(withdrawn, native_submission=native, research_protocol_selected=True)
        assert stop['state'] == 'REVIEW_REQUIRED' and stop['mathematical_claim'] is None and not stop['backend_called']
        work.write_json(folder / 'withdrawn_result.json', stop)
        rows.append(dict(case=name, lane=lane, state=result['state'],
            independent_replay=result['independent_replay'], items=len(s.item_review.items),
            interval=(result['mathematical_claim'] or {}).get('interval'), withdrawal_blocks=True))
    summary = dict(passed=True, cases=rows, api_calls=0, synthetic_only=True, production_admission=False)
    work.write_json(output / 'SUMMARY.json', summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-synthetic-reviews', action='store_true')
    args = parser.parse_args(argv)
    if not args.allow_synthetic_reviews:
        parser.error('Explicit synthetic protocol selection is required')
    print(json.dumps(run(args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
