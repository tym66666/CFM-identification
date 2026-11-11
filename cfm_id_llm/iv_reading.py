"""Source-bound structured reading adapter for the binary-IV research route.

This module does not infer scientific assumptions from prose and does not
create approvals. It validates an explicit candidate, preserves source IDs,
and prepares separate reading/science review worksheets for human review.
"""
from copy import deepcopy
from cfm_id_bridge.scientific_binding import sha
from cfm_id.iv_route_contract import (IVProblem, IVReview, IVReadingReview,
    IVScienceReview, READING_DECISIONS, SCIENCE_DECISIONS, digest, science_decisions)
from cfm_id.iv_research import prepare, submit


def inspect_candidate(candidate):
    out=dict(state='CHECK_BLOCKED',reason_code=None,reading_approval=False,
        science_approval=False,backend_called=False,certificate_replayed=False,
        production_admission=False,estimation_handoff_allowed=False,
        reading_worksheet=None,science_worksheet=None,problem=None)
    try:
        if type(candidate) is not dict or set(candidate)!={'problem','source_catalog'}:
            raise ValueError('EXACT_IV_CANDIDATE_FIELDS_REQUIRED')
        p=IVProblem.model_validate(candidate['problem'])
        catalog=candidate['source_catalog']
        if type(catalog) is not dict or not set(p.source_ids)<=set(catalog):
            raise ValueError('SOURCE_CATALOG_MUST_COVER_ALL_DECLARED_SOURCE_IDS')
        for sid in p.source_ids:
            row=catalog[sid]
            if type(row) is not dict or set(row)!={'uri','sha256','locator'}:
                raise ValueError('SOURCE_REFERENCE_MUST_INCLUDE_URI_HASH_AND_LOCATOR')
            if type(row['uri']) is not str or not row['uri'].strip() or type(row['locator']) is not str or not row['locator'].strip():
                raise ValueError('SOURCE_REFERENCE_URI_AND_LOCATOR_REQUIRED')
            if type(row['sha256']) is not str or len(row['sha256'])!=64:
                raise ValueError('SOURCE_REFERENCE_HASH_REQUIRED')
        if sha(catalog)!=p.source_sha256:
            raise ValueError('SOURCE_CATALOG_HASH_DOES_NOT_MATCH_PROBLEM')
        psha=digest(p); base=prepare(p)
        out.update(state=base['state'],reason_code=base.get('reason_code'),problem=p.model_dump(),
            problem_sha256=psha,source_catalog=deepcopy(catalog),candidate_sha256=sha(candidate))
        if base['state']=='REVIEW_REQUIRED':
            out['reading_worksheet']=dict(problem_sha256=psha,is_approval=False,
                decisions={k:'PENDING' for k in READING_DECISIONS})
            decisions=science_decisions(p)
            out['science_worksheet']=dict(problem_sha256=psha,is_approval=False,
                decisions={k:'PENDING' for k in decisions})
        return out
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        out['reason_code']=str(exc) if str(exc) else 'INVALID_IV_READING_CANDIDATE'
        return out


def submit_reviewed(candidate, *, reading_review=None, science_review=None, research_protocol_selected=False):
    inspected=inspect_candidate(candidate)
    if inspected['state']!='REVIEW_REQUIRED' or research_protocol_selected is not True:return inspected
    try:
        p=IVProblem.model_validate(candidate['problem']); psha=digest(p)
        rr=IVReadingReview.model_validate(reading_review)
        sr=IVScienceReview.model_validate(science_review)
        review=IVReview(version=p.version,problem_sha256=psha,reading_review=rr,science_review=sr)
        result=submit(p,review=review,research_protocol_selected=True)
        return {**inspected,**result,'source_catalog':deepcopy(candidate['source_catalog']),
            'reading_review_sha256':sha(rr),'science_review_sha256':sha(sr),
            'reading_approval_is_not_scientific_proof':True}
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        return {**inspected,'state':'CHECK_BLOCKED','reason_code':'INVALID_OR_STALE_IV_REVIEW'}
