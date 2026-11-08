"""Constrain exact A4 identifiers in the request schema, never relax validation."""
import json
from .business_candidate_base import evaluate_with_candidates as previous
from .business_candidate_prompt import ADDITIONAL_RULES

VERSION = "business-candidate-v0.35.2"
SCHEMA_MARKER = "\n\n候选输出的严格 JSON Schema：\n"
EXACT_RULES = """
字段填写补充：
- a4_used.operator是机器标识符，REVIEWED_OPERATOR时必须逐字复制scientific_scope.a4_sources中的operator，例如NODE_FULL_LAW；不能加冒号、空格解释或数学表达式。解释放reasoning_steps。
- finite_conditional_first_moments表示相关潜在结果在给定W时绝对一阶矩有限，包括目标涉及的潜在结果；它既不是只约束观测到的分配，也不连接不同分配下的潜在结果均值。
- NODE_FULL_LAW的观测联合律只按实际分配律定义；拥有完整的观测律并不等于知道零概率事件上的条件量。若需要干预律，那是另一个额外信息条件。
"""


def specialize_schema(user_prompt):
    head, tail = user_prompt.split(SCHEMA_MARKER, 1)
    payload, _ = json.JSONDecoder().raw_decode(head.split("\n", 1)[1])
    schema, end = json.JSONDecoder().raw_decode(tail)
    a4 = payload["scientific_scope"]["a4_sources"]
    pairs = sorted({(x["operator"], x["level"]) for x in a4 if x["level"] is not None})
    use = schema["$defs"]["CandidateA4UseV03"]
    use["allOf"] = [{
        "if": {"properties": {"source": {"const": "REVIEWED_OPERATOR"}}, "required": ["source"]},
        "then": {"anyOf": [
            {"properties": {"operator": {"const": op}, "level": {"const": level}},
             "required": ["operator", "level"]} for op, level in pairs
        ]} if pairs else {"not": {}}
    }]
    schema["$defs"]["CandidateDraftV03"]["properties"]["admitted_assumptions_used"]["items"] = {
        "type": "string", "enum": sorted(x["name"] for x in payload["scientific_scope"]["a5_licenses"])}
    return head + SCHEMA_MARKER + json.dumps(schema, ensure_ascii=False, separators=(",", ":")) + tail[end:]


def evaluate_with_candidates(value, raw, packet, *, provider=None, **kwargs):
    class ExplainedProvider:
        name = provider.name if provider else "NOT_CONFIGURED"

        def generate_json(self, *, system_prompt, user_prompt):
            return provider.generate_json(
                system_prompt=system_prompt + ADDITIONAL_RULES + EXACT_RULES,
                user_prompt=specialize_schema(user_prompt))
    result = previous(value, raw, packet, provider=ExplainedProvider() if provider else None, **kwargs)
    result.update(version=VERSION, candidate_prompt_version=VERSION)
    return result
