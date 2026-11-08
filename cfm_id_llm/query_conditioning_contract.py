"""Opt-in per-query conditioning, retained beside the legacy projection.

Owns one field from first read to review and explicit recheck. No prose
classification, target repair, scientific permission or mathematical solving.
"""
from copy import deepcopy
from dataclasses import asdict
from pydantic import ValidationError
from . import local_field_contract as previous
from .business_field_contract import Field
from .compact_inline_evidence_contract import MissingClaim
from .quality_formulator import A0QualityValidationError

CONTRACT = 'query-conditioning-1'
FIELD = 'conditioning_context'
RULE = Field(FIELD, '本问明确限定的条件及所指背景层，保留变量、取值或符号条件及其时点。',
    '不是普通场景说明、协变量清单、评价名单、政策使用名单或科学许可。固定背景与跨背景按分布平均是不同目标；'
    '前者写这里，后者写standardization_distribution，不从历史分布自动生成目标权重。'
    '只列协变量不等于指定目标条件。局部比较中保持不变的本人或同伴处理状态仍归comparison_request.shared_condition。'
    '处理后条件也照原意保留，不改称处理前条件。'
    '原文没有指定条件用UNKNOWN；明确尚未决定用MISSING及原因和引用。不要为了填字段创造条件。', section='semantics')
DESCRIPTION = RULE.meaning + ' ' + RULE.excludes
QUESTION = '本问希望在哪些已指定的条件下评价，还是希望跨背景评价？请说明条件、所指背景及时间；尚未决定可以保留。'
MATCH_DECISION = 'fixed_conditioning_matches_reviewed_query'
FACT_DESCRIPTION = (DESCRIPTION + ' 事实读取的conditioning须与已审核的逐问条件表达同一目标。'
    '仍引用本轮原文目录；A0定位信息不是事实来源。业务语义一致性由独立审核确认，不能按文字相似度自动批准。')
FACT_VERSION = previous.FACT_VERSION
BIND_POPULATION_INFORMATION = previous.BIND_POPULATION_INFORMATION
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
omitted_semantics = previous.omitted_semantics
review_semantics = previous.review_semantics
clarify_fact_request = previous.clarify_fact_request
fact_constraints = previous.fact_constraints


def review_definition(rule):
    return dict(asdict(RULE), wire_description=DESCRIPTION) if rule == RULE else previous.review_definition(rule)


def describe(schema):
    addition = previous.describe(schema)
    for name in ('CompactSemantics', 'OrderedLocalSemantics'):
        definition = schema['$defs'][name]
        definition['properties'][FIELD] = dict(description=DESCRIPTION, anyOf=[
            {'$ref': '#/$defs/OrderedLocalClaim'}, {'$ref': '#/$defs/MissingClaim'},
            dict(type='string', const='UNKNOWN')])
        definition['required'] = [*definition.get('required', []), FIELD]
    return addition


def system_prompt(**kwargs):
    return previous.system_prompt(**kwargs) + '\n\n每个query的semantics必须包含conditioning_context。' + DESCRIPTION


def _reject(index, code):
    raise A0QualityValidationError('Query conditioning rejected', code='A0_CONDITIONING_CONTEXT_REJECTED',
        diagnostics=dict(stage='query_conditioning', issues=[dict(code=code,
            path=['queries', index, 'semantics', FIELD])]))


def project(raw, catalog):
    from .compact_formulator import CompactClaim
    output = deepcopy(raw)
    if type(output) is not dict or type(output.get('queries')) is not list:
        return previous.project(output, catalog)
    refs = {r['ref'] for r in catalog}
    contexts = {}
    for index, query in enumerate(output['queries']):
        if type(query) is not dict or type(query.get('semantics')) is not dict:
            continue  # Existing section/type validation owns these failures.
        semantics = query['semantics']
        if FIELD not in semantics:
            _reject(index, 'missing')
        value = semantics.pop(FIELD)
        if value != 'UNKNOWN':
            try:
                if type(value) is not dict:
                    raise ValueError('claim required')
                if value.get('state') == 'MISSING':
                    claim = MissingClaim.model_validate(value)
                    if not claim.reason.strip():
                        raise ValueError('empty reason')
                else:
                    claim = CompactClaim.model_validate(value)
                    if claim.state == 'NOT_APPLICABLE' or (claim.value is not None and not claim.value.strip()):
                        raise ValueError('invalid conditioning state')
                if len(set(claim.refs)) != len(claim.refs) or any(r not in refs for r in claim.refs):
                    _reject(index, 'CONDITIONING_REFERENCES_INVALID')
            except A0QualityValidationError:
                raise
            except (ValidationError, ValueError, TypeError):
                _reject(index, 'CONDITIONING_CLAIM_INVALID')
        contexts[f'q{index+1}'] = value
    projected, details = previous.project(output, catalog)
    # Legacy canonical draft intentionally has no new field. Every new-profile
    # consumer receives this explicit, review-bound extension; raw is retained.
    details['query_conditioning'] = dict(contract=CONTRACT, queries=contexts, is_approval=False)
    return projected, details


def state(value):
    return value.get('state', 'UNKNOWN') if type(value) is dict else value


def apply_gate(gate, details):
    previous.apply_gate(gate, details)
    gate['query_conditioning'] = deepcopy(details['query_conditioning'])
    for qid, value in details['query_conditioning']['queries'].items():
        gate['slot_states'][qid][FIELD] = state(value)
        if state(value) == 'MISSING':
            gate['proposed_business_questions'].append(dict(query_id=qid, field=FIELD,
                question=QUESTION, status='VERIFY_MISSING_IN_SOURCE_BEFORE_ASKING'))
            if not gate['issues']:
                gate['status'] = 'BUSINESS_CLARIFICATION_REQUIRED'


