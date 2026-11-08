"""Offline session checkpoints and review files; never calls a model or loads keys."""
import argparse
import json
from . import research_session as work
from .session_routes import LANES,DAG


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('new','request','candidate','inspect','worksheet','review','plan','reply','revise','submit-dag',
                 'review-open-dag','review-items','review-decide','review-finalize','fork-version'):
        p=sub.add_parser(name);p.add_argument('--output',required=True)
        if name=='new':p.add_argument('--lane',choices=LANES,required=True)
        else:p.add_argument('--session',required=True)
        if name in ('new','revise'):p.add_argument('--bundle',required=True)
        if name=='revise':p.add_argument('--reason',required=True)
        if name=='fork-version':
            p.add_argument('--label',required=True);p.add_argument('--reason',required=True);p.add_argument('--bundle')
        if name=='candidate':p.add_argument('--candidate',required=True)
        if name in ('review','review-decide','review-finalize'):p.add_argument('--review',required=True)
        if name=='worksheet':
            p.add_argument('--reading-review');p.add_argument('--science-review')
        if name=='reply':
            p.add_argument('--plan',required=True);p.add_argument('--clarification-id',required=True)
            p.add_argument('--reply-file',required=True)
        if name in ('submit-dag','review-open-dag'):
            p.add_argument('--reading-review',required=True);p.add_argument('--science-review',required=True)
        if name=='submit-dag':
            p.add_argument('--select-research-protocol',action='store_true')
    a=parser.parse_args(argv)
    try:
        from pathlib import Path
        if Path(a.output).exists():raise work.SessionError('OUTPUT_ALREADY_EXISTS')
        if a.command=='new':result=work.start(a.lane,work.read_json(a.bundle))
        else:
            s=work.restore(a.session)
            if a.command=='request':result=work.prepare_request(s)
            elif a.command=='candidate':result=work.receive_candidate(s,work.read_json(a.candidate))
            elif a.command=='inspect':result=work.inspect(s)
            elif a.command=='worksheet':
                native=None
                if a.reading_review or a.science_review:
                    if not (a.reading_review and a.science_review) or s.lane not in DAG:
                        raise work.SessionError('BOTH_NATIVE_DAG_REVIEW_FILES_REQUIRED')
                    from .dag_business import route_contract,reading_contract
                    native=dict(reading_review=reading_contract(s.lane)[2].model_validate(work.read_json(a.reading_review)),
                                science_review=route_contract(s.lane)[1].model_validate(work.read_json(a.science_review)))
                result=work.review_worksheet(s,native_submission=native)
            elif a.command=='review':result=work.record_review(s,work.read_json(a.review))
            elif a.command=='review-items':result=work.item_review_worksheet(s)
            elif a.command=='review-decide':result=work.decide_item(s,work.read_json(a.review))
            elif a.command=='review-finalize':result=work.finalize_item_review(s,**work.read_json(a.review))
            elif a.command=='fork-version':
                from .research_versions import fork_version
                result=fork_version(s,label=a.label,reason=a.reason,bundle=work.read_json(a.bundle) if a.bundle else None)
            elif a.command=='plan':result=work.clarification_plan(s)
            elif a.command=='reply':result=work.append_reply(s,work.read_json(a.plan),a.clarification_id,Path(a.reply_file).read_text('utf-8-sig'))
            elif a.command=='revise':result=work.revise_materials(s,work.read_json(a.bundle),reason=a.reason)
            else:
                if s.lane not in DAG:raise work.SessionError('NATIVE_PYTHON_CONTEXT_REQUIRED_FOR_THIS_LANE')
                from .dag_business import route_contract,reading_contract
                native=dict(reading_review=reading_contract(s.lane)[2].model_validate(work.read_json(a.reading_review)),
                            science_review=route_contract(s.lane)[1].model_validate(work.read_json(a.science_review)))
                if a.command=='review-open-dag':result=work.begin_item_review(s,native_submission=native)
                else:result=work.execute(s,native_submission=native,research_protocol_selected=a.select_research_protocol)
        if type(result) is work.ResearchSession:work.save(result,a.output)
        else:work.write_json(a.output,result)
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
        reason=str(exc) if type(exc) is work.SessionError else 'SESSION_INPUT_OR_OUTPUT_REJECTED'
        print(json.dumps(dict(status='FAILED',reason_code=reason,api_calls=0)));return 2
    print(json.dumps(dict(status='SAVED',api_calls=0)));return 0


if __name__=='__main__':raise SystemExit(main())
