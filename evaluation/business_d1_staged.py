"""Separate a remaining-allocation decision from its cited evidence.

This is a reading contract and deterministic representation adapter, not a
semantic entailment verifier. Source membership and contradiction checks are
necessary gates; neither this adapter nor an LLM may approve A4/A5 or call Core.
"""
from copy import deepcopy
import json
from typing import Literal
from . import business_d1_aggregation as prior
from .business_core_pilot_base import Closed
from .business_materials_base import bundle_value
from .business_materials_target_provenance import target_sources
from .business_materials_whole_clause_evidence import clause_choices
from .business_materials_undecided_allocation import _UNCERTAIN, _DENIED

VERSION = 'business-d1-staged-v0.49.1'
study_request = prior.study_request
review_study = prior.review_study


from cfm_id.workflows.legacy_network.d1_staged import Remaining


def target_request(bundle, study_raw):
    system, user = prior.target_request(bundle, study_raw)
    message = json.loads(user)
    question = message['output_schema']['$defs']['Question']
    for field in ('remaining_source', 'remaining_evidence_span'):
        question['properties'].pop(field)
        question['required'].remove(field)
    question['properties']['remaining'] = Remaining.model_json_schema()
    question['required'].append('remaining')
    # Remove the inherited instructions for the two replaced wire fields.
    old = ('remaining_source引用当前目标中肯定说明其他人按原抽签在满足条件的安排中平均的语句，'
           '并用remaining_evidence_span引用完整连续语句。\n'
           '安排未说明、未决定或被否定时两字段都null；过去的抽签规则不能替业务方确定当前目标。')
    if system.count(old) != 1:
        raise ValueError('EXPECTED_PRIOR_REMAINING_INSTRUCTIONS')
    system = system.replace(old, '')
    system += '''
每个问题用remaining对象分别表示其他人的安排规则和原文证据：
rule=原抽签条件平均，仅在当前目标明确说其余人沿用原抽签、在符合所问条件的安排中按原概率平均时采用；source与quote都必须填写。
rule=未确定，用于没有说明、尚未决定或几种提议还未选定。可以引用说明“尚未决定”的原文；完全没有信息时source与quote均为null。
rule=其他安排，用于明确选择了另一种安排，必须引用实际安排；本入口不支持这种安排，不能改为原抽签。
source为当前目标材料的来源编号，quote为该来源中的连续完整语句；两者同时有值或同时null。保留否定、尚未决定等词。
引文存在只表示有材料，不表示安排规则已经确定。不能由study中的历史抽签事实代替当前目标的安排选择。
本次只返回questions；规则分类和引文仍是阅读候选，不是科学许可或识别证明。
'''
    return system, json.dumps(message, ensure_ascii=False)


from cfm_id.workflows.legacy_network.d1_staged import project_target_candidate


def compose_reading(bundle, study_raw, target_raw):
    status = review_study(bundle, study_raw)
    if status['state'] != 'TARGET_INPUT_REQUIRED':
        return status
    try:
        projected, evidence = project_target_candidate(bundle, target_raw)
    except (ValueError, TypeError, KeyError) as exc:
        status.update(version=VERSION, state='DRAFT_INVALID', target_normalization_performed=True,
                      target_candidate=deepcopy(target_raw), reason_code=str(exc))
        return status
    result = prior.compose_reading(bundle, study_raw, projected)
    result.update(version=VERSION, target_candidate=deepcopy(target_raw),
                  legacy_target_candidate=projected, remaining_decisions=evidence,
                  representation_projection='explicit_rule_to_legacy_remaining_source_v0491',
                  evidence_is_semantic_proof=False)
    if result['state'] != 'DRAFT_INVALID' and any(x['rule'] == '其他安排' for x in evidence.values()):
        result.update(state='UNSUPPORTED', reason_code='REMAINING_OUTSIDE_D1_ENTRY', clarification_questions=[])
    return result


def normalize_in_stages(bundle, study_provider, target_provider=None):
    s, u = study_request(bundle)
    study = study_provider.generate_json(system_prompt=s, user_prompt=u)
    status = review_study(bundle, study)
    if status['state'] != 'TARGET_INPUT_REQUIRED' or target_provider is None:
        return status
    s, u = target_request(bundle, study)
    raw = target_provider.generate_json(system_prompt=s, user_prompt=u)
    return compose_reading(bundle, study, raw)
