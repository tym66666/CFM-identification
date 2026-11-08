"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.evidence_entries as entries
from cfm_id.serialization import canonical_hash
import cfm_id.workflows.legacy_network.d1_submission as d1
import cfm_id.workflows.legacy_network.d2_submission as d2


VERSION='business-staged-d1-d2-v0.54'


def _model(entry):
    if entry=='D1_EFFECTS':return d1.Study
    if entry=='D2_ARM':return d2.Study
    raise ValueError('STAGED_D1_D2_ENTRY_REQUIRED')


def historical_materials(bundle,entry):
    _model(entry)
    _,user=entries.base_request(bundle,entry);m=json.loads(user)
    excluded={bundle['active_goal_document'],'business_question.md'}
    m['documents']={k:v for k,v in m['documents'].items() if k not in excluded}
    m['source_catalog']={k:v for k,v in m['source_catalog'].items() if k.split(':L')[0] in m['documents']}
    for k in ('output_schema','question_slots','active_goal_document','target_statement_sources'):m.pop(k,None)
    return m


def bind_study(bundle,entry,raw):
    if not isinstance(raw,dict) or set(raw)!={'study'}:raise ValueError('STUDY_RESPONSE_ONLY')
    s=_model(entry).model_validate(raw['study']);catalog=historical_materials(bundle,entry)['source_catalog']
    if not s.design_sources or any(x not in catalog for x in s.design_sources):raise ValueError('HISTORICAL_STUDY_SOURCE_REQUIRED')
    if (s.exposure is None)!=(s.exposure_source is None) or (s.exposure_source is not None and s.exposure_source not in catalog):
        raise ValueError('HISTORICAL_EXPOSURE_SOURCE_REQUIRED')
    if entry=='D1_EFFECTS':
        if (s.declared_independent is None)!=(s.independence_source is None) or (s.independence_source is not None and s.independence_source not in catalog):
            raise ValueError('HISTORICAL_INDEPENDENCE_SOURCE_REQUIRED')
        if s.probability_source is not None and d1.probability_table(bundle) is None:raise ValueError('PROBABILITY_TABLE_NOT_PROVIDED')
    return dict(version=VERSION,entry=entry,state='STUDY_CANDIDATE_BOUND',study_candidate=deepcopy(raw),
        historical_materials_sha256=canonical_hash(historical_materials(bundle,entry)),core_called=False,scientific_approval=False)


def validate_envelope(bundle,entry,envelope):
    if bind_study(bundle,entry,envelope['study_candidate'])!=envelope:raise ValueError('STUDY_ENVELOPE_CHANGED_OR_STALE')


def target_request(bundle,entry,envelope):
    validate_envelope(bundle,entry,envelope)
    system,user=entries.make_request(bundle,entry);m=json.loads(user)
    m['output_schema']['properties'].pop('study');m['output_schema']['required']=['questions']
    m['bound_study_candidate']=deepcopy(envelope['study_candidate']['study'])
    m['historical_materials_sha256']=envelope['historical_materials_sha256']
    system+='''
本次只返回questions，不返回study。已绑定研究候选不能在目标阶段修改。
当前目标未决定邻居人数时保留neighbors=不明确；这不会删除历史协议已经说明的人数分类。
保留已经明确的评价对象、本人状态、安排规则；其余条件不能从历史事实或其他问题补齐。
研究绑定、原文引用都不是科学许可或识别证明。
'''
    return system,json.dumps(m,ensure_ascii=False)


def compose(bundle,entry,envelope,raw):
    validate_envelope(bundle,entry,envelope)
    if not isinstance(raw,dict) or set(raw)!={'questions'}:raise ValueError('TARGET_RESPONSE_ONLY')
    return dict(study=deepcopy(envelope['study_candidate']['study']),questions=deepcopy(raw['questions']))


def identify(bundle,entry,envelope,raw,packet=None,*,context=None,synthetic_protocol_selected=False):
    combined=compose(bundle,entry,envelope,raw)
    result=entries.identify(bundle,combined,entry,packet=packet,context=context,synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(study_envelope=deepcopy(envelope),target_candidate=deepcopy(raw),staged_version=VERSION)
    return result
