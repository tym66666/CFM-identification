"""Preserve original v2.2 32-card audit and append 5 LIVE R3 v2.3 cases.
No relabelling of B24 observational direct-effect: that target is not implemented.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,json

from .run_observational_r3_and_signature import case

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'assets/business_coverage_fixtures'/'CFM_ID_Business_Coverage_32_Cards.json'


def build_delta():
    baseline=json.loads(BASELINE.read_text(encoding='utf8'))
    if len(baseline.get('cards',[]))!=32 or len({x['case_id'] for x in baseline['cards']})!=32:
        raise ValueError('Original v2.2 32-card audit has changed unexpectedly')
    b24=next(x for x in baseline['cards'] if x['case_id']=='B24')
    if b24['l2_identification']!='NO_REGISTERED_THEOREM':
        raise ValueError('B24 observational direct effect must not be silently counted as R3 policy')
    real=case()['observational_policy']
    specs=[
      ('C33','supported_full','观测网络下有完整 assignment 支持的固定政策','R3_FULL_ASSIGNMENT'),
      ('C34','offsupport_with_mean_suff','观测网络 off-support 固定政策 + 已接受 mean-signature sufficiency','R3_MEAN_SIGNATURE'),
      ('C35','offsupport_without_mean_suff','相同政策但没有接受 mean-signature sufficiency','BLOCKED_PRECONDITION'),
      ('C36','exchangeability_not_confirmed','观测网络没有确认 full-vector conditional exchangeability','BLOCKED_PRECONDITION'),
      ('C37','only_finite_sample','观测网络只有有限样本统计而缺少总体 A4','BLOCKED_PRECONDITION'),
    ]
    additions=[]
    for cid,key,question,route in specs:
        result=real[key]
        additions.append(dict(case_id=cid,business_question=question,
            l0_target='FIXED_FULL_ASSIGNMENT_POLICY_MEAN',
            l1_route=result['route'] or route,
            l2_identification='POINT_VERIFIED' if result['status']=='POINT' else result['status'],
            observed_reason=result['reason_code'],
            l3_estimation='NO_NUMERIC_ESTIMATOR_VERIFIED' if result['status']=='POINT' else 'NOT_APPLICABLE_NO_POINT',
            a4_required_information='Exact conditional P_obs(T|W) plus node assignment conditional mean population operator',
            a5_required_assumptions='Full-vector conditional exchangeability, consistency, fixed network, integrability' +
                       ('; admitted mean-signature sufficiency' if key=='offsupport_with_mean_suff' else ''),
            a6_support_and_validity='Policy assignment support or per-node signature support (finite N <= 12)',
            evidence_type='LIVE_R3_FORMAL_THEOREM_AND_REPLAY' if result['status']=='POINT' else 'LIVE_SAFE_REFUSAL',
            note='Synthetic exact population fixture; not a real estimate; no automatic exchangeability validation'))
    return dict(version='v2.3',baseline_file=str(BASELINE.relative_to(ROOT)),
        baseline_cards=32,additional_r3_cards=len(additions),
        baseline_B24_observational_direct_effect_status=b24['l2_identification'],
        baseline_status_counts=baseline['counts'],
        additional_status_counts=dict(Counter(x['l2_identification'] for x in additions)),
        additions=additions,
        warning='These are synthetic safety audit cases, not a market coverage denominator. B24 remains unsupported.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=Path('showcase_v23'))
    args=p.parse_args();args.output_dir.mkdir(exist_ok=True,parents=True)
    data=build_delta();dest=args.output_dir/'CFM_ID_v2_3_Business_Coverage_Delta_32plus5.json'
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(version=data['version'],additions=data['additional_status_counts'],
                          old_B24=data['baseline_B24_observational_direct_effect_status'],output=str(dest)),
                     ensure_ascii=False,indent=2))


if __name__=='__main__':main()
