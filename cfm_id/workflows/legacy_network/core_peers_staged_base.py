"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.core_peers_base as core
import cfm_id.workflows.legacy_network.core_peers as reading
from cfm_id.serialization import canonical_hash


VERSION='business-core-peers-staged-v0.52'


def historical_materials(bundle):
    _,user=reading.make_request(bundle);m=json.loads(user)
    excluded={bundle['active_goal_document'],'business_question.md'}
    m['documents']={k:v for k,v in m['documents'].items() if k not in excluded}
    m['source_catalog']={k:v for k,v in m['source_catalog'].items() if k.split(':L')[0] in m['documents']}
    for k in ('output_schema','question_slots','active_goal_document','target_statement_sources'):
        m.pop(k,None)
    return m


def bind_study(bundle,raw):
    if not isinstance(raw,dict) or set(raw)!={'study'}:
        raise ValueError('STUDY_RESPONSE_ONLY')
    s=core.Study.model_validate(raw['study']);catalog=historical_materials(bundle)['source_catalog']
    if not s.design_sources or any(x not in catalog for x in s.design_sources):
        raise ValueError('HISTORICAL_STUDY_SOURCE_REQUIRED')
    for value,source in ((s.exposure,s.exposure_source),(s.declared_independent,s.independence_source)):
        if (value is None)!=(source is None) or (source is not None and source not in catalog):
            raise ValueError('HISTORICAL_STUDY_SOURCE_REQUIRED')
    rates=core.d1.probability_table(bundle);peers=core.core_partner_table(bundle)
    if s.probability_source is not None and rates is None:raise ValueError('PROBABILITY_TABLE_NOT_PROVIDED')
    if s.core_partner_source is not None and (s.exposure!=core.E3 or peers is None):raise ValueError('CORE_PARTNER_SOURCE_NOT_APPLICABLE')
    complete=(s.design=='逐单位抽签' and s.declared_independent is True and rates is not None and s.probability_source is not None
              and s.exposure is not None and (s.exposure!=core.E3 or s.core_partner_source is not None))
    return dict(version=VERSION,state='TARGET_INPUT_REQUIRED' if complete else 'NEEDS_INPUT',core_called=False,
        study_candidate=deepcopy(raw),historical_materials_sha256=canonical_hash(historical_materials(bundle)),
        scientific_approval=False)


def validate_envelope(bundle,envelope):
    expected=bind_study(bundle,envelope['study_candidate'])
    if expected!=envelope:raise ValueError('STUDY_ENVELOPE_CHANGED_OR_STALE')
    if expected['state']!='TARGET_INPUT_REQUIRED':raise ValueError('COMPLETE_STUDY_REQUIRED')
    return expected


def target_request(bundle,envelope):
    validate_envelope(bundle,envelope)
    system,user=reading.make_request(bundle);m=json.loads(user);schema=m['output_schema']
    schema['properties'].pop('study');schema['required']=['questions']
    m['bound_study_candidate']=envelope['study_candidate']['study']
    m['historical_materials_sha256']=envelope['historical_materials_sha256']
    system+='''
本次只返回questions，不返回study。研究设计候选已经单独读取并绑定在bound_study_candidate中，不能在目标读取阶段修改。
研究协议的分析分组与当前想问的同伴范围是两件事：当前目标尚未决定范围时peer_scope=不明确，不改变历史研究分组。
历史研究分组已知不代表当前目标范围已知；目标写明全部邻居时如实保留全部邻居，不改成研究的核心伙伴范围。
该绑定只保持研究候选与材料的一致性，不是科学许可或识别证明。'''
    return system,json.dumps(m,ensure_ascii=False)


def compose_reading(bundle,envelope,target_raw):
    validate_envelope(bundle,envelope)
    if not isinstance(target_raw,dict) or set(target_raw)!={'questions'}:
        raise ValueError('TARGET_RESPONSE_ONLY')
    return dict(study=deepcopy(envelope['study_candidate']['study']),questions=deepcopy(target_raw['questions']))
