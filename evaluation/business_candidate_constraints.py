"""Expose cross-field rules already enforced by candidate validators to the model."""
import json
from .business_candidate_base import evaluate_with_candidates as previous
from .business_candidate_prompt import ADDITIONAL_RULES
from .business_candidate_identifiers import specialize_schema, SCHEMA_MARKER, EXACT_RULES

VERSION = "business-candidate-v0.35.3"
CROSS_FIELD_RULES = """
输出一致性：
只选择一种主要判断与一个适用范围。NOT_POINT/UNDETERMINED的candidate_expression必须null；目标定义和备选研究思路写reasoning_steps或suggested_checks。
NOT_POINT必须给反例，POINT/PARTIAL不能同时给非识别反例。AS_REVIEWED的additional_requirements必须[]。
additional_requirements是使你当前选定的判断成立所需的新增条件，不是把所有能改变结论的备选研究路径混在一起。备选路径放suggested_checks，不要与当前假设集混用。
检查反例时必须对实际设计能产生的每一个分配核对两世界的观测结果律；只说两世界使用相同随机化设计不能证明结果的观测律相同。
"""


def _when(field, condition, then):
    return {"if": {"properties": {field: condition}, "required": [field]}, "then": then}


def complete_schema(user_prompt):
    prompt = specialize_schema(user_prompt)
    head, tail = prompt.split(SCHEMA_MARKER, 1)
    schema, end = json.JSONDecoder().raw_decode(tail)
    draft = schema["$defs"]["CandidateDraftV03"]
    draft["allOf"] = [
        _when("claimed_identification", {"enum": ["NOT_POINT", "UNDETERMINED"]},
              {"properties": {"candidate_expression": {"type": "null"}}}),
        _when("claimed_identification", {"const": "NOT_POINT"},
              {"properties": {"nonidentification_witness": {"type": "object"}},
               "required": ["nonidentification_witness"]}),
        _when("claimed_identification", {"enum": ["POINT", "PARTIAL", "UNDETERMINED"]},
              {"properties": {"nonidentification_witness": {"type": "null"}}}),
        _when("claimed_identification", {"enum": ["POINT", "PARTIAL"]},
              {"properties": {"candidate_expression": {"type": "string", "minLength": 1}},
               "required": ["candidate_expression"]}),
        _when("scope", {"const": "AS_REVIEWED"},
              {"properties": {"additional_requirements": {"maxItems": 0}}}),
        _when("scope", {"const": "IF_ADDITIONAL_REQUIREMENTS"},
              {"properties": {"additional_requirements": {"minItems": 1}},
               "required": ["additional_requirements"]}),
        {"if": {"properties": {"a4_used": {"properties": {"source": {"const": "ADDITIONAL_OPERATOR"}},
                                           "required": ["source"]}}, "required": ["a4_used"]},
         "then": {"properties": {"scope": {"const": "IF_ADDITIONAL_REQUIREMENTS"},
            "additional_requirements": {"contains": {"properties": {"kind": {"const": "A4_INFORMATION"}},
                                                     "required": ["kind"]}}},
                  "required": ["additional_requirements"]}},
        {"if": {"properties": {"a4_used": {"properties": {"source": {"const": "UNRESOLVED"}},
                                           "required": ["source"]},
                               "claimed_identification": {"enum": ["POINT", "PARTIAL", "NOT_POINT"]}},
                "required": ["a4_used", "claimed_identification"]},
         "then": {"properties": {"scope": {"const": "IF_ADDITIONAL_REQUIREMENTS"},
            "additional_requirements": {"contains": {"properties": {"kind": {"const": "A4_INFORMATION"}},
                                                     "required": ["kind"]}}},
                  "required": ["additional_requirements"]}},
    ]
    use = schema["$defs"]["CandidateA4UseV03"]
    use["allOf"].extend([
        _when("source", {"const": "UNRESOLVED"},
              {"properties": {"level": {"type": "null"}, "operator": {"type": "null"}}}),
        _when("source", {"enum": ["REVIEWED_OPERATOR", "ADDITIONAL_OPERATOR"]},
              {"properties": {"level": {"type": "string", "not": {"const": "UNRESOLVED"}},
                               "operator": {"type": "string", "minLength": 1}},
               "required": ["level", "operator"]}),
    ])
    return head + SCHEMA_MARKER + json.dumps(schema, ensure_ascii=False, separators=(",", ":")) + tail[end:]


def evaluate_with_candidates(value, raw, packet, *, provider=None, **kwargs):
    class ExplainedProvider:
        name = provider.name if provider else "NOT_CONFIGURED"

        def generate_json(self, *, system_prompt, user_prompt):
            return provider.generate_json(
                system_prompt=system_prompt + ADDITIONAL_RULES + EXACT_RULES + CROSS_FIELD_RULES,
                user_prompt=complete_schema(user_prompt))
    result = previous(value, raw, packet, provider=ExplainedProvider() if provider else None, **kwargs)
    result.update(version=VERSION, candidate_prompt_version=VERSION)
    return result
