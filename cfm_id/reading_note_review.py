"""Independent source-bound adjudication of reader notes, never fact repair.

Notes remain in the original candidate and decoded facts. Release permits only
the next validation step; typed gaps, scientific review and math checks remain.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .business_dispatch import sha,DispatchError
from .source_locations import build_catalog

VERSION='reading-note-review-1'
RELEASED={'NONBLOCKING_COMMENT','DEFER_TO_MATHEMATICS'}


class NoteDecision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    disposition: Literal['PENDING','MATERIAL_GAP','READING_ERROR',
                         'NONBLOCKING_COMMENT','DEFER_TO_MATHEMATICS']
    reason: str=Field(min_length=12)
    source_ids: list[str]


class ReadingNoteReview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    version: Literal['reading-note-review-1']=VERSION
    binding_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    reviewer: str=Field(min_length=3)
    evidence: str=Field(min_length=12)
    decisions: dict[str,NoteDecision]


def inspect_notes(entry,candidate,notes,documents,review=None):
    """Pure review of notes. Does not edit candidate, infer facts or call math.

`notes` contains decoded source locators; all other input is already validated
by the caller's reading contract. `documents` must be the original material.
"""
    if not notes:
        if review is not None:
            raise DispatchError('CHECK_BLOCKED','NOTE_REVIEW_WITHOUT_CURRENT_NOTES')
        return dict(state='NO_NOTES',worksheet=None,review=None,receipt=None,
                    clarification_questions=[],reading_recheck_notes=[])
    catalog=build_catalog(documents)
    binding=sha(dict(version=VERSION,query_id=entry['query_id'],request_sha256=entry['request_sha256'],
        fact_binding_sha256=entry['fact_binding_sha256'],query_review=entry['query_review'],
        documents=documents,candidate=candidate,notes=notes))
    indexed={f'n{i:04d}':deepcopy(note) for i,note in enumerate(notes,1)}
    sheet=dict(version=VERSION,binding_sha256=binding,expected_authority=entry['query_review']['authority'],
        notes=indexed,source_catalog=deepcopy(catalog),is_approval=False,
        decisions={key:dict(disposition='PENDING',reason='',source_ids=[]) for key in indexed},
        scope='Adjudicate notes only; no fact replacement, scientific admission or mathematical certification.')
    out=dict(state='REVIEW_REQUIRED',reason_code='INDEPENDENT_READING_NOTE_REVIEW_REQUIRED',
        worksheet=sheet,review=None,receipt=None,clarification_questions=[],reading_recheck_notes=[])
    if review is None:return out
    raw=review.model_dump(mode='json') if type(review) is ReadingNoteReview else review
    try:
        r=ReadingNoteReview.model_validate(raw)
        if (not r.reviewer.strip() or not r.evidence.strip() or r.binding_sha256!=binding or
            r.authority!=entry['query_review']['authority'] or set(r.decisions)!=set(indexed)):
            raise ValueError('Wrong review identity, scope or authority')
        for decision in r.decisions.values():
            if not decision.reason.strip() or len(set(decision.source_ids))!=len(decision.source_ids):
                raise ValueError('Nonblank reason and unique source references required')
            if (decision.disposition!='PENDING' and not decision.source_ids) or any(s not in catalog for s in decision.source_ids):
                raise ValueError('Original source references required')
    except (ValueError,TypeError,KeyError,AttributeError):
        raise DispatchError('CHECK_BLOCKED','INVALID_OR_STALE_READING_NOTE_REVIEW') from None
    record=r.model_dump(mode='json')
    out.update(review=record,receipt=dict(version=VERSION,binding_sha256=binding,review_sha256=sha(record),
        reviewer=r.reviewer,authority=r.authority,decisions=deepcopy(record['decisions']),
        original_notes=deepcopy(indexed),candidate_modified=False,scientific_approval=False,
        mathematical_verification='NOT_PERFORMED'))
    states={d.disposition for d in r.decisions.values()}
    out['clarification_questions']=[indexed[k]['text'] for k,d in r.decisions.items() if d.disposition=='MATERIAL_GAP']
    out['reading_recheck_notes']=[indexed[k]['text'] for k,d in r.decisions.items() if d.disposition=='READING_ERROR']
    if 'READING_ERROR' in states:
        return dict(out,state='READING_RECHECK_REQUIRED',reason_code='REVIEWED_READING_ERROR_REQUIRES_NEW_CANDIDATE')
    if 'MATERIAL_GAP' in states:
        return dict(out,state='NEEDS_INPUT',reason_code='REVIEWED_MATERIAL_GAP')
    if 'PENDING' in states:
        return dict(out,state='REVIEW_REQUIRED',reason_code='READING_NOTE_REVIEW_PENDING')
    if not states<=RELEASED:
        raise DispatchError('CHECK_BLOCKED','UNKNOWN_NOTE_REVIEW_DISPOSITION')
    return dict(out,state='NOTES_RELEASED_FOR_CHECKS',reason_code=None)
