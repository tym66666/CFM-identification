"""Resumable identification research sessions over existing business boundaries.

Saved files contain materials, candidate and private review declarations, never
executable Core contexts or authoritative results. Reading, reviewing and mathematically
verifying remain distinct. Content hashes detect stale bindings, not identities.
"""
from copy import deepcopy
from pathlib import Path
from typing import Literal
from uuid import uuid4
import json
from pydantic import BaseModel, ConfigDict, Field
from cfm_id_bridge.scientific_binding import sha
from . import session_routes as routes
from . import review_items as items

DECISIONS=('business_target_and_sources','population_information','scientific_assumptions')


class SessionError(ValueError):
    pass


class StrictRecord(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)


class SessionReview(StrictRecord):
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    native_submission_sha256: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    item_review_sha256: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    decisions: dict[str,Literal['ACCEPTED','PENDING','REJECTED']]


class ResearchSession(StrictRecord):
    version: Literal['identification-research-session-1']='identification-research-session-1'
    session_id: str = Field(pattern=r'^[0-9a-f-]{36}$')
    revision: int = Field(ge=0)
    lane: str
    bundle: dict
    request_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    candidate: dict | None = None
    review: SessionReview | None = None
    item_review: items.ItemReview | None = None
    history: list[dict] = Field(default_factory=list)


def _checked(session):
    if type(session) is not ResearchSession: raise SessionError('TYPED_SESSION_REQUIRED')
    s=ResearchSession.model_validate(deepcopy(session.model_dump()))
    routes.public_bundle(s.lane,s.bundle)
    if sha(routes.request(s.lane,s.bundle))!=s.request_sha256:
        raise SessionError('STALE_MATERIALS_OR_READING_PROTOCOL')
    if s.item_review is not None:
        items.checked(s.item_review,lane=s.lane,bundle=s.bundle,candidate=s.candidate,binding=_binding(s))
    if s.review is not None:
        r=s.review
        if r.binding_sha256!=_binding(s):raise SessionError('STALE_SESSION_REVIEW')
        if s.candidate is None or set(r.decisions)!=set(DECISIONS) or not r.reviewer.strip() or not r.evidence.strip():
            raise SessionError('EXACT_NONBLANK_REVIEW_REQUIRED')
        if all(v=='ACCEPTED' for v in r.decisions.values()) and not r.native_submission_sha256:
            raise SessionError('BOUND_NATIVE_SUBMISSION_REQUIRED')
        _check_item_binding(s,r)
    return s


def _check_item_binding(s,r):
    if s.item_review is None:
        if r.item_review_sha256 is not None:raise SessionError('ITEM_REVIEW_REQUIRED')
        return
    if (r.item_review_sha256!=sha(s.item_review) or
            r.native_submission_sha256!=sha(s.item_review.native_snapshot)):
        raise SessionError('CURRENT_ITEM_REVIEW_BINDING_REQUIRED')
    if all(v=='ACCEPTED' for v in r.decisions.values()) and any(
            v!='ACCEPTED' for v in items.decisions(s.item_review).values()):
        raise SessionError('ALL_REVIEW_ITEMS_MUST_BE_ACCEPTED')


def _binding(s):
    return sha(dict(version=s.version,session_id=s.session_id,revision=s.revision,lane=s.lane,
        bundle=s.bundle,candidate=s.candidate,request_sha256=s.request_sha256))


def binding(session):
    return _binding(_checked(session))


def start(lane, bundle):
    b=routes.public_bundle(lane,bundle)
    return ResearchSession(session_id=str(uuid4()),revision=0,lane=lane,bundle=b,
        request_sha256=sha(routes.request(lane,b)))


def prepare_request(session):
    s=_checked(session)
    return deepcopy(routes.request(s.lane,s.bundle))


