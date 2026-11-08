"""Offline research CLI: inspect inventory, prepare typed input, submit separate review."""
import argparse,json
from pathlib import Path
from cfm_id.research_route_catalog import inventory,schemas
from cfm_id.research_route_entry import run_registered_route
from evaluation.mean_order_workflow import load_json,write_json

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('list','schema','prepare','submit','acceptance'):
        p=sub.add_parser(name);p.add_argument('--output',required=True)
        if name in ('schema','prepare','submit'):p.add_argument('--route',required=True)
        if name in ('prepare','submit'):p.add_argument('--problem',required=True)
        if name=='submit':
            p.add_argument('--review',required=True)
            p.add_argument('--select-research-protocol',action='store_true')
        if name=='acceptance':p.add_argument('--allow-synthetic-reviews',action='store_true')
    args=parser.parse_args(argv)
    try:
        if Path(args.output).exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
        if args.command=='list':result=inventory()
        elif args.command=='schema':result=schemas(args.route)
        elif args.command=='acceptance':
            if not args.allow_synthetic_reviews:raise ValueError('EXPLICIT_SYNTHETIC_SELECTION_REQUIRED')
            # Fixtures stay in an explicitly selected offline test command.
            from evaluation.research_route_acceptance import evaluate_references
            result=evaluate_references()
        else:
            if args.command=='submit' and not args.select_research_protocol:
                raise ValueError('EXPLICIT_RESEARCH_SELECTION_REQUIRED')
            result=run_registered_route(args.route,load_json(args.problem),
                review=load_json(args.review) if args.command=='submit' else None,
                research_protocol_selected=args.command=='submit')
        write_json(args.output,result)
    except (ValueError,TypeError,KeyError,OSError):
        print(json.dumps(dict(status='FAILED',reason='RESEARCH_ENTRY_INPUT_OR_OUTPUT_REJECTED',api_calls=0)))
        return 2
    print(json.dumps(dict(status='SAVED',state=result.get('state'),api_calls=0)))
    return 0

if __name__=='__main__':raise SystemExit(main())

