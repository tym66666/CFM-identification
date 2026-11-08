"""Reproduce the synthetic joint-contrast acceptance and fixed-input ladder.

Offline only. No credentials, external requests, production route registration,
or arbitrary adapter loading. Existing output directories are never replaced.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from cfm_id_bridge.scientific_binding import canonical_data, sha
from evaluation.partial_extension_acceptance import evaluate
from examples.partial_contrast_reference import BoundedContrastReference
from examples.partial_extension_reference import BoundedPolicyReference


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    records={}

    def save(path, data):
        with (output/path).open('x',encoding='utf8') as stream:
            json.dump(canonical_data(data),stream,ensure_ascii=False,indent=2)
            stream.write('\n')

    class RecordingContrast(BoundedContrastReference):
        def run(self,case):
            result=super().run(case)
            records[case.name]=(case.payload,result)
            save(case.name+'.json',dict(input=case.payload,result=result,
                expected_state=case.expected_state,expected_interval=case.expected_interval,
                actual_llm_call=False,scientific_review_kind='EXPLICIT_SYNTHETIC_FIXTURE'))
            return result

    contrast=evaluate(RecordingContrast())
    single=evaluate(BoundedPolicyReference())
    save('CONTRAST_ACCEPTANCE.json',contrast)
    save('SINGLE_REFERENCE_ACCEPTANCE.json',single)
    ladder=[]
    for name in ('ladder_point','ladder_informative_science','ladder_logical_only'):
        p,r=records[name];cert=r['bounded_result']
        invariant=dict(bundle=p['bundle'],raw=p['raw'],inquiries=p['inquiries'],
            information={s:p['information'][s].model_dump(exclude={'bounds'}) for s in ('first','second')})
        ladder.append(dict(case=name,fixed_problem_sha256=sha(invariant),
            scientific_mean_bounds=[p['information']['first'].bounds[0].lower,p['information']['first'].bounds[0].upper],
            identified_interval=[cert['lower'],cert['upper']],state=r['state'],sharp=cert['sharp'],
            a4_gain_relative_to_stage_scientific_bounds=cert['informative'],
            fixed_binary_logic_range=['-1','1'],joint_review_sha256=r['joint_review_sha256'],
            independent_replay=r['bounded_certificate_replayed'],evidence_file=name+'.json'))
    invariant=len({r['fixed_problem_sha256'] for r in ladder})==1
    separate_reviews=len({r['joint_review_sha256'] for r in ladder})==3
    ranges=[tuple(map(Fraction,r['identified_interval'])) for r in ladder]
    nested=all(a[0]>=b[0] and a[1]<=b[1] for a,b in zip(ranges,ranges[1:]))
    if not (invariant and separate_reviews and nested and all(r['independent_replay'] for r in ladder)):
        raise ValueError('ASSUMPTION_LADDER_ACCEPTANCE_FAILED')
    save('ASSUMPTION_LADDER.json',dict(stages=ladder,same_problem_target_and_a4=invariant,
        separate_bound_reviews=separate_reviews,nested_intervals=nested,
        last_stage='SHARP_LOGICAL_INTERVAL_NOT_UNBOUNDED_OR_UNSUPPORTED'))
    summary=dict(status='PASS',completed_at_utc=datetime.now(timezone.utc).isoformat(),
        contrast_cases=contrast['cases'],single_reference_cases=single['cases'],
        contrast_rehashed_forgery_rejections=sum(len(r['forged_certificates_rejected']) for r in contrast['rows']),
        single_rehashed_forgery_rejections=sum(len(r['forged_certificates_rejected']) for r in single['rows']),
        same_problem_assumption_ladder=True,http_calls=0,llm_accuracy_measured=False,
        production_admission=False,estimation_handoff_allowed=False)
    save('SUMMARY.json',summary)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    save('EVIDENCE_HASHES.json',manifest)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args(argv)
    print(json.dumps(run(args.output_dir),ensure_ascii=False))


if __name__=='__main__':main()
