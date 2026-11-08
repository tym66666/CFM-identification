"""Whole-case coverage over independently reviewed query executions.

No query merging, default theorem selection, model calls, or restored-result
admission. A successful query cannot mark the remaining queries complete.
"""
from copy import deepcopy
from pydantic import BaseModel
from . import business_intake as intake_api
from . import business_dispatch as dispatch

CASE_DECISIONS = ('all_business_questions_represented', 'query_boundaries_and_targets_reviewed')
SUBMISSION_FIELDS = {'query_review', 'candidate', 'request_sha256', 'plan_review', 'native_reviews',
                     'note_review', 'reading_revision', 'change_review', 'information_evidence_review', 'source_review'}


def _base():
    return dict(state='CASE_INCOMPLETE', result_scope='WHOLE_BUSINESS_CASE',
        mathematical_claim=None, certificate=None, backend_called=False,
        production_admission=False, estimation_handoff_allowed=False,
        expected_query_ids=[], identified_query_ids=[], unresolved_query_ids=[],
        point_identified_query_ids=[], partially_identified_query_ids=[],
        all_queries_identified=False, all_queries_point_identified=False, results=[], case_worksheet=None)


def prepare_case(intake, *, query_reviews=None):
    out = _base()
    try:
        s = intake_api._checked(intake)
        reading = intake_api.inspect(s)
        if 'report' not in reading:
            return dict(out, state=reading['state'], reason_code=reading.get('reason_code'))
        queries = reading['report']['draft']['queries']
        ids = [q['query_id'] for q in queries]
        reviews = {} if query_reviews is None else query_reviews
        if type(reviews) is not dict or not set(reviews) <= set(ids):
            raise ValueError('EXACT_CURRENT_QUERY_IDS_REQUIRED')
        binding = intake_api._sha(s.model_dump(mode='json'))
        out.update(case_binding_sha256=binding, expected_query_ids=ids, unresolved_query_ids=list(ids),
            case_worksheet=dispatch.worksheet(binding, CASE_DECISIONS),
            queries=[dict(query_id=q['query_id'], business_goal=deepcopy(q['business_goal']),
                reader_plan=dispatch.prepare_reader(s, q['query_id'], query_review=reviews.get(q['query_id'])))
                for q in queries])
        return out
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_CASE_OR_QUERY_REVIEW_SET')


def _review_json(records):
    if type(records) is not dict:
        raise ValueError('NATIVE_REVIEW_MAPPING_REQUIRED')
    return {method: {key: value.model_dump(mode='json') if isinstance(value, BaseModel) else value
                     for key,value in pair.items()} for method,pair in records.items()}


