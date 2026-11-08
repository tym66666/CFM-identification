"""Explicit source-located re-reading; never edit candidates or grant science.

The caller authorizes each model invocation. This module only prepares requests
and validates the complete bounded history against the current original input.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from . import business_dispatch as dispatch

VERSION='fact-reading-revision-1'
MAX_ROUNDS=3
sha=dispatch.sha


class StrictRecord(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)


class ReadingIssue(StrictRecord):
    # RFC 6901: empty pointer selects the whole object, useful for omitted keys.
    field_path: str=Field(max_length=500)
    kind: Literal['OMITTED_OR_MISREAD','POSSIBLE_DUPLICATION','UNSUPPORTED_ADDITION','WIRE_FORMAT_ERROR']
    source_ids: list[str]=Field(min_length=1,max_length=64)
    reason: str=Field(min_length=12,max_length=1200)


class ReadingFeedback(StrictRecord):
    version: Literal['fact-reading-feedback-1']='fact-reading-feedback-1'
    binding_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW']
    reviewer: str=Field(min_length=3,max_length=200)
    evidence: str=Field(min_length=12,max_length=3000)
    issues: list[ReadingIssue]=Field(min_length=1,max_length=20)


class RevisionStep(StrictRecord):
    request_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    candidate: dict
    feedback: ReadingFeedback


class ReadingRevision(StrictRecord):
    version: Literal['fact-reading-revision-1']=VERSION
    steps: list[RevisionStep]=Field(min_length=1,max_length=MAX_ROUNDS)


def _references(entry):
    if entry.get('reference_format')!='short_refs':
        raise dispatch.DispatchError('ADAPTER_NOT_CONNECTED','RECHECK_REQUIRES_SHORT_FACT_READING')
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    contract=contract_for_entry(entry)
    if contract is not None:
        return contract.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    raise dispatch.DispatchError('ADAPTER_NOT_CONNECTED','RECHECK_READER_NOT_CONNECTED')


def _paths(candidate):
    if type(candidate) is not dict:
        raise ValueError('JSON_OBJECT_REQUIRED')
    if len(json.dumps(candidate,ensure_ascii=False,allow_nan=False).encode('utf8'))>1000000:
        raise ValueError('RECHECK_CANDIDATE_TOO_LARGE')
    paths=['']
    def walk(value,path):
        if path:paths.append(path)
        if isinstance(value,dict):
            for key,child in value.items():
                if type(key) is not str:raise ValueError('JSON_STRING_KEYS_REQUIRED')
                walk(child,path+'/'+key.replace('~','~0').replace('/','~1'))
        elif isinstance(value,list):
            for i,child in enumerate(value):walk(child,path+'/'+str(i))
    walk(candidate,'')
    return paths


def _public_constraints(entry,paths):
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    contract=contract_for_entry(entry)
    if contract is not None:
        return contract.public_constraints(entry,paths)
    return []


def _sheet(entry,candidate):
    refs=_references(entry)
    paths=_paths(candidate)
    from cfm_id_llm.wire_type_diagnostics import diagnose
    out=dict(version='fact-reading-feedback-1',binding_sha256=sha(dict(version=VERSION,entry=entry,candidate=candidate)),
        expected_authority=entry['query_review']['authority'],candidate_sha256=sha(candidate),
        field_paths=paths,format_issues=diagnose(entry,candidate),
        source_catalog={r['source_id']:deepcopy(r) for r in refs['aliases'].values()},
        issues=[],is_approval=False,scope='Locate reading errors only. No replacement values, scientific permission or identification answer.')
    rules=_public_constraints(entry,[''])
    if rules:out['public_field_constraints']=rules
    return out


def _check_feedback(sheet,value,cls=ReadingFeedback):
    raw=value.model_dump(mode='json') if type(value) is cls else value
    r=cls.model_validate(raw)
    if (r.binding_sha256!=sheet['binding_sha256'] or r.authority!=sheet['expected_authority'] or
            not r.reviewer.strip() or not r.evidence.strip()):raise ValueError('FEEDBACK_SCOPE_OR_AUTHORITY_MISMATCH')
    seen=set()
    for issue in r.issues:
        identity=(issue.field_path,issue.kind)
        paths=({d['field_path'] for d in sheet.get('format_issues',[])}
               if issue.kind=='WIRE_FORMAT_ERROR' else sheet['field_paths'])
        if (identity in seen or issue.field_path not in paths or not issue.reason.strip() or
            len(issue.source_ids)!=len(set(issue.source_ids)) or
            any(s not in sheet['source_catalog'] for s in issue.source_ids)):
            raise ValueError('INVALID_READING_ISSUE_OR_SOURCE')
        seen.add(identity)
    return r


def apply_revision(base,revision,*,contexts,signed_comparison=False):
    """Rebuild every request; stale source, query, prompt or feedback is rejected."""
    raw=revision.model_dump(mode='json') if type(revision) is ReadingRevision else revision
    history=ReadingRevision.model_validate(raw)
    current=deepcopy(base);steps=[]
    for step in history.steps:
        if step.request_sha256!=current['request_sha256']:
            raise ValueError('STALE_RECHECK_PREVIOUS_REQUEST')
        review=_check_feedback(_sheet(current,step.candidate),step.feedback)
        steps.append(step.model_dump(mode='json'))
        binding=sha(dict(version=VERSION,base_fact_binding_sha256=base['fact_binding_sha256'],steps=steps))
        revised=dict(base,fact_binding_sha256=binding)
        refs=_references(revised)
        aliases={r['source_id']:key for key,r in refs['aliases'].items()}
        target=base.get('reviewed_local_request',{})
        request=dispatch._fact_request(base['bundle'],binding,base['reader_id'],base['reference_format'],base['selected_query'],contexts,
                                       assignment_semantics=base.get('assignment_semantics'),network_fact_contract=base.get('network_fact_contract'),
                                       observational_fact_profile=base.get('observational_fact_profile'),
                                       signed_comparison=signed_comparison,
                                       ordered_target=target.get('raw_query'),target_contract=target.get('contract'),
                                       reviewed_target_context=base.get('reviewed_target_context'),material_inventory=base.get('material_inventory'),
                                       reviewed_policy_request=base.get('reviewed_policy_request'),
                                       reviewed_intent=base.get('reviewed_intent'))
        request['system']+='''
本轮是对原事实读取的独立复查。复查定位与旧回答仅是待核对上下文，不是新业务事实或科学批准，不能作为source_ids。只引用本轮原文目录，并使用本轮reference_context。
按原文重新核对全部字段，返回完整的新候选，不返回补丁。指出的重复可能判断有误：仅当同一内容已由专用字段完整表达时避免重复；真正额外的条件、限制和未知内容必须保留。不可因复查要求而默认填值、删去限制或输出识别结论。'''
        public=dict(kind='READING_RECHECK_CONTEXT_NOT_EVIDENCE',previous_candidate=deepcopy(step.candidate),
            issues=[dict(field_path=i.field_path,kind=i.kind,source_refs=[aliases[s] for s in i.source_ids]) for i in review.issues])
        rules=_public_constraints(base,[i.field_path for i in review.issues])
        if rules:
            public['public_field_constraints']=rules
            request['system']+='\npublic_field_constraints来自当前公开字段定义，与首次Schema和审核工作表相同；它们不是新增原文、私有评审理由或该题替换答案。结合本轮原文逐项核对，不能用它们作为source_ids。'
        format_paths={i.field_path for i in review.issues if i.kind=='WIRE_FORMAT_ERROR'}
        if format_paths:
            from cfm_id_llm.wire_type_diagnostics import diagnose
            public['wire_format_constraints']=[d for d in diagnose(current,step.candidate)
                                                if d['field_path'] in format_paths]
            request['system']+='\nwire_format_constraints只来自当前读取类型合同，表示格式错误位置和合法枚举，不是业务事实、替换答案或科学批准。按本轮Schema与原文重新输出完整候选；不能为通过格式校验而改变目标、填补未知或删除真实约束。'
            if any('field_rule' in row for row in public['wire_format_constraints']):
                request['system']+='\nfield_rule是现有字段组合规则：nonempty表示该列表非空，nonnull_values表示其中有非null的value；此时required_field必须符合required_value。原文性质优先：不能为了过校验将样本或未知改称精确总体。先核对原文，再选择忠实的字段表示，样本原文及引用必须保留。'
            if any('field_combination' in row for row in public['wire_format_constraints']):
                request['system']+='\nfield_combination来自首次请求的公开字段组合规则：trigger=nonempty表示列表非空，其他trigger表示该字段等于所列枚举；此时另一字段应符合required_value。定位到整条信息记录不代表已经确定哪个字段误读；须回到原文判断。不得为通过校验把有限样本改为总体信息，也不得删除真实样本来源；独立提供的样本与总体信息应分别保留。'
        # Reviewer identity, free-text reasons, decisions and expected answers stay local.
        request['user']+='\n\n独立复查定位（不是新增事实）：\n'+json.dumps(public,ensure_ascii=False)
        current=dict(revised,request=request,request_sha256=sha(dict(version=VERSION,base_request_sha256=base['request_sha256'],steps=steps,request=request)),
            reading_revision=dict(version=VERSION,steps=deepcopy(steps)),
            reading_revision_receipt=dict(version=VERSION,rounds=len(steps),history_sha256=sha(steps),
                previous_candidate_sha256=sha(step.candidate),feedback_sha256=sha(review.model_dump(mode='json')),
                original_materials_sha256=sha(base['bundle']),candidate_modified=False,scientific_approval=False,
                mathematical_verification='NOT_PERFORMED',automatic_retry=False))
    return current


def prepare_recheck(intake,query_id,*,query_review,candidate,request_sha256,reading_revision=None,feedback=None):
    """Worksheet first; explicit independent feedback permits one new request."""
    out=dispatch.empty_result()
    try:
        entry=dispatch.prepare_reader(intake,query_id,query_review=query_review,reading_revision=reading_revision)
        if entry['state']!='READY_TO_READ':return entry
        if request_sha256!=entry['request_sha256']:raise ValueError('STALE_RECHECK_RESPONSE')
        old=entry.get('reading_revision',dict(version=VERSION,steps=[]))
        if len(old['steps'])>=MAX_ROUNDS:
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='EXPLICIT_RECHECK_ROUND_LIMIT',request=None,
                        reading_revision=deepcopy(old))
        sheet=_sheet(entry,candidate)
        out.update(state='REVIEW_REQUIRED',reason_code='INDEPENDENT_READING_FEEDBACK_REQUIRED',request=None,
                   feedback_worksheet=sheet,previous_candidate=deepcopy(candidate),request_sha256=request_sha256)
        if feedback is None:return out
        review=_check_feedback(sheet,feedback)
        revision=dict(version=VERSION,steps=[*old['steps'],dict(request_sha256=request_sha256,
            candidate=deepcopy(candidate),feedback=review.model_dump(mode='json'))])
        return dispatch.prepare_reader(intake,query_id,query_review=query_review,reading_revision=revision)
    except dispatch.DispatchError as exc:
        return dict(out,state=exc.state,reason_code=exc.reason,request=None)
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_OR_STALE_READING_FEEDBACK',request=None)
