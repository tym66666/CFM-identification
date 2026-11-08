"""Route-neutral business reading. No method selection or scientific approval.

This is the public intake before the specialist research-session adapters.
It reuses the existing A0 contract, including its limits; it is not an automatic
translator into native mathematical problems. Saved content is never executable.
"""
from __future__ import annotations

from hashlib import sha256
from copy import deepcopy
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from cfm_id_llm.quality import MultiQueryDraftV010, audit_business_quality
from cfm_id_llm.quality_prompts import (
    PROMPT_VERSION_V010, SYSTEM_PROMPT_V010, make_quality_user_prompt,
)
from cfm_id_llm.schemas import BusinessCase, SourceDocument, SourceKind
from cfm_id_llm.compact_formulator import CompactFormulator, make_compact_request, COMPACT_PROMPT_VERSION
from cfm_id_llm.evidence_refs import _BoundDraftProvider
from cfm_id_llm.assignment_semantics import Profile
from cfm_id_llm.target_summary_contract import Profile as TargetSummaryProfile
from cfm_id_llm.compact_reference_contract import Profile as A0ReferenceProfile
from cfm_id_llm.compact_response_contract import Profile as A0ResponseProfile
from cfm_id_llm.quality_formulator import A0QualityValidationError
from .business_reading_config import ReadingConfig, ReadingFormat, FactFormat, ObservationalProfile
from cfm_id_llm.network_fact_protocols import NetworkFactProfile


class IntakeError(ValueError):
    pass


