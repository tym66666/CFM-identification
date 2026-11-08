"""Reviewed mapping of an explicit local-effect background to native W.

This module never classifies prose or approves a condition. The existing local
effect model supports one fixed pretreatment study background; extra selection
or post-treatment conditions require another mathematical adapter.
"""
from copy import deepcopy
import json

MATCH_DECISION = 'fixed_conditioning_matches_reviewed_query'
SCOPE_DECISION = 'conditioning_is_only_fixed_pretreatment_study_background'
DECISIONS = (MATCH_DECISION, SCOPE_DECISION)
DESCRIPTION = (
    '逐项核对已审核目标中的conditioning_context仅指定同一处理前固定研究背景W，'
    '并与study.context以及该字段的原文来源完全表达同一研究背景。'
    '不能把额外子群筛选、处理后条件或跨背景平均折叠到study.context。'
    '若材料有这些额外条件，应在additional_restrictions保留完整条件和原文来源；'
    '若无法判断，应在unresolved保留问题，不能为了适配读取器删掉条件。'
    '读取和文字相等均不授予批准；固定背景范围与跨阶段一致性须分别独立审核。')


def has_explicit_context(context):
    value = (context or {}).get('conditioning_context')
    return isinstance(value, dict) and value.get('state') in ('STATED', 'INTERPRETED')


def clarify_request(request):
    result = deepcopy(request)
    body, end = json.JSONDecoder().raw_decode(result['user'])
    body['fixed_study_background_contract'] = dict(
        version='network-effect-fixed-background-1', instruction=DESCRIPTION,
        native_symbol='W', automatic_approval=False)
    result['user'] = json.dumps(body, ensure_ascii=False) + result['user'][end:]
    return result


def field_constraints(paths):
    return [dict(field_path=path, description=DESCRIPTION) for path in dict.fromkeys(paths)
            if path in ('/study', '/study/context', '/study/source_ids', '/additional_restrictions')
            or path.startswith('/additional_restrictions/')]


def review_item(context, study):
    return dict(version='network-effect-fixed-background-1', requirement=DESCRIPTION,
        reviewed_query=deepcopy(context),
        fact_conditioning=dict(context=study.context, source_ids=list(study.source_ids)),
        native_symbol='W', decisions=list(DECISIONS), is_approval=False)
