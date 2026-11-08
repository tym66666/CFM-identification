"""Explicit A0 source re-reading, independent of theorem or research family."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, model_serializer
from . import business_intake as intake
from .fact_reading_revision import StrictRecord,ReadingFeedback,_paths,_check_feedback,MAX_ROUNDS
from cfm_id_llm.compact_reference_contract import catalog,rebind_revision

VERSION='intake-reading-revision-1'


class IntakeFeedback(ReadingFeedback):
    version: Literal['intake-reading-feedback-1']='intake-reading-feedback-1'


class Step(StrictRecord):
    request_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    candidate: dict
    feedback: IntakeFeedback
    field_role_contract: Literal['query-schema-1'] | None = None

    @model_serializer(mode='wrap')
    def preserve_historical_step(self, handler):
        value = handler(self)
        if self.field_role_contract is None:
            value.pop('field_role_contract', None)
        return value


class Revision(StrictRecord):
    version: Literal['intake-reading-revision-1']=VERSION
    steps: list[Step]=Field(min_length=1,max_length=MAX_ROUNDS)


def sources(s):
    return {r['ref']:dict(source_id=r['ref'],doc_id=r['source_id'],text=r['quote'])
            for r in catalog(s.case,s.a0_reference_contract)}


def _identity(s,base):
    return dict(intake_id=s.intake_id,revision=s.revision,case=s.case.model_dump(mode='json'),
                reading_format=s.reading_format,base_request=base)


def _sha_request(s,request):
    return intake._sha(dict(intake_id=s.intake_id,revision=s.revision,request=request))


def _format_issues(s,request,candidate):
    from cfm_id_llm.compact_wire_diagnostics import diagnose
    from cfm_id_llm.compact_reference_contract import request_context
    return diagnose(s.case,candidate,response_contract=s.a0_response_contract,
        reference_contract=s.a0_reference_contract,
        expected_context=request_context(request['user_prompt']) if s.a0_reference_contract else None)


def _sheet(s,base,steps,request,candidate,authority):
    return dict(version='intake-reading-feedback-1',binding_sha256=intake._sha(dict(version=VERSION,
        identity=_identity(s,base),steps=steps,request_sha256=_sha_request(s,request),candidate=candidate)),
        expected_authority=authority,candidate_sha256=intake._sha(candidate),field_paths=_paths(candidate),
        source_catalog=sources(s),format_issues=_format_issues(s,request,candidate),issues=[],is_approval=False)


def apply_revision(s,base):
    history=Revision.model_validate(s.reading_revision)
    request=deepcopy(base);steps=[];authority=history.steps[0].feedback.authority
    for step in history.steps:
        if step.request_sha256!=_sha_request(s,request):raise ValueError('STALE_A0_RECHECK_REQUEST')
        sheet=_sheet(s,base,steps,request,step.candidate,authority)
        feedback=_check_feedback(sheet,step.feedback,IntakeFeedback)
        steps.append(step.model_dump(mode='json'))
        public=dict(kind='A0_RECHECK_CONTEXT_NOT_EVIDENCE',previous_candidate=deepcopy(step.candidate),
            issues=[dict(field_path=i.field_path,kind=i.kind,source_refs=i.source_ids) for i in feedback.issues])
        from cfm_id_llm.compact_unified_contract import recheck_field_roles
        from cfm_id_llm.compact_response_contract import evidence_contract
        adapter = evidence_contract(s.a0_response_contract)
        recheck_field_roles = getattr(adapter, 'recheck_field_roles', recheck_field_roles)
        roles = recheck_field_roles([i.field_path for i in feedback.issues],contract=s.a0_response_contract)
        if step.field_role_contract == 'query-schema-1':
            from cfm_id_llm.compact_response_contract import scope_recheck_roles
            roles = scope_recheck_roles(roles, contract=s.a0_response_contract,
                user_prompt=base['user_prompt'], candidate=step.candidate)
        if roles:
            public['field_role_constraints'] = roles
        format_paths={i.field_path for i in feedback.issues if i.kind=='WIRE_FORMAT_ERROR'}
        if format_paths:
            public['wire_format_constraints']=[d for d in sheet['format_issues'] if d['field_path'] in format_paths]
        request=dict(base,prompt_version=base['prompt_version']+':'+VERSION,
            reading_revision_sha256=intake._sha(steps),
            system_prompt=base['system_prompt']+'''
本轮重新阅读原始业务材料。旧回答和复查定位不是事实来源，不是科学批准，定位也可能不正确。按原文重读全部业务目标和字段，返回完整候选，不返回补丁。只使用原目录引用；不照抄旧候选，不为填字段推算识别公式或目标下暴露。不替用户补条件，不删除真实限制，不输出识别结论。''',
            user_prompt=base['user_prompt']+'\n\n独立复查定位（不是新增事实）：\n'+json.dumps(public,ensure_ascii=False))
        if roles:
            request['system_prompt']+='\nfield_role_constraints来自本次读取Schema的字段职责，不是审核者的替换值或新增事实。用原文核对被指出的字段属于哪类内容，并重读全部候选。原本未定、否定或真正额外的条件仍须保留，不能为了符合提示补条件或删除限制。'
        if format_paths:
            request['system_prompt']+='\nwire_format_constraints来自当前读取类型合同，只说明格式错误位置和合法枚举，不是替换答案、业务事实或科学批准。结合原文重新输出完整候选；不能为通过格式而填补未知、改换目标或删掉真实条件。诊断为空也不表示读对。'
        if s.a0_reference_contract:
            request=rebind_revision(request,base,intake._sha(steps))
    return request


def prepare_recheck(value,*,feedback=None,authority='EXTERNAL_RESEARCH_REVIEW'):
    s=intake._checked(value)
    if s.candidate is None:raise intake.IntakeError('A0_CANDIDATE_REQUIRED_FOR_RECHECK')
    if s.reading_format!='compact':raise intake.IntakeError('A0_RECHECK_REQUIRES_COMPACT_FORMAT')
    old=Revision.model_validate(s.reading_revision) if s.reading_revision else None
    steps=[v.model_dump(mode='json') for v in old.steps] if old else []
    if len(steps)>=MAX_ROUNDS:raise intake.IntakeError('EXPLICIT_A0_RECHECK_ROUND_LIMIT')
    if authority not in ('SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW'):raise ValueError('INVALID_FEEDBACK_AUTHORITY')
    if old:authority=old.steps[0].feedback.authority
    base=intake._base_request(s)
    sheet=_sheet(s,base,steps,intake._request(s),s.candidate,authority)
    if feedback is None:
        return dict(state='REVIEW_REQUIRED',feedback_worksheet=sheet,request=None,api_calls=0,
                    scientific_approval=False,mathematical_claim=None)
    r=_check_feedback(sheet,feedback,IntakeFeedback)
    step = dict(request_sha256=s.request_sha256,candidate=deepcopy(s.candidate),feedback=r.model_dump(mode='json'))
    from cfm_id_llm.compact_response_contract import LOCAL_COMPARISON_PROFILES
    if s.a0_response_contract in LOCAL_COMPARISON_PROFILES:
        # Version only new rechecks. Replaying an issued request must never
        # silently substitute different instructions or invalidate its receipt.
        step['field_role_contract'] = 'query-schema-1'
    steps.append(step)
    event=dict(action='SOURCE_LOCATED_A0_RECHECK',previous_sha256=intake._sha(s.model_dump(mode='json')))
    if s.reading_stop_review is not None:event['previous_stop_review']=deepcopy(s.reading_stop_review)
    revised=s.model_copy(update=dict(candidate=None,reading_revision=dict(version=VERSION,steps=steps),
        reading_change_review=None,reading_stop_review=None,history=[*s.history,event]))
    return intake._checked(revised.model_copy(update=dict(request_sha256=intake._request_sha(revised))))


def inspect_changes(s):
    from .reading_change_review import inspect_changes as check
    if not s.reading_revision:
        if s.reading_change_review is not None:raise ValueError('A0_CHANGE_REVIEW_WITHOUT_REVISION')
        return None
    if s.candidate is None:
        if s.reading_change_review is not None:raise ValueError('A0_CHANGE_REVIEW_WITHOUT_CANDIDATE')
        return None
    history=Revision.model_validate(s.reading_revision)
    return check(binding=dict(request_sha256=s.request_sha256,history=s.reading_revision),
        before=history.steps[-1].candidate,after=s.candidate,source_catalog=sources(s),
        authority=history.steps[0].feedback.authority,review=s.reading_change_review)


def review_changes(value,review):
    s=intake._checked(value)
    if review is None:raise intake.IntakeError('A0_CHANGE_REVIEW_REQUIRED')
    revised=intake._checked(s.model_copy(update=dict(reading_change_review=deepcopy(review),reading_stop_review=None)))
    inspect_changes(revised)  # Reject stale/invalid review before saving.
    if s.reading_change_review is not None:
        event=dict(action='REVISE_A0_CHANGE_REVIEW',previous_sha256=intake._sha(s.model_dump(mode='json')),
                   previous_change_review=deepcopy(s.reading_change_review))
        revised=intake._checked(revised.model_copy(update=dict(history=[*s.history,event])))
    if s.reading_stop_review is not None:
        event=dict(action='CLEAR_STOP_REVIEW_AFTER_CHANGE_REVIEW',previous_sha256=intake._sha(s.model_dump(mode='json')),
                   previous_stop_review=deepcopy(s.reading_stop_review))
        revised=intake._checked(revised.model_copy(update=dict(history=[*revised.history,event])))
    return revised
