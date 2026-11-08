"""Offline whole-case planning and execution; no route selection or API calls."""
import argparse
import json
from pathlib import Path
from . import business_intake as intake
from . import business_case as work


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('plan', 'execute'):
        p = sub.add_parser(name)
        p.add_argument('--intake', required=True)
        p.add_argument('--output', required=True)
        if name == 'plan':
            p.add_argument('--query-reviews')
        else:
            p.add_argument('--submissions', required=True)
            p.add_argument('--case-review', required=True)
            p.add_argument('--select-research-protocol', action='store_true')
    a = parser.parse_args(argv)
    try:
        if Path(a.output).exists():
            raise ValueError('OUTPUT_EXISTS')
        s = intake.restore(a.intake)
        if a.command == 'plan':
            result = work.prepare_case(s, query_reviews=intake.read_json(a.query_reviews) if a.query_reviews else None)
        else:
            result = work.execute_case(s, intake.read_json(a.submissions),
                case_review=intake.read_json(a.case_review), research_protocol_selected=a.select_research_protocol)
        intake.write_json(a.output, result)
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        print(json.dumps(dict(status='FAILED', reason_code='CASE_INPUT_OR_OUTPUT_REJECTED', api_calls=0)))
        return 2
    print(json.dumps(dict(status='SAVED', state=result['state'], api_calls=0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