def execute_case(intake, submissions, *, case_review=None, research_protocol_selected=False):
    """Recompute each supplied query; return gaps as gaps, never fill/merge them."""
    out = prepare_case(intake)
    if not out.get('case_worksheet'):
        return out
    try:
        s = intake_api._checked(intake)
        if s.fact_format != 'short_refs':
            raise dispatch.DispatchError('ADAPTER_NOT_CONNECTED', 'WHOLE_CASE_REQUIRES_QUERY_SCOPE_READING')
        if type(submissions) is not dict or not set(submissions) <= set(out['expected_query_ids']):
            raise dispatch.DispatchError('CHECK_BLOCKED', 'UNKNOWN_OR_STALE_SUBMISSION_QUERY')
        for value in submissions.values():
            if type(value) is not dict or set(value) - SUBMISSION_FIELDS:
                raise dispatch.DispatchError('CHECK_BLOCKED', 'ONLY_QUERY_INPUTS_NOT_SAVED_RESULTS_ALLOWED')
        if research_protocol_selected is not True:
            raise dispatch.DispatchError('REVIEW_REQUIRED', 'EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review = dispatch.checked_review(case_review, out['case_worksheet'])
        out['case_review'] = review.model_dump(mode='json')
        out['submitted_query_ids'] = [q for q in out['expected_query_ids'] if q in submissions]
        for query in out['queries']:
            qid = query['query_id']
            row = submissions.get(qid)
            result = dict(dispatch.empty_result(), state='READING_REQUIRED',
                          reason_code='QUERY_SUBMISSION_MISSING', query_id=qid)
            if row is not None:
                try:
                    row = deepcopy(row)
                    entry = dispatch.prepare_reader(s, qid, query_review=row.get('query_review'),reading_revision=row.get('reading_revision'))
                    result = entry
                    if entry['state'] == 'READY_TO_READ':
                        if entry['query_review']['authority'] != review.authority:
                            raise dispatch.DispatchError('CHECK_BLOCKED', 'CASE_AND_QUERY_REVIEW_AUTHORITY_MISMATCH')
                        if 'candidate' not in row or 'request_sha256' not in row:
                            result = dict(dispatch.empty_result(), state='READING_REQUIRED',
                                          reason_code='QUERY_CANDIDATE_REQUIRED')
                        else:
                            # Source-role review is an input, not a saved result or
                            # scientific approval. The individual dispatcher checks
                            # its scope and binding on both inspection and execution.
                            options = dict(query_review=row['query_review'], candidate=row['candidate'],
                                           request_sha256=row['request_sha256'], note_review=row.get('note_review'),
                                           reading_revision=row.get('reading_revision'), change_review=row.get('change_review'),
                                           information_evidence_review=row.get('information_evidence_review'),source_review=row.get('source_review'))
                            plan = dispatch.inspect_methods(s, qid, **options)
                            result = plan
                            if plan['state'] == 'REVIEW_REQUIRED' and 'plan_worksheet' in plan:
                                from .business_dispatch import native_reviews_from_json
                                records = row.get('native_reviews')
                                if records is not None:
                                    records = native_reviews_from_json(plan, _review_json(records))
                                result = dispatch.execute(s, qid, **options, plan_review=row.get('plan_review'),
                                    native_reviews=records, research_protocol_selected=True)
                except dispatch.DispatchError as exc:
                    result = dict(dispatch.empty_result(), state=exc.state, reason_code=exc.reason)
                except (ValueError, TypeError, KeyError, AttributeError):
                    result = dict(dispatch.empty_result(), reason_code='INVALID_QUERY_SUBMISSION')
            out['results'].append(dict(query_id=qid, business_goal=query['business_goal'], result=result))
            out['backend_called'] |= result.get('backend_called') is True
            if (result['state'] in ('POINT','PARTIAL') and result.get('independent_replay') is True
                    and result.get('answers')):
                out['identified_query_ids'].append(qid)
                key='point_identified_query_ids' if result['state']=='POINT' else 'partially_identified_query_ids'
                out[key].append(qid)
        if intake_api._sha(s.model_dump(mode='json')) != out['case_binding_sha256']:
            raise dispatch.DispatchError('CHECK_BLOCKED', 'CASE_CHANGED_DURING_EXECUTION')
        out['unresolved_query_ids'] = [q for q in out['expected_query_ids'] if q not in out['identified_query_ids']]
        out['all_queries_identified'] = bool(out['expected_query_ids']) and not out['unresolved_query_ids']
        out['all_queries_point_identified'] = out['all_queries_identified'] and not out['partially_identified_query_ids']
        out['state'] = 'ALL_QUERIES_IDENTIFIED' if out['all_queries_identified'] else 'CASE_INCOMPLETE'
        return out
    except dispatch.DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason, results=[], identified_query_ids=[],
                    point_identified_query_ids=[],partially_identified_query_ids=[],
                    unresolved_query_ids=out['expected_query_ids'], all_queries_identified=False,all_queries_point_identified=False)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_WHOLE_CASE_EXECUTION', results=[],
                    identified_query_ids=[],point_identified_query_ids=[],partially_identified_query_ids=[],
                    unresolved_query_ids=out['expected_query_ids'], all_queries_identified=False,all_queries_point_identified=False)