def _change(s, *, action, note, bundle=None, candidate=None):
    if type(note) is not str or not note.strip(): raise SessionError('CHANGE_REASON_REQUIRED')
    b=deepcopy(s.bundle if bundle is None else routes.public_bundle(s.lane,bundle))
    return ResearchSession(session_id=s.session_id,revision=s.revision+1,lane=s.lane,bundle=b,
        request_sha256=sha(routes.request(s.lane,b)),candidate=deepcopy(candidate),review=None,
        history=[*deepcopy(s.history),dict(action=action,note=note,parent_binding_sha256=_binding(s),
            parent_revision=s.revision,prior_review_sha256=sha(s.review) if s.review else None,
            prior_item_review_sha256=sha(s.item_review) if s.item_review else None)])


def receive_candidate(session, candidate):
    s=_checked(session)
    if type(candidate) is not dict: raise SessionError('JSON_OBJECT_CANDIDATE_REQUIRED')
    # Schema-invalid objects are preserved for diagnosis, never repaired.
    json.dumps(candidate,allow_nan=False)
    return _change(s,action='CANDIDATE_REPLACED',note='Actual reading received; prior review invalidated.',candidate=candidate)


def revise_materials(session, bundle, *, reason):
    return _change(_checked(session),action='MATERIALS_REVISED',note=reason,bundle=bundle)


def inspect(session):
    s=_checked(session)
    out=dict(session_id=s.session_id,revision=s.revision,lane=s.lane,binding_sha256=_binding(s),
        state='READING_REQUIRED',reason_code=None,mathematical_claim=None,certificate=None,
        independent_replay=False,backend_called=False,production_admission=False,
        estimation_handoff_allowed=False,clarification_questions=[],native_inspection=None)
    if s.candidate is None:return out
    try:
        native=routes.inspect(s.lane,s.bundle,deepcopy(s.candidate))
        # A malformed native reading is an input-contract block, not approval
        # readiness. Preserve the native label in the diagnostic record.
        state='CHECK_BLOCKED' if native['state']=='READING_REVIEW_REQUIRED' else native['state']
        out.update(state=state,reason_code=native.get('reason_code'),native_inspection=native,
                   clarification_questions=routes.questions(s.lane,native))
        if s.review is not None:
            if 'REJECTED' in s.review.decisions.values():out.update(state='CHECK_BLOCKED',reason_code='SESSION_REVIEW_REJECTED')
            elif 'PENDING' in s.review.decisions.values() and out['state']=='REVIEW_REQUIRED':out['reason_code']='SESSION_REVIEW_PENDING'
        if s.item_review is not None:
            current=items.decisions(s.item_review)
            if 'REJECTED' in current.values():out.update(state='CHECK_BLOCKED',reason_code='ITEM_REVIEW_REJECTED')
            elif any(v!='ACCEPTED' for v in current.values()) and out['state']=='REVIEW_REQUIRED':
                out['reason_code']='ITEM_REVIEW_INCOMPLETE_OR_WITHDRAWN'
        return out
    except (ValueError,TypeError,KeyError,AttributeError):
        out.update(state='CHECK_BLOCKED',reason_code='SESSION_INSPECTION_REJECTED')
        return out


def review_worksheet(session, *, native_submission=None):
    s=_checked(session); view=inspect(s)
    material=routes.submission_snapshot(s.lane,native_submission) if native_submission is not None else None
    return dict(binding_sha256=_binding(s),
        native_submission_sha256=sha(material) if material is not None else None,
        native_review_materials=material,
        decisions={key:'PENDING' for key in DECISIONS},is_approval=False,
        inspection_state=view['state'],native_inspection=view['native_inspection'],
        instruction='Separate reviewer/evidence and exact native review objects are required; this worksheet is not approval.')


def record_review(session, review):
    s=_checked(session)
    r=SessionReview.model_validate(deepcopy(review.model_dump() if type(review) is SessionReview else review))
    if r.binding_sha256!=_binding(s):raise SessionError('STALE_SESSION_REVIEW')
    if set(r.decisions)!=set(DECISIONS) or not r.reviewer.strip() or not r.evidence.strip():
        raise SessionError('EXACT_NONBLANK_REVIEW_REQUIRED')
    if s.candidate is None:raise SessionError('READING_REQUIRED_BEFORE_REVIEW')
    _check_item_binding(s,r)
    if all(v=='ACCEPTED' for v in r.decisions.values()):
        if not r.native_submission_sha256:raise SessionError('BOUND_NATIVE_SUBMISSION_REQUIRED')
        # Rejected earlier decisions may be explicitly revised; do not recycle their state.
        raw=s.model_copy(update={'review':None})
        if inspect(raw)['state']!='REVIEW_REQUIRED':raise SessionError('CANDIDATE_NOT_READY_FOR_REVIEW')
    return ResearchSession.model_validate(dict(s.model_dump(),review=r.model_dump(),
        history=[*s.history,dict(action='REVIEW_RECORDED',binding_sha256=_binding(s),review_sha256=sha(r))]))