def review_items(raw, query_id):
    yield from previous.review_items(raw, query_id)
    value = raw['queries'][int(query_id[1:])-1]['semantics'][FIELD]
    yield RULE, f'queries.{query_id}.semantics.{FIELD}', value, state(value)


def recheck_field_roles(paths, **kwargs):
    rows = previous.recheck_field_roles(paths, **kwargs)
    for path in dict.fromkeys(paths):
        parts = path.split('/')[1:]
        if len(parts) >= 4 and parts[0] == 'queries' and parts[2:4] == ['semantics', FIELD]:
            rows = [r for r in rows if r['field_path'] != path]
            rows.append(dict(field_path=path, field_role=DESCRIPTION))
    return rows


def fact_focus(raw_query, *, query_id, binding):
    focus = previous.fact_focus(raw_query, query_id=query_id, binding=binding)
    focus['reviewed_business_roles']['contract'] = CONTRACT
    return focus


def target_context(raw_query, *, query_id):
    """No value extraction from goal, covariates or another field."""
    return dict(contract=CONTRACT, query_id=query_id,
        conditioning_context=deepcopy(raw_query['semantics'][FIELD]),
        standardization_distribution=deepcopy(raw_query['semantics'].get('standardization_distribution', 'UNKNOWN')),
        authority='REVIEWED_TARGET_CONTEXT_NOT_SOURCE_OR_SCIENTIFIC_PERMISSION')


def admission(context, reader_id):
    """Typed scope guard, never interpretation of a claim's prose."""
    value = context['conditioning_context']
    if reader_id in ('NETWORK_RANDOMIZED_ARM_FACTS','NETWORK_FINITE_POLICY_FACTS','NETWORK_OBSERVATIONAL_EFFECT_FACTS'):
        # These contracts carry their own explicit averaging target, law and
        # background. The fact and source reviews must compare all three.
        if state(value)=='MISSING' or state(context['standardization_distribution'])=='MISSING':
            return 'NEEDS_INPUT','TARGET_CONTEXT_OR_AVERAGING_UNRESOLVED'
    elif reader_id == 'NETWORK_OBSERVATIONAL_POLICY_FACTS':
        if state(context['standardization_distribution']) in ('STATED', 'INTERPRETED'):
            return 'ADAPTER_NOT_CONNECTED', 'STANDARDIZED_OBSERVATIONAL_TARGET_NOT_CONNECTED'
        if state(context['standardization_distribution']) == 'MISSING':
            return 'NEEDS_INPUT', 'TARGET_STANDARDIZATION_UNRESOLVED'
        if state(value) not in ('STATED', 'INTERPRETED'):
            return 'NEEDS_INPUT', 'FIXED_CONDITIONING_TARGET_NOT_ESTABLISHED'
    elif reader_id in ('NETWORK_POLICY_CONTRAST_FACTS','NETWORK_FIXED_POLICY_FACTS'):
        if state(context['standardization_distribution']) in ('STATED', 'INTERPRETED'):
            return 'ADAPTER_NOT_CONNECTED', 'STANDARDIZED_CONTRAST_TARGET_NOT_CONNECTED'
        if state(context['standardization_distribution']) == 'MISSING':
            return 'NEEDS_INPUT', 'TARGET_STANDARDIZATION_UNRESOLVED'
        if state(value) == 'MISSING':
            return 'NEEDS_INPUT', 'FIXED_CONDITIONING_TARGET_NOT_ESTABLISHED'
        # The contrast adapter requires separate target and conditional-model
        # reviews before compiling either endpoint. Presence is not approval.
    elif reader_id == 'NETWORK_RANDOMIZED_EFFECT_FACTS':
        # This family carries fixed study background W through its target and
        # requires a separate scope/match review before native compilation.
        if state(value) == 'MISSING':
            return 'NEEDS_INPUT', 'FIXED_CONDITIONING_TARGET_NOT_ESTABLISHED'
    elif state(value) in ('STATED', 'INTERPRETED'):
        return 'ADAPTER_NOT_CONNECTED', 'CONDITIONED_TARGET_NOT_CONNECTED_TO_SELECTED_READER'
    return None


def clarify_conditioning_request(request):
    """One field description shared by initial fact request and its recheck."""
    import json
    result = deepcopy(request)
    body = json.loads(result['user'])
    body['output_schema']['properties']['conditioning']['description'] = FACT_DESCRIPTION
    result['user'] = json.dumps(body, ensure_ascii=False)
    return result


def conditioning_constraints(paths):
    return [dict(field_path=p, description=FACT_DESCRIPTION) for p in dict.fromkeys(paths)
            if p == '/conditioning' or p.startswith('/conditioning/')]


CONTRAST_DESCRIPTION = (
    '核对事实读取 study.context 中的固定背景与本问已审核条件含义一致；'
    '允许同时保留评价期间，但不能用仅有的期间或“两端背景相同”代替具体条件。'
    'study.source_ids 必须覆盖该背景。此项只审核目标与来源，不批准条件分配律、总体信息或科学假设。')


def preserve_contrast_request(request):
    """Use the existing study/context wire; do not add a duplicate model field."""
    return deepcopy(request)


def contrast_conditioning_constraints(paths):
    return [dict(field_path=p, description=CONTRAST_DESCRIPTION) for p in dict.fromkeys(paths)
            if p in ('/study', '/study/context', '/study/source_ids') or p.startswith('/study/source_ids/')]
