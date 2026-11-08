"""One field owner for ordered-mean statements, without changing the wire.

The old request is immutable. This explicit revision replaces conflicting
instructions; it never deduplicates a model reply or grants scientific review.
"""
from copy import deepcopy
import json
from .network_remainder_contract import REMAINDER as OLD_REMAINDER
from .network_outcome_contract import COUPLING_DECLARATION as OLD_COUPLING

PROFILE = 'network-source-selections-mean-orders-2'
REMAINDER = (
    'additional_restrictions仅保留专门字段未能完整表达的额外信息、关系或方法要求。'
    '均值顺序的对象、轴、方向、层级、范围和采用态度统一放mean_order_model.order_reading；'
    '已在那里完整表达的同一顺序不再抄到本列表。总体量放information，界限放bounded_model。'
    '同段仍有未表达的跨对象等式、其他关系、总体区间或额外信息时，只保留这部分及其范围和引用；'
    '不能把它与已表达的顺序一起删掉。无法确认是否完整表达时保留原意并在unresolved说明疑点。'
    '没有剩余内容才用[]；程序不作语义去重，也不批准科学条件。')
COUPLING = OLD_COUPLING.replace(
    '额外关系完整保留在additional_restrictions',
    '关系本身保留在其专门字段：已表达的均值顺序在mean_order_model.order_reading，'
    '仅未表达的其他关系在additional_restrictions')
CONTEXT = (
    '记录结果适用的研究时期与明确限定的研究背景；此字段会进入数学目标的context，'
    '不是业务故事摘要。保留原文明示的时期和固定背景，不混入合作动机、服务介绍或解释识别方法的文字。'
    '实际填写内容仍由study.source_ids完整支持；未说明的内容保持null，不自行补时期。')

ROLES = {
    '/additional_restrictions': REMAINDER,
    '/bounded_model/no_additional_coupling_constraints': COUPLING,
    '/study/context': CONTEXT,
}


def apply(request):
    result = deepcopy(request)
    old = '关系同时完整保留在additional_restrictions。'
    new = ('关系由对应专门字段完整保留；已表达的均值顺序只放mean_order_model.order_reading，'
           '尚未表达的其他关系放additional_restrictions。')
    for before, after in ((old, new), (OLD_REMAINDER, REMAINDER)):
        if result['system'].count(before) != 1:
            raise ValueError('MEAN_ORDER_BASE_FIELD_RULE_CHANGED')
        result['system'] = result['system'].replace(before, after)
    body = json.loads(result['user'])
    schema = body['output_schema']
    schema['properties']['additional_restrictions']['description'] = REMAINDER
    schema['$defs']['BoundedModel']['properties']['no_additional_coupling_constraints']['description'] = COUPLING
    schema['$defs']['Study']['properties']['context']['description'] = CONTEXT
    body['field_ownership_contract'] = dict(version=PROFILE, semantic_deduplication=False,
        fields={p: dict(description=d) for p, d in ROLES.items()})
    result['user'] = json.dumps(body, ensure_ascii=False)
    return result


def field_constraints(paths, *, request):
    body = json.JSONDecoder().raw_decode(request['user'])[0]
    contract = body.get('field_ownership_contract', {})
    if contract.get('version') != PROFILE:
        return []  # The same profile's single-policy reader has no order model.
    return [dict(field_path=p, **deepcopy(row)) for p, row in contract['fields'].items()
            if any(not q or p == q or p.startswith(q+'/') or q.startswith(p+'/') for q in paths)]


def overlap_checks(candidate):
    """Locate possible overlaps for source review, never infer equivalence."""
    model = candidate.get('mean_order_model') or {}
    claims = model.get('order_reading', {}).get('claims', [])
    result = {}
    for i, note in enumerate(candidate.get('additional_restrictions', [])):
        paths = [f'/mean_order_model/order_reading/claims/{j}' for j, claim in enumerate(claims)
                 if set(note.get('source_ids', [])) & set(claim.get('source_ids', []))]
        if paths:
            result[f'/additional_restrictions/{i}'] = dict(
                code='SHARED_SOURCE_REQUIRES_FIELD_OWNERSHIP_REVIEW', related_fields=paths,
                shared_source_is_not_duplicate_proof=True, candidate_modified=False,
                instruction='核对是已表达顺序的重复，还是同一来源中的不同额外关系；后者必须保留。')
    return result
