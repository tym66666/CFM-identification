"""Independent synthetic condition ladders using existing mathematics only."""
from pathlib import Path
import argparse
import json
from cfm_id import research_session as work, research_versions as versions
from cfm_id_bridge.scientific_binding import sha
from .research_item_review_reference import approve_items
from .research_session_reference import mean_order
from .research_policy_session_reference import contrast, policy


def policy_bounds(lower, upper):
    """Explicit test-only bounds declaration and independent native re-review."""
    from cfm_id.bounded_policy import worksheet
    lane,b,c,native = policy('star7',bounded=True)
    info = native['information']
    bounds = [row.model_copy(update={'lower':lower,'upper':upper}) if row.node=='H' else row for row in info.bounds]
    native['information'] = info.model_copy(update={'bounds':bounds,'bounds_kind':'CONDITIONAL_MEAN'})
    sheet = worksheet(b,c,**{k:native[k] for k in ('query_id','packet','context','information')})
    record = native['bounded_review'].model_dump()
    record.update(sheet, evidence='Independently stipulated synthetic conditional-mean bounds for this version; no real-world approval.')
    native['bounded_review'] = type(native['bounded_review']).model_validate(record)
    return lane,b,c,native


def reviewed(factory, *, parent=None, label='Synthetic baseline'):
    lane,b,c,native = factory()
    s = work.start(lane,b) if parent is None else versions.fork_version(parent,label=label,
        reason='Separate hypothetical condition version, independently reviewed and verified.',bundle=b)
    if s.candidate is None or sha(s.candidate)!=sha(c):
        s = work.receive_candidate(s,c)
    s = work.begin_item_review(s,native_submission=native)
    return approve_items(s),native


def run(output):
    from .partial_contrast_reference import ladder_payloads
    payloads = ladder_payloads()
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    series = [
        ('contrast_bounds', [('mean_half',lambda:contrast(payload=payloads[0])),
                             ('mean_quarter_to_three_quarters',lambda:contrast(payload=payloads[1])),
                             ('binary_logical_bounds',lambda:contrast(payload=payloads[2]))]),
        ('policy_bounds', [('hub_mean_half',lambda:policy_bounds('1/2','1/2')),
                           ('hub_mean_quarter_to_three_quarters',lambda:policy_bounds('1/4','3/4')),
                           ('hub_mean_zero_to_one',lambda:policy_bounds('0','1'))]),
        ('mean_orders', [('both_axes',lambda:mean_order(mode='BOTH')),
                         ('own_axis_only',lambda:mean_order(mode='OWN')),
                         ('neither_axis',lambda:mean_order(mode='NONE'))]),
    ]
    summaries=[]
    for name,factories in series:
        previous = None
        comparisons=[]
        for label,factory in factories:
            s,native = reviewed(factory,parent=previous[0] if previous else None,label=label)
            folder=output/name/label
            work.save(s,folder/'reviewed.json')
            restored=work.restore(folder/'reviewed.json')
            work.write_json(folder/'public_materials.json',restored.bundle)
            if previous:
                old,old_native=previous
                plan=versions.plan_comparison(old,restored,before_submission=old_native,after_submission=native)
                work.write_json(folder/'comparison_plan.json',plan)
                report=versions.compare_versions(old,restored,plan=plan,before_submission=old_native,
                    after_submission=native,research_protocol_selected=True)
                assert report['state']=='COMPARED', (name,report['state'],report['reason_code'],plan['reason_code'])
                assert report['conclusion']['declaration_relation']=='WEAKENING'
                assert report['both_results_independently_replayed']
                work.write_json(folder/'comparison_result.json',report)
                comparisons.append(dict(label=label,**report['conclusion']))
            previous=restored,native
        summaries.append(dict(series=name,comparisons=comparisons))
    summary=dict(passed=True,series=summaries,versions=9,comparisons=6,api_calls=0,synthetic_only=True)
    work.write_json(output/'SUMMARY.json',summary)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--allow-synthetic-reviews',action='store_true')
    args=parser.parse_args(argv)
    if not args.allow_synthetic_reviews:
        parser.error('Explicit synthetic protocol selection is required')
    result=run(args.output)
    print(json.dumps(dict(passed=result['passed'],versions=result['versions'],comparisons=result['comparisons'],
        intervals={s['series']:[s['comparisons'][0]['before_interval'],*[r['after_interval'] for r in s['comparisons']]]
                   for s in result['series']},api_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
