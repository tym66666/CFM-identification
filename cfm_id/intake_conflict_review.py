"""Source-bound reviewer-confirmed conflict stop; no target or scientific approval."""
from copy import deepcopy
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from . import business_field_review,business_intake
from .intake_reading_revision import sources


class ConflictSource(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    source_id: str=Field(min_length=1)
    quote: str=Field(min_length=1,max_length=3000)


class ConflictReview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    version: Literal['intake-conflict-review-1']='intake-conflict-review-1'
    query_id: str=Field(min_length=1)
    field: str=Field(min_length=1)
    authority: Literal['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW']
    reviewer: str=Field(min_length=3,max_length=200)
    reason: str=Field(min_length=12,max_length=2000)
    sources: list[ConflictSource]=Field(min_length=2,max_length=8)


def review_conflict(value,query_id,*,field_review,conflict_review):
    """Stop only after an explicit field rejection and located reviewer assessment.

    The reviewer establishes the conflict; this function validates provenance,
    not whether language entails a contradiction. No candidate is repaired.
    """
    s=business_intake._checked(value)
    r=ConflictReview.model_validate(conflict_review)
    if r.query_id!=query_id or r.field!=f'queries.{query_id}.'+r.field.removeprefix(f'queries.{query_id}.'):
        raise ValueError('CONFLICT_QUERY_OR_FIELD_MISMATCH')
    raw=field_review.model_dump(mode='json') if hasattr(field_review,'model_dump') else field_review
    if raw.get('authority')!=r.authority:raise ValueError('CONFLICT_AUTHORITY_MISMATCH')
    decision=raw.get('decisions',{}).get(r.field,{})
    if not any(decision.get(k)=='REJECTED' for k in ('field_role','value_state','source_coverage')):
        raise ValueError('EXPLICIT_FIELD_REJECTION_REQUIRED')
    checked=business_field_review.submit(s,query_id,raw,authority=r.authority)
    if checked.get('state')!='CHECK_BLOCKED' or checked.get('reason_code')!='DISPATCH_REVIEW_REJECTED':
        raise ValueError('CURRENT_PROJECT_FIELD_REJECTION_REQUIRED')
    catalog=sources(s)
    ids=[x.source_id for x in r.sources]
    if len(ids)!=len(set(ids)) or any(x.source_id not in catalog or x.quote not in catalog[x.source_id]['text'] for x in r.sources):
        raise ValueError('CONFLICT_SOURCES_INVALID_OR_STALE')
    # Distinct located statements may conflict within one document. Requiring
    # separate documents incorrectly blocks that case; repeated quotes alone
    # cannot serve as the two statements of the review.
    if len({x.quote.strip() for x in r.sources})<2:
        raise ValueError('TWO_DISTINCT_CONFLICT_STATEMENTS_REQUIRED')
    return dict(state='CLARIFICATION_REQUIRED',reason_code='REVIEWED_CONFLICT_IN_BUSINESS_MATERIALS',
        clarification_questions=['材料对目标政策或相关业务条件的表述存在冲突。请确认本次使用的安排或条件，并说明哪项表述不再适用？'],
        query_id=query_id,backend_called=False,independent_replay=False,mathematical_claim=None,certificate=None,
        scientific_approval=False,candidate_modified=False,api_calls=0,review_origin='EXPLICIT_SOURCE_REVIEW',
        source_review=deepcopy(r.model_dump(mode='json')),
        field_review_sha256=business_intake._sha(raw),intake_sha256=business_intake._sha(s.model_dump(mode='json')),
        evidence_note='Conflicting meaning is asserted by the reviewer; the program validates source locations, not entailment.')