def begin_item_review(session, *, native_submission):
    """Start a new pending checklist; native approvals are only retained as evidence."""
    s=_checked(session)
    snapshot=routes.submission_snapshot(s.lane,native_submission)
    book=items.open_book(lane=s.lane,bundle=s.bundle,candidate=s.candidate,
                         binding=_binding(s),native_snapshot=snapshot)
    return ResearchSession.model_validate(dict(s.model_dump(),review=None,item_review=book.model_dump(),
        history=[*s.history,dict(action='ITEM_REVIEW_OPENED',binding_sha256=_binding(s),
            prior_review_sha256=sha(s.review) if s.review else None,
            prior_item_review_sha256=sha(s.item_review) if s.item_review else None,
            item_review_sha256=sha(book))]))


def item_review_worksheet(session):
    s=_checked(session)
    if s.item_review is None:raise SessionError('ITEM_REVIEW_REQUIRED')
    return items.worksheet(s.item_review)


def decide_item(session, change):
    s=_checked(session)
    if s.item_review is None:raise SessionError('ITEM_REVIEW_REQUIRED')
    book=items.decide(s.item_review,change)
    return ResearchSession.model_validate(dict(s.model_dump(),review=None,item_review=book.model_dump(),
        history=[*s.history,dict(action='ITEM_REVIEW_DECIDED',binding_sha256=_binding(s),
            prior_review_sha256=sha(s.review) if s.review else None,
            prior_item_review_sha256=sha(s.item_review),item_review_sha256=sha(book))]))


def finalize_item_review(session, *, expected_review_sha256, reviewer, evidence):
    """Bind completed outer decisions only; native review gates still run on execute."""
    s=_checked(session)
    if s.item_review is None:raise SessionError('ITEM_REVIEW_REQUIRED')
    if expected_review_sha256!=sha(s.item_review):raise SessionError('STALE_ITEM_REVIEW_FINALIZATION')
    if any(v!='ACCEPTED' for v in items.decisions(s.item_review).values()):
        raise SessionError('ALL_REVIEW_ITEMS_MUST_BE_ACCEPTED')
    return record_review(s,SessionReview(binding_sha256=_binding(s),
        native_submission_sha256=sha(s.item_review.native_snapshot),item_review_sha256=sha(s.item_review),
        reviewer=reviewer,evidence=evidence,decisions={k:'ACCEPTED' for k in DECISIONS}))


def clarification_plan(session):
    s=_checked(session); view=inspect(s)
    rows=[]
    for row in view['clarification_questions']:
        rows.append(dict(**row,clarification_id='clarify_'+sha(dict(binding=_binding(s),**row))))
    return dict(binding_sha256=_binding(s),basis='CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE',
        questions=rows,scientific_approval=False)


def append_reply(session, plan, clarification_id, reply):
    s=_checked(session)
    current=clarification_plan(s)
    if plan!=current:raise SessionError('STALE_OR_CHANGED_CLARIFICATION_PLAN')
    row=next((r for r in current['questions'] if r['clarification_id']==clarification_id),None)
    if row is None or type(reply) is not str or not reply.strip():raise SessionError('CURRENT_QUESTION_AND_TEXT_REPLY_REQUIRED')
    b=deepcopy(s.bundle)
    text='【补充材料，尚未经业务与科学审核】\n追问：'+row['text']+'\n答复：'+reply
    doc='session_reply_'+sha(dict(binding=_binding(s),id=clarification_id,reply=reply))[:24]+'.txt'
    if doc in b['documents']:raise SessionError('DUPLICATE_REPLY_DOCUMENT')
    if s.lane == routes.NETWORK and row['query_id'] is not None:
        from .session_materials import append_target_reply
        b = append_target_reply(b, row['query_id'], doc, text)
        return _change(s,action='CLARIFICATION_REPLIED',note=clarification_id,bundle=b)
    b['documents'][doc]=text
    if row['query_id'] is not None:
        qid=row['query_id']
        b['question_slots'][qid]+='\n'+text
        b['documents'][doc]=b['question_slots'][qid]
    return _change(s,action='CLARIFICATION_REPLIED',note=clarification_id,bundle=b)