def _sha(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


class ClarificationContext(BaseModel):
    """Assistant-generated context; not part of the quotable user sources."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['ASSISTANT_CONTEXT_NOT_EVIDENCE'] = 'ASSISTANT_CONTEXT_NOT_EVIDENCE'
    query_id: str = Field(pattern=r'^q[1-9][0-9]{0,2}$')
    previous_goal: str = Field(min_length=1, max_length=2500)
    question: str = Field(min_length=1, max_length=2000)
    reply_source_id: str = Field(min_length=1, max_length=80)


class BusinessIntake(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: Literal['business-intake-1'] = 'business-intake-1'
    intake_id: str
    revision: int = Field(default=0, ge=0)
    case: BusinessCase
    request_sha256: str
    # Absent in historical checkpoints: retain their exact canonical request.
    reading_format: ReadingFormat = 'canonical'
    fact_format: FactFormat = 'source_hash'
    candidate: dict | None = None
    clarifications: list[ClarificationContext] = Field(default_factory=list, max_length=20)
    history: list[dict] = Field(default_factory=list)
    reading_revision: dict | None = None
    reading_change_review: dict | None = None
    reading_stop_review: dict | None = None
    assignment_semantics: Profile = None
    target_summary_contract: TargetSummaryProfile = None
    a0_reference_contract: A0ReferenceProfile = None
    a0_response_contract: A0ResponseProfile = None
    network_fact_contract: NetworkFactProfile = None
    observational_fact_profile: ObservationalProfile = None
    material_handoff: Literal['information-inventory-1'] | None = None

    @model_serializer(mode='wrap')
    def omit_absent_review_extensions(self,handler):
        # Preserve historical checkpoint and review hashes for ordinary reads.
        value=handler(self)
        for key in ('reading_revision','reading_change_review','reading_stop_review','assignment_semantics','network_fact_contract','target_summary_contract','a0_reference_contract','a0_response_contract','material_handoff','observational_fact_profile'):
            if value.get(key) is None:value.pop(key,None)
        return value


def _base_request(s):
    if s.reading_format == 'compact':
        system, user, _ = make_compact_request(s.case, assignment_semantics=s.assignment_semantics,
            target_summary_contract=s.target_summary_contract,a0_reference_contract=s.a0_reference_contract,
            reference_scope=dict(intake_id=s.intake_id,revision=s.revision),a0_response_contract=s.a0_response_contract)
        version = COMPACT_PROMPT_VERSION + ('+' + s.assignment_semantics if s.assignment_semantics else '')
        if s.target_summary_contract:
            version += '+' + s.target_summary_contract
        if s.a0_reference_contract:
            version += '+' + s.a0_reference_contract
        if s.a0_response_contract:
            version += '+' + s.a0_response_contract
    else:
        user = make_quality_user_prompt(s.case)
        system, version = SYSTEM_PROMPT_V010, PROMPT_VERSION_V010
    if s.clarifications:
        user += ('\n\n澄清上下文：下面的 previous_goal 和 question 是此前助手的待审核表述，'
                 '不是用户事实，也不是可引用来源。它们仅帮助理解用户在回答什么；'
                 '不得从问题的前提推定事实。用户实际答复只在 reply_source_id 对应的 sources.text 中。'
                 '答复不清楚时继续保留未知。重新核对全部目标，不把旧 query_id 当永久目标编号。\n'
                 + json.dumps([c.model_dump(mode='json') for c in s.clarifications], ensure_ascii=False))
    return dict(prompt_version=version, system_prompt=system,
                user_prompt=user)


def _request(s):
    base=_base_request(s)
    if s.reading_revision is not None:
        from .intake_reading_revision import apply_revision
        return apply_revision(s,base)
    return base


def _request_sha(s):
    return _sha(dict(intake_id=s.intake_id, revision=s.revision, request=_request(s)))


def _checked(value):
    raw = value.model_dump(mode='json') if isinstance(value, BusinessIntake) else value
    s = BusinessIntake.model_validate(raw)
    if s.observational_fact_profile is not None and s.fact_format != 'short_refs':
        raise IntakeError('OBSERVATIONAL_PROFILE_REQUIRES_SHORT_REFS')
    if s.material_handoff and (s.reading_format!='compact' or s.fact_format!='short_refs'):
        raise IntakeError('MATERIAL_HANDOFF_REQUIRES_COMPACT_AND_SHORT_REFS')
    if s.a0_reference_contract is not None and s.reading_format != 'compact':
        raise IntakeError('A0_REFERENCE_CONTRACT_REQUIRES_COMPACT')
    if s.a0_response_contract is not None and s.reading_format != 'compact':
        raise IntakeError('A0_RESPONSE_CONTRACT_REQUIRES_COMPACT')
    replies = [c.reply_source_id for c in s.clarifications]
    if len(set(replies)) != len(replies) or any(x not in {d.source_id for d in s.case.sources} for x in replies):
        raise IntakeError('CLARIFICATION_REPLY_SOURCE_MISSING_OR_DUPLICATE')
    if s.request_sha256 != _request_sha(s):
        raise IntakeError('INTAKE_MATERIAL_OR_PROMPT_CHANGED')
    _sha(s.model_dump(mode='json'))  # Reject non-JSON/nonfinite candidate values.
    return s


def start(case: BusinessCase | dict, *, reading_format='compact', fact_format='short_refs',
          assignment_semantics=None, network_fact_contract=None, target_summary_contract=None,
          a0_reference_contract=None, a0_response_contract=None, material_handoff=None, observational_fact_profile=None) -> BusinessIntake:
    """Accept question and sources without asking the user to choose a method."""
    if isinstance(case, BusinessCase):
        case = case.model_dump(mode='json')
    s = BusinessIntake(intake_id=str(uuid4()), case=BusinessCase.model_validate(case), request_sha256='',
                       reading_format=reading_format, fact_format=fact_format,
                       assignment_semantics=assignment_semantics if reading_format == 'compact' else None,
                       target_summary_contract=target_summary_contract if reading_format == 'compact' else None,
                       a0_reference_contract=a0_reference_contract,
                       a0_response_contract=a0_response_contract,
                       network_fact_contract=network_fact_contract, material_handoff=material_handoff,
                       observational_fact_profile=observational_fact_profile)
    return _checked(s.model_copy(update={'request_sha256': _request_sha(s)}))


def start_configured(case: BusinessCase | dict, config: ReadingConfig | dict) -> BusinessIntake:
    """Initialize from developer settings without a route or scientific permit.

    Historical ``start`` kwargs remain supported. Existing checkpoints retain
    their flat fields and hashes; this function only creates a new intake.
    """
    if isinstance(config, ReadingConfig):
        config = config.model_dump(mode='json')
    return start(case, **ReadingConfig.model_validate(config).intake_options())


def configure_fact_format(intake, fact_format):
    """Change only a specialist wire protocol; preserve A0 and invalidate reviews."""
    s = _checked(intake)
    event = dict(action='CONFIGURE_FACT_FORMAT', previous_sha256=_sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:event['previous_stop_review']=deepcopy(s.reading_stop_review)
    return _checked(s.model_copy(update=dict(fact_format=fact_format,reading_stop_review=None,history=[*s.history, event])))


def configure_network_fact_contract(intake, contract):
    """Select an experimental wire, preserving A0 and invalidating old reviews."""
    s = _checked(intake)
    event = dict(action='CONFIGURE_NETWORK_FACT_CONTRACT', previous_sha256=_sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:event['previous_stop_review']=deepcopy(s.reading_stop_review)
    return _checked(s.model_copy(update=dict(network_fact_contract=contract,reading_stop_review=None,history=[*s.history, event])))


def configure_material_handoff(intake, contract='information-inventory-1'):
    """Opt in to source-bound accounting; invalidate reviews, not A0 answers."""
    s=_checked(intake)
    event=dict(action='CONFIGURE_MATERIAL_HANDOFF',previous_sha256=_sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:event['previous_stop_review']=deepcopy(s.reading_stop_review)
    return _checked(s.model_copy(update=dict(material_handoff=contract,reading_stop_review=None,history=[*s.history,event])))


def prepare_request(intake):
    s = _checked(intake)
    return dict(**_request(s), request_sha256=s.request_sha256)


def receive_candidate(intake, candidate, *, request_sha256):
    s = _checked(intake)
    if request_sha256 != s.request_sha256:
        raise IntakeError('STALE_INTAKE_RESPONSE')
    if type(candidate) is not dict:
        raise IntakeError('JSON_OBJECT_CANDIDATE_REQUIRED')
    _sha(candidate)
    event = dict(action='RECEIVE_CANDIDATE', previous_sha256=_sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:
        event['previous_stop_review'] = deepcopy(s.reading_stop_review)
    return _checked(s.model_copy(update={'candidate': candidate, 'reading_change_review':None,
                                        'reading_stop_review':None,'history': [*s.history, event]}))


def read_once(intake, provider):
    """One caller-authorized provider invocation; no retries or backend calls."""
    request = prepare_request(intake)
    raw = provider.generate_json(system_prompt=request['system_prompt'], user_prompt=request['user_prompt'])
    return receive_candidate(intake, raw, request_sha256=request['request_sha256'])


def wire_recheck_issues(gate):
    """Interpretations require the independent query review, not regeneration.

    No meaning is accepted here. All other wire signals remain hard rechecks;
    the complete original gate is retained for the external reviewer.
    """
    return [item for item in (gate or {}).get('issues', [])
            if item['code'] != 'INTERPRETATION_REQUIRES_REVIEW']


def inspect(intake):
    s = _checked(intake)
    out = dict(state='READING_REQUIRED', request_sha256=s.request_sha256,
               method_matching='NOT_PERFORMED', core_called=False,
               scientific_review_required=True, mathematical_claim=None, certificate=None,
               production_admission=False, estimation_handoff_allowed=False)
    if s.candidate is None:
        return out
    gate = None
    try:
        if s.reading_format == 'compact':
            # Local projection only. This provider returns the stored raw reply;
            # it never invokes an LLM, repairs a claim, or approves a condition.
            formulator = CompactFormulator(_BoundDraftProvider('intake-candidate', s.candidate),
                                          assignment_semantics=s.assignment_semantics,
                target_summary_contract=s.target_summary_contract,a0_reference_contract=s.a0_reference_contract,
                reference_scope=dict(intake_id=s.intake_id,revision=s.revision),a0_response_contract=s.a0_response_contract)
            from cfm_id_llm.compact_reference_contract import request_context
            report = formulator.formulate(s.case,response_reference_context=(
                request_context(_request(s)['user_prompt']) if s.a0_reference_contract else None))
            gate = formulator.last_gate
        else:
            draft = MultiQueryDraftV010.model_validate(s.candidate)
            report = audit_business_quality(s.case, draft, provider='intake-candidate',
                                            prompt_version=PROMPT_VERSION_V010)
    except A0QualityValidationError as exc:
        return dict(out, state='READING_RECHECK_REQUIRED', reason_code=exc.code,
                    diagnostics=exc.diagnostics)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='READING_RECHECK_REQUIRED', reason_code='A0_SCHEMA_OR_PROVENANCE_REJECTED')
    states = {'BUSINESS_CLARIFICATION_REQUIRED': 'BUSINESS_CLARIFICATION_REQUIRED',
              'FORMULATION_RECHECK_REQUIRED': 'READING_RECHECK_REQUIRED',
              'FORMALIZATION_READY': 'SEMANTIC_REVIEW_REQUIRED'}
    state = states[report.overall_business_status]
    if gate:
        if wire_recheck_issues(gate):
            state = 'READING_RECHECK_REQUIRED'
        elif gate['proposed_business_questions'] and state != 'READING_RECHECK_REQUIRED':
            state = 'BUSINESS_CLARIFICATION_REQUIRED'
    result=dict(out, state=state, report=report.model_dump(mode='json'), wire_gate=gate)
    try:
        from .intake_reading_revision import inspect_changes
        changes=inspect_changes(s)
        if changes:
            result.update(reading_change_worksheet=changes['worksheet'],reading_change_receipt=changes['receipt'])
            if changes['state'] not in ('UNCHANGED','CHANGES_REVIEWED'):
                # No consumable report: query/case dispatch cannot skip this gate.
                result['unreviewed_report']=result.pop('report')
                result.update(state=changes['state'],reason_code=changes['reason_code'])
        if s.reading_stop_review is not None and 'report' in result:
            from .intake_stop_review import apply_review
            try:
                result = apply_review(s, result)
            except (ValueError,TypeError,KeyError,AttributeError):
                return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_OR_STALE_A0_STOP_REVIEW')
        return result
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_OR_STALE_A0_CHANGE_REVIEW')


def clarification_plan(intake):
    from cfm_id_llm.target_clarification_contract import field_path
    s = _checked(intake)
    result = inspect(s)
    questions = []
    for query in result.get('report', {}).get('query_quality', []):
        for i, question in enumerate(query['business_questions']):
            questions.append(dict(clarification_id=f"{query['query_id']}:{i}",
                                  query_id=query['query_id'], **question))
    for item in (result.get('wire_gate') or {}).get('proposed_business_questions', []):
        field = field_path(item)
        if not any(q.get('field_path') == field for q in questions):
            questions.append(dict(clarification_id=f"{item['query_id']}:slot:{item['field']}",
                query_id=item['query_id'], field_path=field, question=item['question'],
                reason='当前读取未填；须先核对原文是否确实缺少，再向业务用户追问。',
                status=item['status']))
    receipt = result.get('reading_stop_receipt')
    if receipt:
        rows = receipt['queries']
        questions = [q for q in questions if q['query_id'] not in rows]
        for qid,row in rows.items():
            for item in row['clarification_questions']:
                questions.append(dict(clarification_id=f"{qid}:slot:{item['field']}",query_id=qid,
                    field_path=field_path(item),question=item['question'],
                    reason='独立对照原文后确认该目标口径尚未提供；仅请求补充，不授予科学许可。',
                    status='SOURCE_CONFIRMED_TARGET_GAP'))
        return dict(binding_sha256=_sha(s.model_dump(mode='json')),questions=questions,
                    evidence_status='PER_QUERY_SOURCE_REVIEW',stop_review_receipt=deepcopy(receipt),
                    scientific_questions_are_separate=True)
    return dict(binding_sha256=_sha(s.model_dump(mode='json')), questions=questions,
                evidence_status='CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE',
                scientific_questions_are_separate=True)


def revise_materials(intake, case, *, reason):
    s = _checked(intake)
    return _revise(s, case, reason=reason, clarifications=[])


def _revise(s, case, *, reason, clarifications):
    if not isinstance(reason, str) or not reason.strip():
        raise IntakeError('REVISION_REASON_REQUIRED')
    if isinstance(case, BusinessCase):
        case = case.model_dump(mode='json')
    revised = BusinessCase.model_validate(case)
    if revised.case_id != s.case.case_id:
        raise IntakeError('CASE_ID_CHANGED_START_NEW_INTAKE')
    event = dict(action='REVISE_MATERIALS', reason=reason,
                 previous_sha256=_sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:
        event['previous_stop_review'] = deepcopy(s.reading_stop_review)
    if s.reading_revision:
        event.update(previous_reading_revision=deepcopy(s.reading_revision),previous_candidate=deepcopy(s.candidate),
                     previous_change_review=deepcopy(s.reading_change_review))
    new = s.model_copy(update=dict(revision=s.revision + 1, case=revised, candidate=None,reading_revision=None,reading_change_review=None,reading_stop_review=None,
                                   history=[*s.history, event], clarifications=clarifications))
    return _checked(new.model_copy(update={'request_sha256': _request_sha(new)}))


def append_reply(intake, plan, clarification_id, reply):
    """Historical single-reply interface; the supplied plan remains mandatory."""
    return _append_replies(intake, plan, {clarification_id: reply}, require_source_review=False,
                           reason='BUSINESS_CLARIFICATION_REPLY')


def append_replies(intake, plan, replies):
    """Attach answers to source-reviewed questions from one revision atomically.

    Answers become separate sources; questions remain non-evidence context.
    Missing answers, target coordinates and scientific approval are never filled.
    """
    return _append_replies(intake, plan, replies, require_source_review=True,
                           reason='BUSINESS_CLARIFICATION_REPLIES')


def _append_replies(intake, plan, replies, *, require_source_review, reason):
    s = _checked(intake)
    expected = clarification_plan(s)
    if type(plan) is not dict or plan != expected:
        raise IntakeError('STALE_OR_CHANGED_CLARIFICATION_PLAN')
    if type(replies) is not dict or not replies:
        raise IntakeError('CURRENT_QUESTION_AND_TEXT_REPLY_REQUIRED')
    items = {q['clarification_id']: q for q in expected['questions']}
    if any(k not in items or not isinstance(v, str) or not v.strip() for k,v in replies.items()):
        raise IntakeError('CURRENT_QUESTION_AND_TEXT_REPLY_REQUIRED')
    if require_source_review and any(items[k].get('status') != 'SOURCE_CONFIRMED_TARGET_GAP' for k in replies):
        raise IntakeError('SOURCE_REVIEWED_QUESTIONS_REQUIRED')
    goals = {q['query_id']:q['business_goal']['value'] for q in inspect(s)['report']['draft']['queries']}
    docs, contexts = [], []
    for item in expected['questions']:
        key = item['clarification_id']
        if key not in replies:
            continue
        doc = SourceDocument(source_id='reply_' + uuid4().hex, kind=SourceKind.BUSINESS_NARRATIVE,
            text=replies[key], label=f"对上一轮 {item['query_id']} 的业务澄清答复")
        docs.append(doc.model_dump(mode='json'))
        contexts.append(ClarificationContext(query_id=item['query_id'], previous_goal=goals[item['query_id']],
            question=item['question'], reply_source_id=doc.source_id))
    case = s.case.model_dump(mode='json')
    case['sources'].extend(docs)
    return _revise(s, case, reason=reason, clarifications=[*s.clarifications, *contexts])


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise IntakeError('DUPLICATE_JSON_KEY')
            out[key] = value
        return out
    def invalid(_):
        raise IntakeError('NONFINITE_JSON_NUMBER')
    return json.loads(Path(path).read_text('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def write_json(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(text)


def save(intake, path):
    payload = _checked(intake).model_dump(mode='json')
    write_json(path, dict(kind='BUSINESS_INTAKE_CHECKPOINT', payload=payload, sha256=_sha(payload)))


def restore(path):
    value = read_json(path)
    if type(value) is not dict or set(value) != {'kind', 'payload', 'sha256'} or value['kind'] != 'BUSINESS_INTAKE_CHECKPOINT':
        raise IntakeError('BUSINESS_INTAKE_CHECKPOINT_REQUIRED')
    if value['sha256'] != _sha(value['payload']):
        raise IntakeError('INTAKE_CHECKPOINT_CHANGED')
    return _checked(value['payload'])
