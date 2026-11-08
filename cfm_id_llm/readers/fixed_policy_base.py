"""Fixed-arrangement reading: intent is independent of coordinate completeness.

Only public text and a roster enter the prompt. Scientific sources, licenses,
route choices and approval records remain outside the model's authority.
"""
from copy import deepcopy
from fractions import Fraction
import json
from typing import Literal

from pydantic import StrictInt, model_validator
from cfm_id_llm.schemas import StrictModel


class Intent(StrictModel):
    kind: Literal['比较', '水平', '选最优', '不明确']
    quote: str


class Conditions(StrictModel):
    first: dict[str, StrictInt | None] | None
    second: dict[str, StrictInt | None] | None
    population: list[str] | None
    aggregation: Literal['等权平均', '不明确', '其他']

    @model_validator(mode='after')
    def binary(self):
        for side in (self.first, self.second):
            if side is not None and any(v not in (0, 1, None) for v in side.values()):
                raise ValueError('BINARY_OR_UNKNOWN_REQUIRED')
        return self


class Reading(StrictModel):
    intents: dict[str, Intent]
    questions: dict[str, Conditions]


def _nodes(bundle):
    nodes = bundle['node_order']
    if (not isinstance(nodes, list) or not nodes or len(set(nodes)) != len(nodes)
            or any(not isinstance(n, str) or not n for n in nodes)):
        raise ValueError('EXPLICIT_PUBLIC_ROSTER_REQUIRED')
    return nodes


def make_request(bundle, envelope=None):
    if envelope is not None:
        raise ValueError('FIXED_POLICY_HAS_NO_STAGED_READING')
    nodes = _nodes(bundle)
    schema = Reading.model_json_schema()
    for field, definition in (('intents', 'Intent'), ('questions', 'Conditions')):
        schema['properties'][field] = dict(type='object', additionalProperties=False,
            required=list(bundle['question_slots']), properties={
                q: {'$ref': '#/$defs/' + definition} for q in bundle['question_slots']})
    system = '''读取自然语言业务目标，严格返回给定JSON结构。不要识别、证明或批准因果假设。
先判断intents中的kind，再填写questions中的条件。比较=问影响、改变或两种情形的差；水平=问一个安排下的均值；选最优=选最好安排；不明确=连问题类型也未确定。条件缺失不改变比较/水平意图。quote完整照抄对应question_slots。
本入口读取完整的指定安排，名册node_order只用于对象编号。first/second将每个名册对象映射为1（使用）、0（不使用）或null（尚未说明）。明确全员使用时可逐个展开；只提到一人时，其余填null，不能默认为0或沿历史抽签。比较的两端均保留对象，未知坐标填null；水平的second必须null。不要把“有没有影响”自动补成全员使用减全员不用。
population只列明确评价的对象；明确全体可展开名册，不明确则null。aggregation只有明确每人同样权重的平均才填等权平均。不得从历史分组、暴露定义或研究设计补目标坐标。历史材料不是A4总体信息许可，也不是A5科学假设。
若问题为比较但两端已完整，本入口仍只保留阅读结果；不会把它改成单一水平。只输出intents和questions，禁止增加审核、路线或识别状态。
'''
    return system, json.dumps(dict(documents=bundle['documents'], node_order=nodes,
        question_slots=bundle['question_slots'], output_schema=schema), ensure_ascii=False)


def project(bundle, raw):
    nodes = _nodes(bundle)
    reading = Reading.model_validate(raw)
    qids = set(bundle['question_slots'])
    if set(reading.intents) != qids or set(reading.questions) != qids:
        raise ValueError('EXACT_QUESTION_COVERAGE_REQUIRED')
    receipts, targets = {}, {}
    for qid in bundle['question_slots']:
        intent, c = reading.intents[qid], reading.questions[qid]
        if intent.quote != bundle['question_slots'][qid]:
            raise ValueError('CURRENT_QUESTION_QUOTE_REQUIRED')
        sides = ('first', 'second') if intent.kind == '比较' else ('first',) if intent.kind == '水平' else ()
        missing = []
        for side in sides:
            values = getattr(c, side)
            if values is None or set(values) != set(nodes):
                raise ValueError('PARTIAL_ARRANGEMENT_OBJECT_REQUIRED')
            missing.extend(side + '.' + n for n in nodes if values[n] is None)
        for values in (c.first, c.second):
            if values is not None and set(values) != set(nodes):
                raise ValueError('ARRANGEMENT_ROSTER_MISMATCH')
        if intent.kind == '水平' and c.second is not None:
            raise ValueError('LEVEL_MUST_NOT_INVENT_BASELINE')
        if c.population is None or not c.population:
            missing.append('population')
        elif len(set(c.population)) != len(c.population) or not set(c.population).issubset(nodes):
            raise ValueError('POPULATION_ROSTER_MISMATCH')
        if c.aggregation == '不明确':
            missing.append('aggregation')
        assessed = intent.kind in ('比较', '水平')
        receipts[qid] = dict(intent=intent.model_dump(), missing_conditions=missing,
            coordinate_status='NOT_ASSESSED' if not assessed else 'INCOMPLETE' if missing else 'COMPLETE_REQUIRES_REVIEW',
            scientific_approval=False)
        if intent.kind == '水平' and not missing and c.aggregation == '等权平均':
            targets[qid] = dict(classification='FIXED_POLICY', node_order=nodes,
                assignment=[c.first[n] for n in nodes], unit_weights=[
                    str(Fraction(1, len(c.population))) if n in c.population else '0' for n in nodes])
    return targets, receipts


def preview(bundle, raw):
    out = dict(version='business-fixed-intent-v0.57', state='READING_REVIEW_REQUIRED',
        reading_candidate=deepcopy(raw), core_called=False, candidate_model_calls=0,
        estimation_called=False, policy_called=False, production_admission=False,
        estimation_handoff_allowed=False, query_views=[], intent_condition_review={})
    try:
        targets, receipts = project(bundle, raw)
    except (ValueError, TypeError, KeyError):
        out['reason_code'] = 'INVALID_INTENT_OR_CONDITIONS'
        return out
    out.update(proposed_targets=targets, intent_condition_review=receipts)
    for qid, r in receipts.items():
        state = ('REVIEW_REQUIRED' if qid in targets else 'NEEDS_INPUT'
                 if r['missing_conditions'] or r['intent']['kind'] == '不明确' else 'UNSUPPORTED')
        out['query_views'].append(dict(query_id=qid, state=state, core_called=False))
    states = {r['state'] for r in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    return out
