"""Explicit synthetic item-review acceptance; never imported by runtime code."""
from pathlib import Path
import argparse
import json
from cfm_id import research_session as work, session_routes as routes
from cfm_id_bridge.scientific_binding import sha
from .research_session_reference import network, mean_order, dag

REVIEWER = 'Independent synthetic item reviewer'
EVIDENCE = 'This exact declaration is stipulated by the separate synthetic reference protocol; no real business approval.'


def decide(s, item_id, decision):
    return work.decide_item(s, dict(expected_review_sha256=sha(s.item_review),
        item_id=item_id, decision=decision, reviewer=REVIEWER, evidence=EVIDENCE))


def finalize(s):
    return work.finalize_item_review(s, expected_review_sha256=sha(s.item_review),
                                     reviewer=REVIEWER, evidence=EVIDENCE)


def approve_items(s):
    # Test fixtures only, not a public "accept all" command or business policy.
    for row in s.item_review.items:
        s = decide(s, row.item_id, 'ACCEPTED')
    return finalize(s)


def backdoor():
    from . import dag_business_reference as module
    c = module.cases()[0]
    reading, science = module.reference_reviews(c['bundle'], c['reference'])
    return routes.DAG[0], c['bundle'], c['reference'], dict(reading_review=reading, science_review=science)


def adjustment():
    from . import dag_adjustment_business_reference as module
    c = module.cases()[0]
    reading, science = module.reference_reviews(c['bundle'], c['reference'])
    return routes.DAG[1], c['bundle'], c['reference'], dict(reading_review=reading, science_review=science)


FACTORIES = (network, mean_order, backdoor, adjustment, dag)


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for factory in FACTORIES:
        folder = output / factory.__name__
        lane, bundle, candidate, native = factory()
        s = work.receive_candidate(work.start(lane, bundle), candidate)
        s = work.begin_item_review(s, native_submission=native)
        work.save(s, folder / 'pending.json')
        work.write_json(folder / 'worksheet.json', work.item_review_worksheet(s))
        reviewed = approve_items(s)
        work.save(reviewed, folder / 'reviewed.json')
        restored = work.restore(folder / 'reviewed.json')
        result = work.execute(restored, native_submission=native, research_protocol_selected=True)
        expected = 'PARTIAL' if lane == routes.MEAN_ORDER else 'POINT'
        assert result['state'] == expected and result['independent_replay'], (lane, result['state'])
        if expected == 'PARTIAL':
            assert result['mathematical_claim']['interval'] == ['1/5', '1']
        work.write_json(folder / 'result.json', result)
        item = next(r for r in restored.item_review.items if r.category == 'A5')
        withdrawn = decide(restored, item.item_id, 'WITHDRAWN')
        work.save(withdrawn, folder / 'withdrawn.json')
        stopped = work.execute(withdrawn, native_submission=native, research_protocol_selected=True)
        assert stopped['state'] == 'REVIEW_REQUIRED' and stopped['mathematical_claim'] is None
        assert not stopped['backend_called'] and not stopped['independent_replay']
        work.write_json(folder / 'withdrawn_result.json', stopped)
        rows.append(dict(lane=lane, items=len(s.item_review.items), state=result['state'],
            independent_replay=True, withdrawal_blocks_before_backend=True))
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
