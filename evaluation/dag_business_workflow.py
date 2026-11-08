"""Offline CLI and one-call provider entry for the explicit DAG business bridge."""
import argparse,json
from copy import deepcopy
from pathlib import Path
from cfm_id_llm.dag_reading import make_request,public_bundle,ReadingError
from cfm_id.dag_business import (
    inspect_candidate,submit_reviewed,DagReadingReview,route_contract,reading_contract,CLASSICAL_ROUTE,ROUTE_IDS)
from evaluation.mean_order_workflow import load_json,write_json


def read_once(bundle,provider,*,allow_external=False,allow_document_sharing=False,route_id=CLASSICAL_ROUTE):
    if allow_external is not True or allow_document_sharing is not True:
        raise ReadingError('EXPLICIT_EXTERNAL_AND_DOCUMENT_SHARING_REQUIRED')
    route_contract(route_id)
    request_builder,_,_,_,_=reading_contract(route_id)
    bundle=public_bundle(bundle);request=request_builder(bundle)
    try:wire=deepcopy(provider.generate_json(system_prompt=request['system'],user_prompt=request['user']))
    except Exception:raise ReadingError('LLM_REQUEST_FAILED_NO_REPLY') from None
    return inspect_candidate(bundle,wire,route_id=route_id)


def main(argv=None):
    parser=argparse.ArgumentParser(description='DAG研究工作流；CLI离线，不创建审核，不调用API。')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('request','inspect','submit'):
        p=sub.add_parser(name);p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
        p.add_argument('--route',choices=ROUTE_IDS,default=CLASSICAL_ROUTE)
        if name!='request':p.add_argument('--candidate',required=True)
        if name=='submit':
            p.add_argument('--reading-review',required=True);p.add_argument('--science-review',required=True)
            p.add_argument('--select-research-protocol',action='store_true')
    args=parser.parse_args(argv)
    try:
        if Path(args.output).exists():raise ReadingError('OUTPUT_ALREADY_EXISTS')
        b=public_bundle(load_json(args.bundle))
        if args.command=='request':result=reading_contract(args.route)[0](b)
        elif args.command=='inspect':result=inspect_candidate(b,load_json(args.candidate),route_id=args.route)
        else:
            if not args.select_research_protocol:raise ReadingError('EXPLICIT_RESEARCH_SELECTION_REQUIRED')
            _,review_type,_,_,_=route_contract(args.route)
            result=submit_reviewed(b,load_json(args.candidate),route_id=args.route,
                reading_review=reading_contract(args.route)[2].model_validate(load_json(args.reading_review)),
                science_review=review_type.model_validate(load_json(args.science_review)),research_protocol_selected=True)
        write_json(args.output,result)
    except (ValueError,TypeError,KeyError,OSError):
        print(json.dumps(dict(status='FAILED',reason='DAG_WORKFLOW_INPUT_OR_OUTPUT_REJECTED',api_calls=0)));return 2
    print(json.dumps(dict(status='SAVED',state=result.get('state'),api_calls=0)));return 0


if __name__=='__main__':raise SystemExit(main())
