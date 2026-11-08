"""Offline bridge from neutral intake to reviewed method checks; no API calls."""
import argparse
import json
from pathlib import Path
from . import business_intake as intake
from . import business_dispatch as dispatch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('reader-plan', 'method-plan', 'execute', 'recheck-plan', 'information-evidence-plan', 'source-review-plan'):
        p = sub.add_parser(name)
        p.add_argument('--intake', required=True)
        p.add_argument('--query', required=True)
        p.add_argument('--query-review', required=name != 'reader-plan')
        p.add_argument('--output', required=True)
        p.add_argument('--reading-revision')
        if name != 'reader-plan':
            p.add_argument('--reader-plan', required=True)
            p.add_argument('--candidate', required=True)
            p.add_argument('--note-review')
            p.add_argument('--change-review')
        if name in ('method-plan','execute'):
            p.add_argument('--information-evidence-review')
            p.add_argument('--source-review')
        if name == 'recheck-plan':
            p.add_argument('--feedback')
        if name == 'execute':
            p.add_argument('--plan-review', required=True)
            p.add_argument('--native-reviews', required=True)
            p.add_argument('--select-research-protocol', action='store_true')
    a = parser.parse_args(argv)
    try:
        if Path(a.output).exists(): raise ValueError('OUTPUT_EXISTS')
        s = intake.restore(a.intake)
        query_review = intake.read_json(a.query_review) if a.query_review else None
        revision = intake.read_json(a.reading_revision) if a.reading_revision else None
        entry = dispatch.prepare_reader(s, a.query, query_review=query_review,reading_revision=revision)
        if a.command == 'reader-plan':
            result = entry
        else:
            saved = intake.read_json(a.reader_plan)
            if entry['state'] != 'READY_TO_READ' or saved != entry:
                raise ValueError('STALE_OR_CHANGED_READER_PLAN')
            options = dict(query_review=query_review, candidate=intake.read_json(a.candidate),
                           request_sha256=entry['request_sha256'],
                           note_review=intake.read_json(a.note_review) if a.note_review else None,reading_revision=revision,
                           change_review=intake.read_json(a.change_review) if a.change_review else None)
            if a.command in ('method-plan','execute') and a.information_evidence_review:
                options['information_evidence_review']=intake.read_json(a.information_evidence_review)
            if a.command in ('method-plan','execute') and a.source_review:
                options['source_review']=intake.read_json(a.source_review)
            if a.command == 'source-review-plan':
                if a.note_review or a.change_review:raise ValueError('SOURCE_WORKSHEET_IS_NOT_CHANGE_OR_NOTE_APPROVAL')
                from .fact_source_review import prepare
                result=dict(state='REVIEW_REQUIRED',source_review_worksheet=prepare(entry,options['candidate']),
                    api_calls=0,scientific_approval=False,backend_called=False)
            elif a.command == 'information-evidence-plan':
                if a.note_review or a.change_review:raise ValueError('EVIDENCE_WORKSHEET_IS_NOT_CHANGE_OR_NOTE_APPROVAL')
                from .network_information_evidence import prepare
                result=dict(state='REVIEW_REQUIRED',information_evidence_worksheet=prepare(entry,options['candidate']),
                    api_calls=0,scientific_approval=False,backend_called=False)
            elif a.command == 'recheck-plan':
                if a.note_review or a.change_review:raise ValueError('RESPONSE_REVIEW_IS_NOT_READING_FEEDBACK')
                from .fact_reading_revision import prepare_recheck
                result = prepare_recheck(s,a.query,**{k:v for k,v in options.items() if k not in ('note_review','change_review')},
                    feedback=intake.read_json(a.feedback) if a.feedback else None)
            else:
                result = dispatch.inspect_methods(s, a.query, **options)
            if a.command == 'execute' and result['state'] == 'REVIEW_REQUIRED' and 'plan_worksheet' in result:
                from .business_dispatch import native_reviews_from_json
                records = native_reviews_from_json(result, intake.read_json(a.native_reviews))
                result = dispatch.execute(s, a.query, **options,
                    plan_review=intake.read_json(a.plan_review), native_reviews=records,
                    research_protocol_selected=a.select_research_protocol)
        intake.write_json(a.output, result)
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        print(json.dumps(dict(status='FAILED', reason_code='DISPATCH_INPUT_OR_OUTPUT_REJECTED', api_calls=0)))
        return 2
    print(json.dumps(dict(status='SAVED', state=result['state'], api_calls=0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
