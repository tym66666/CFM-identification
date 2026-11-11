"""IV adapter for existing intake, source reviews, plan reviews and replay."""
from copy import deepcopy
from .business_dispatch import empty_result, worksheet, checked_review, DispatchError, PLAN_DECISIONS, sha
from .iv_route_contract import IVProblem, IVReview, VERSION, ROUTE, validate, digest, science_decisions
from . import iv_research
from .iv_research_adapter import BinaryIVRoute
from cfm_id_llm.iv_fact_reading import FAMILY

METHOD = ROUTE


def inspect_methods(entry, candidate):
    out = dict(empty_result(), fact_family=FAMILY, methods=[], query_id=entry['query_id'],
        remaining_query_ids=entry['remaining_query_ids'], query_review=entry['query_review'],
        request_sha256=entry['request_sha256'], reading_candidate=deepcopy(candidate),
        selected_query=deepcopy(entry['selected_query']))
    try:
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        facts = contract_for_entry(entry).parse_candidate(entry, candidate)['facts']
        out['facts'] = facts
        # Source and whole-reading completeness review uses the common workflow.
        if entry.get('source_review_receipt') is None:
            from .fact_source_review import prepare
            return dict(out, state='REVIEW_REQUIRED', reason_code='IV_SOURCE_REVIEW_REQUIRED',
                source_review_worksheet=prepare(entry, candidate))
        out['source_review_receipt'] = deepcopy(entry['source_review_receipt'])
        target = facts['target']
        if target['kind'] != entry['selected_query']['target']['kind']:
            return dict(out, state='READING_RECHECK_REQUIRED', reason_code='IV_TARGET_CHANGED_BETWEEN_STAGES')
        if target['direction'] != 'Y1_MINUS_Y0':
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='IV_TARGET_DIRECTION_NOT_SUPPORTED')
        if facts['unresolved']:
            return dict(out, state='NEEDS_INPUT', reason_code='IV_UNRESOLVED_MATERIAL',
                clarification_questions=[s['text'] for s in facts['unresolved']])
        if facts['additional_restrictions']:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='IV_EXTRA_RESTRICTIONS_NOT_COMPILED')
        if facts['information']['kind'] != 'POPULATION_CONDITIONAL_LAW':
            return dict(out, state='NEEDS_INPUT', reason_code='IV_POPULATION_LAW_REQUIRED')
        if facts['monotonicity'] == 'UNKNOWN':
            return dict(out, state='NEEDS_INPUT', reason_code='IV_MODEL_CHOICE_UNRESOLVED')
        mono = facts['monotonicity'] == 'IMPOSED'
        if target['kind'] == 'LATE' and not mono:
            return dict(out, state='UNSUPPORTED', reason_code='LATE_REQUIRES_MONOTONICITY')
        keys = ('instrument', 'treatment', 'outcome')
        required = [k for k in facts['assumptions'] if k != 'monotonicity_direction' or mono]
        records = [facts[k] for k in keys] + [facts['assumptions'][k] for k in required]
        if any(r['state'] == 'REJECTED' for r in records):
            return dict(out, state='UNSUPPORTED', reason_code='IV_REQUIRED_CONDITION_REJECTED')
        if any(r['state'] != 'STATED' for r in records):
            return dict(out, state='NEEDS_INPUT', reason_code='IV_REQUIRED_CONDITION_MISSING')
        if (not target['source_ids'] or not facts['information']['source_ids']
                or not facts['monotonicity_source_ids']):
            return dict(out, state='READING_RECHECK_REQUIRED', reason_code='IV_REQUIRED_SOURCE_MISSING')
        if facts['instrument']['text'] == facts['treatment']['text']:
            return dict(out, state='READING_RECHECK_REQUIRED', reason_code='IV_INSTRUMENT_TREATMENT_CONFLATED')
        refs = contract_for_entry(entry).reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])
        p = IVProblem(version=VERSION, target=target['kind'], monotonicity=mono,
            cells=[{k: c[k] for k in ('z','d','y','probability')} for c in facts['information']['cells']],
            **{k: facts[k]['text'] for k in keys}, population=target['population'], context=target['context'],
            source_ids=[refs['aliases'][sid]['source_id'] for sid in facts['information']['source_ids']],
            # Binds the original documents, exact first/revised answer and source review.
            source_sha256=sha(dict(entry=entry, candidate=candidate)), assumptions=required)
        validate(p)
        native = iv_research.prepare(p)
        row = dict(method=METHOD, proposed_problem=p.model_dump(mode='json'),
            native_worksheet=native['worksheet'], state='REVIEW_REQUIRED')
        out['methods'] = [row]
        binding = sha(dict(entry=entry, candidate=candidate, methods=out['methods']))
        return dict(out, state='REVIEW_REQUIRED', plan_sha256=binding,
            plan_worksheet=worksheet(binding, PLAN_DECISIONS + ('iv_target_population_coding_and_time_match',)))
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_SOURCE_BOUND_IV_FACTS')


def native_reviews_from_json(plan, records):
    if type(records) is not dict or set(records) != {METHOD}:
        raise ValueError('EXACT_IV_NATIVE_REVIEW_REQUIRED')
    return {METHOD: IVReview.model_validate(records[METHOD])}


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    out = dict(empty_result(), query_id=plan['query_id'], remaining_query_ids=plan['remaining_query_ids'])
    try:
        if research_protocol_selected is not True:
            raise DispatchError('REVIEW_REQUIRED', 'EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        approval = checked_review(plan_review, plan['plan_worksheet'])
        authority = plan['query_review']['authority']
        if approval.authority != authority:
            raise DispatchError('CHECK_BLOCKED', 'IV_PLAN_AUTHORITY_MISMATCH')
        if native_reviews is None:
            raise DispatchError('REVIEW_REQUIRED', 'IV_NATIVE_REVIEWS_REQUIRED')
        if type(native_reviews) is not dict or set(native_reviews) != {METHOD}:
            raise DispatchError('CHECK_BLOCKED', 'EXACT_IV_NATIVE_REVIEW_REQUIRED')
        review = IVReview.model_validate(native_reviews[METHOD])
        if any(r.authority != authority for r in (review.reading_review, review.science_review)):
            raise DispatchError('CHECK_BLOCKED', 'IV_NATIVE_AUTHORITY_MISMATCH')
        p = IVProblem.model_validate(plan['methods'][0]['proposed_problem'])
        result = iv_research.submit(p, review=review, research_protocol_selected=True)
        out.update(state=result['state'], reason_code=result.get('reason_code'),
            backend_called=result['backend_called'], native_result=result)
        if result['state'] not in ('POINT','PARTIAL','INCOMPATIBLE'):
            return out
        cert = deepcopy(result['certificate'])
        adapter = BinaryIVRoute()
        if not adapter.replay(p, cert):
            raise DispatchError('CHECK_BLOCKED', 'IV_PUBLICATION_REPLAY_FAILED')
        claim = adapter.claim(cert)
        if not adapter.verify_claim(cert, claim):
            raise DispatchError('CHECK_BLOCKED', 'IV_PUBLICATION_CLAIM_FAILED')
        answer = dict(method=METHOD, mathematical_claim=claim, certificate=cert, independent_replay=True)
        return dict(out, mathematical_claim=claim, certificate=cert, independent_replay=True, answers=[answer])
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_IV_REVIEW_OR_EVIDENCE')
