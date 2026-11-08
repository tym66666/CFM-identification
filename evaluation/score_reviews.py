"""Separate, offline scoring of HUMAN mathematical adjudications for a saved run.

No LLM calls, no proof certification. Run identity is SHA-bound so an adjudication
cannot be accidentally applied to a changed model output.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .real_benchmark import adjudication_summary, stable_sha256


def main(argv=None):
    p=argparse.ArgumentParser(description='Summarize two-reviewer mathematical review of a saved v0.4 model run')
    p.add_argument('--run',required=True,type=Path)
    p.add_argument('--reviews',required=True,type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args(argv)
    try:
        run=json.loads(args.run.read_text(encoding='utf-8'))
        if run.get('schema_version')!='cfm-id-evaluation-run-v0.4':raise ValueError('Wrong run schema')
        reviews=json.loads(args.reviews.read_text(encoding='utf-8'))
        summary=adjudication_summary(run,reviews)
        result={'schema_version':'cfm-id-reviewed-summary-v0.4',
                'run_sha256':stable_sha256(run),
                'manual_adjudication_summary':summary,
                'mathematically_certified':False,
                'note':'Substantive human review is not a formal theorem certificate.'}
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except Exception as exc:
        print(f'Human review scoring stopped safely ({type(exc).__name__}); check saved run hash and review records.',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
