"""Route-neutral, offline business intake. Model execution is a separate opt-in."""
import argparse
import json
from pathlib import Path

from . import business_intake as work
from cfm_id_llm.compact_response_contract import PROFILES as A0_RESPONSE_PROFILES
from cfm_id_llm.compact_reference_contract import PROFILES as A0_REFERENCE_PROFILES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('new', 'request', 'candidate', 'inspect', 'plan', 'reply', 'replies', 'revise','recheck','review-changes','review-stop'):
        p = sub.add_parser(name)
        p.add_argument('--output', required=True)
        if name == 'new':
            inputs = p.add_mutually_exclusive_group(required=True)
            inputs.add_argument('--question-file')
            inputs.add_argument('--case-json')
            p.add_argument('--case-id', default='business_case')
            p.add_argument('--reading-config', help='Developer reading configuration JSON; no routes or permissions')
            p.add_argument('--a0-reference-contract',choices=A0_REFERENCE_PROFILES)
            p.add_argument('--a0-response-contract',choices=A0_RESPONSE_PROFILES)
        else:
            p.add_argument('--intake', required=True)
        if name == 'candidate':
            p.add_argument('--candidate', required=True)
            p.add_argument('--request', required=True)
        if name == 'reply':
            p.add_argument('--plan', required=True)
            p.add_argument('--clarification-id', required=True)
            p.add_argument('--reply-file', required=True)
        if name == 'revise':
            p.add_argument('--case-json', required=True)
            p.add_argument('--reason', required=True)
        if name == 'replies':
            p.add_argument('--plan', required=True)
            p.add_argument('--replies-json', required=True, help='Source-reviewed question IDs mapped to answer text')
        if name == 'recheck':
            p.add_argument('--feedback')
            p.add_argument('--authority',choices=['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST'],default='EXTERNAL_RESEARCH_REVIEW')
        if name == 'review-changes':p.add_argument('--review',required=True)
        if name == 'review-stop':
            p.add_argument('--review')
            p.add_argument('--target-fields', help='Optional query IDs mapped to target fields needing source review')
            p.add_argument('--authority',choices=['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST'],default='EXTERNAL_RESEARCH_REVIEW')
    args = parser.parse_args(argv)
    try:
        if Path(args.output).exists():
            raise work.IntakeError('OUTPUT_ALREADY_EXISTS')
        if args.command == 'new':
            case = (work.read_json(args.case_json) if args.case_json else
                    dict(case_id=args.case_id, business_question=Path(args.question_file).read_text('utf-8-sig')))
            if args.reading_config:
                if args.a0_reference_contract is not None or args.a0_response_contract is not None:
                    raise work.IntakeError('READING_CONFIG_CANNOT_MIX_WITH_LEGACY_FLAGS')
                result = work.start_configured(case, work.read_json(args.reading_config))
            else:
                result = work.start(case,a0_reference_contract=args.a0_reference_contract,
                                    a0_response_contract=args.a0_response_contract)
        else:
            s = work.restore(args.intake)
            if args.command == 'request': result = work.prepare_request(s)
            elif args.command == 'inspect': result = work.inspect(s)
            elif args.command == 'plan': result = work.clarification_plan(s)
            elif args.command == 'candidate':
                request = work.read_json(args.request)
                if request != work.prepare_request(s):
                    raise work.IntakeError('STALE_OR_CHANGED_REQUEST')
                result = work.receive_candidate(s, work.read_json(args.candidate),
                                                request_sha256=request['request_sha256'])
            elif args.command == 'reply':
                result = work.append_reply(s, work.read_json(args.plan), args.clarification_id,
                                           Path(args.reply_file).read_text('utf-8-sig'))
            elif args.command=='replies':
                result=work.append_replies(s,work.read_json(args.plan),work.read_json(args.replies_json))
            elif args.command=='recheck':
                from .intake_reading_revision import prepare_recheck
                result=prepare_recheck(s,feedback=work.read_json(args.feedback) if args.feedback else None,authority=args.authority)
            elif args.command=='review-changes':
                from .intake_reading_revision import review_changes
                result=review_changes(s,work.read_json(args.review))
            elif args.command=='review-stop':
                from .intake_stop_review import prepare_review,review_stop
                if args.review and args.target_fields:
                    raise work.IntakeError('TARGET_FIELDS_ARE_ALREADY_BOUND_IN_REVIEW')
                result=(review_stop(s,work.read_json(args.review),authority=args.authority) if args.review
                        else prepare_review(s,authority=args.authority,
                            target_fields=work.read_json(args.target_fields) if args.target_fields else None))
            else:
                result = work.revise_materials(s, work.read_json(args.case_json), reason=args.reason)
        if isinstance(result, work.BusinessIntake): work.save(result, args.output)
        else: work.write_json(args.output, result)
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        reason = str(exc) if type(exc) is work.IntakeError else 'INTAKE_INPUT_OR_OUTPUT_REJECTED'
        print(json.dumps(dict(status='FAILED', reason_code=reason, api_calls=0)))
        return 2
    print(json.dumps(dict(status='SAVED', api_calls=0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