def execute(session, *, native_submission=None, research_protocol_selected=False):
    """Fresh execution only. Never deserialize or trust a saved mathematical result."""
    s=_checked(session); out=inspect(s)
    if out['state']!='REVIEW_REQUIRED':return out
    if research_protocol_selected is not True:
        return dict(out,reason_code='EXPLICIT_RESEARCH_PROTOCOL_REQUIRED')
    if s.review is None or any(v!='ACCEPTED' for v in s.review.decisions.values()):
        return dict(out,reason_code='SEPARATE_COMPLETED_SESSION_REVIEW_REQUIRED')
    if native_submission is None:
        return dict(out,reason_code='EXPLICIT_NATIVE_REVIEWS_REQUIRED_AFTER_RESTORE')
    try:
        if routes.submission_digest(s.lane,native_submission)!=s.review.native_submission_sha256:
            raise SessionError('NATIVE_SUBMISSION_CHANGED_AFTER_REVIEW')
        native=routes.submit(s.lane,deepcopy(s.bundle),deepcopy(s.candidate),native_submission)
        out['backend_called']=any(native.get(k) is True for k in ('core_called','backend_called','bounded_backend_called')) or any(
            v.get('base_core_called') or v.get('bounded_backend_called') for v in native.get('stages',[]))
        if routes.submission_digest(s.lane,native_submission)!=s.review.native_submission_sha256:
            raise SessionError('NATIVE_SUBMISSION_MUTATED_DURING_EXECUTION')
        claim,certificate=routes.published_evidence(s.lane,native,native_submission=native_submission)
        if routes.submission_digest(s.lane,native_submission)!=s.review.native_submission_sha256:
            raise SessionError('NATIVE_SUBMISSION_MUTATED_DURING_PUBLICATION')
        state='POINT' if native['state']=='CORE_POINT' else native['state']
        out.update(state=state,reason_code=native.get('reason_code') or native.get('answer',{}).get('reason_code'),
            native_result=native,mathematical_claim=claim,certificate=certificate,
            independent_replay=claim is not None)
        return out
    except (ValueError,TypeError,KeyError,AttributeError):
        # No partial proof leaks through the public result on a failed boundary.
        return dict(out,state='CHECK_BLOCKED',reason_code='SESSION_SUBMISSION_OR_PROOF_REJECTED',
            mathematical_claim=None,certificate=None,independent_replay=False)


def read_json(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise SessionError('DUPLICATE_JSON_KEY')
            result[k]=v
        return result
    def invalid(_):raise SessionError('NONFINITE_JSON_NUMBER')
    try:return json.loads(Path(path).read_text('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)
    except (OSError,UnicodeError,json.JSONDecodeError):raise SessionError('INVALID_JSON_FILE') from None


def write_json(path, value):
    encoded=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as f:f.write(encoded)


def save(session, path):
    s=_checked(session);payload=s.model_dump()
    write_json(path,dict(kind='RESEARCH_SESSION_CHECKPOINT',payload=payload,sha256=sha(payload)))


def restore(path):
    value=read_json(path)
    if type(value) is not dict or set(value)!={'kind','payload','sha256'} or value['kind'] not in (
            'PUBLIC_RESEARCH_SESSION_CHECKPOINT','RESEARCH_SESSION_CHECKPOINT'):
        raise SessionError('SESSION_CHECKPOINT_REQUIRED')
    if sha(value['payload'])!=value['sha256']:raise SessionError('SESSION_CHECKPOINT_CHANGED')
    # No saved states, native contexts, certificates or executable objects are fields.
    return _checked(ResearchSession.model_validate(value['payload']))
