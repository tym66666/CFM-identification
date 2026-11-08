"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.d2_submission as d2
import cfm_id.workflows.legacy_network.arm_submission as cluster
import cfm_id.workflows.legacy_network.materials as materials
from cfm_id.workflows.legacy_network.d1_staged import Remaining
from cfm_id.workflows.legacy_network.d1_staged import project_target_candidate
from cfm_id_llm.providers.declared_outcome_contract import annotate_outcome_contract


VERSION = 'business-remaining-transfer-v0.50'


ENTRY_D2 = 'D2_ARM'


ENTRY_CLUSTER = 'CLUSTER_ARM'


INSTRUCTION = '''
每个问题的remaining分成rule、source、quote三个字段。
rule=原抽签条件平均：当前目标明确要求其余对象沿原试验抽签，在符合所问情形的安排中按原有概率平均；必须提供来源和完整引文。
rule=未确定：没有说明、尚未决定或提议尚未选定；如果有表达未定的原文，可以保留source和quote；完全没有信息时两者都null。
rule=其他安排：明确选了另一种规则，必须引用实际安排；当前局部条件入口不支持这种规则，不得改写为原抽签。
source使用当前目标文件的来源编号，quote为该行连续完整语句，两者同时有值或同时null。保留否定和未定限定。
有引文不等于安排已经确定，历史抽签设计不能代替当前目标的安排选择。引用核验不证明全部语义或科学假设。
研究设计、评价对象、权重、本人状态、同伴状态分别读取；缺一项不应删掉其他已知条件，也不得自动补齐。
'''


def _entry(entry):
    if entry == ENTRY_D2:
        return d2.make_request, d2.project, d2.identify_submission
    if entry == ENTRY_CLUSTER:
        return materials.make_request, materials.project, cluster.identify_arm_submission
    raise ValueError('UNKNOWN_REVIEWED_ARM_ENTRY')


def make_request(bundle, entry):
    build, _, _ = _entry(entry)
    system, user = annotate_outcome_contract(*build(bundle))
    message = json.loads(user)
    question = message['output_schema']['$defs']['Question']
    for name in ('remaining_source', 'remaining_evidence_span'):
        question['properties'].pop(name)
        question['required'].remove(name)
    question['properties']['remaining'] = Remaining.model_json_schema()
    question['required'].append('remaining')
    if entry == ENTRY_D2:
        old = '''remaining_source引用当前目标中肯定说明其余分配沿原抽签在满足条件的安排中平均的原句。
只说明过去怎么抽签不能替业务目标决定其余安排。尚未决定、否定或未说明时两个remaining字段均null。
remaining_evidence_span引用来源内完整连续语句，不删否定、不缩为几个词。该引用不是科学证明。'''
        if system.count(old) != 1:
            raise ValueError('EXPECTED_D2_REMAINING_INSTRUCTIONS')
        system = system.replace(old, '')
    else:
        # Each replaced paragraph belongs solely to the superseded wire fields.
        parts = system.split('\n\n')
        parts = [p for p in parts if 'remaining_source' not in p and 'remaining_evidence_span' not in p]
        system = '\n\n'.join(parts)
    if 'remaining_source' in system or 'remaining_evidence_span' in system:
        raise ValueError('CONFLICTING_LEGACY_REMAINING_INSTRUCTIONS')
    return system + INSTRUCTION, json.dumps(message, ensure_ascii=False)


def project_reading(bundle, raw, entry):
    _, project, _ = _entry(entry)
    if not isinstance(raw, dict) or set(raw) != {'study', 'questions'}:
        raise ValueError('STUDY_AND_QUESTIONS_REQUIRED')
    projected, evidence = project_target_candidate(bundle, {'questions': raw['questions']})
    draft = dict(study=deepcopy(raw['study']), questions=projected['questions'])
    # Validate the selected entry's unchanged design and target contracts.
    project(bundle, draft)
    return draft, evidence


def identify_reading(bundle, raw, entry, packet=None, *, context=None, synthetic_protocol_selected=False):
    _, project, identify = _entry(entry)
    try:
        draft, evidence = project_reading(bundle, raw, entry)
    except (ValueError, TypeError, KeyError) as exc:
        return dict(version=VERSION, state='DRAFT_INVALID', reason_code=str(exc), reading_candidate=deepcopy(raw),
                    draft=None, query_views=[], core_called=False, candidate_model_calls=0, production_admission=False,
                    estimation_called=False, policy_called=False, estimation_handoff_allowed=False, clarification_questions=[])
    result = identify(bundle, draft)
    _, _, targets = project(bundle, draft)
    if result['state'] != 'DRAFT_INVALID' and any(x['rule'] == '其他安排' for x in evidence.values()):
        result.update(state='UNSUPPORTED', reason_code='REMAINING_OUTSIDE_REVIEWED_ARM_ENTRY')
        if 'view' in result:
            result['view'].update(state='UNSUPPORTED', label='当前入口不支持这项安排', conclusion='保留实际目标，未进入识别。')
    elif result['state'] == 'REVIEW_REQUIRED':
        result = identify(bundle, draft, packet, context=context, synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION, reading_candidate=deepcopy(raw), remaining_decisions=evidence,
                  representation_projection='explicit_rule_to_legacy_remaining_source_v0491', evidence_is_semantic_proof=False,
                  clarification_questions=[])
    if result['state'] == 'NEEDS_INPUT':
        for qid, target in zip(bundle['question_slots'], targets):
            if target.remaining is None:
                result['clarification_questions'].append(dict(query_id=qid, field='remaining',
                    text='除了题中已经指定的情况，其他对象怎样安排？请说明本次要评价的安排规则。'))
    return result
