"""Versioned candidate envelope with optional, independently checked schedules.

The unmodified v0353 integration still owns actual Core calls and all approvals.
A typed envelope projection is deliberate protocol handling, not output repair.
"""
import json
from typing import Literal
from pydantic import model_validator
from cfm_id_llm.schemas import StrictModel
from cfm_id_llm.candidate_queries import CandidateProposalV011
from cfm_id_llm.orchestration_schemas import canonical_sha256
from .business_candidate_constraints import evaluate_with_candidates as previous
from .business_candidate_identifiers import SCHEMA_MARKER
from .witness_schedule import TwoWorldScheduleV037, inspect_two_worlds

VERSION = "business-candidate-v0.37"
MATH_MARKER = "\n\n已绑定的合成数学输入（不含参考答案或证明）：\n"


class CandidateEnvelopeV037(StrictModel):
    schema_version: Literal["candidate-envelope-v0.37"]
    candidate: CandidateProposalV011
    two_world_schedule: TwoWorldScheduleV037 | None

    @model_validator(mode="after")
    def witness_only_for_nonidentification(self):
        if self.two_world_schedule is not None and self.candidate.proposal.claimed_identification != "NOT_POINT":
            raise ValueError("Structured counterexample requires a NOT_POINT proposal")
        return self


SCHEDULE_RULES = """
本版本输出外层 CandidateEnvelopeV037：schema_version、candidate、two_world_schedule。
candidate 保留原候选合同；two_world_schedule 是可选的数学附件，不能冒充证书。
若主张 NOT_POINT，请尽量明确给出两个完整、确定性的潜在结果表，而不是只写“世界不同但观测相同”：
- node_order 严格等于数学输入的节点顺序。每个 outcomes 向量逐项对应该顺序。
- default_outcomes 定义此世界所有未在 overrides 中列出的二元分配的结果向量。
- 每条 override 指定一个完整 assignment 及该分配下的完整 outcomes。分配必须唯一。
- 数值是有理数字符串，例如整数或分数，不是 Python/SymPy 代码；本实验附件仅检查 [0,1] 内的停机小时构造。
- 两世界必须同时满足主判断使用的全部假设。对每个具有正概率的实际分配核对结果向量，不能只核对相同的随机化概率。
- 按给定 target_assignment 和 target_unit_weights 核对目标差异。反例中的数值是虚构数学构造，不是业务效果估计。
- candidate 中的反例文字必须描述同一附件，不能另写一个不相容的故事。
这里没有指定应该得出哪种判断，也没有指定两个世界的数值。附件不是必需的；如果这种表示不适用，写 null 并说明局限。
若无法构造有效反例，不要为填满字段而编造；UNDETERMINED 是允许的结果。
不因本版本的检查能力有限而改变原科学条件；未批准的无干扰、暴露均值充分性或其他结构限制仍不能默认使用。
"""


def schedule_prompt(system, user):
    head, tail = user.split(SCHEMA_MARKER, 1)
    old, end = json.JSONDecoder().raw_decode(tail)
    schema = CandidateEnvelopeV037.model_json_schema()
    schema["$defs"].update(old["$defs"])
    schema["$defs"]["CandidateProposalV011"] = {k: v for k, v in old.items() if k != "$defs"}
    schema["allOf"] = [{
        "if": {"properties": {"candidate": {"properties": {"proposal": {"properties": {
            "claimed_identification": {"enum": ["POINT", "PARTIAL", "UNDETERMINED"]}},
            "required": ["claimed_identification"]}}, "required": ["proposal"]}}, "required": ["candidate"]},
        "then": {"properties": {"two_world_schedule": {"type": "null"}}},
    }]
    old_rule = "输出严格符合 CandidateProposalV011 JSON Schema 的唯一 JSON 对象"
    assert old_rule in system
    system = system.replace(old_rule, "输出严格符合 CandidateEnvelopeV037 JSON Schema 的唯一 JSON 对象，原候选放在 candidate 字段")
    return system + SCHEDULE_RULES, head + SCHEMA_MARKER + json.dumps(
        schema, ensure_ascii=False, separators=(",", ":")) + tail[end:]


def evaluate_with_candidates(value, raw, packet, *, provider=None, **kwargs):
    envelopes, math_inputs, errors = {}, {}, []
    class ScheduleProvider:
        name = provider.name if provider else "NOT_CONFIGURED"
        def generate_json(self, *, system_prompt, user_prompt):
            payload, _ = json.JSONDecoder().raw_decode(user_prompt.split("\n", 1)[1])
            qid = payload["query_id_exact"]
            math = json.loads(user_prompt.split(MATH_MARKER, 1)[1])
            system, user = schedule_prompt(system_prompt, user_prompt)
            received = provider.generate_json(system_prompt=system, user_prompt=user)
            try:
                envelope = CandidateEnvelopeV037.model_validate(received)
            except Exception:
                errors.append(dict(query_id=qid, code="INVALID_V037_ENVELOPE"))
                raise ValueError("Invalid candidate envelope") from None
            envelopes[qid] = envelope.model_dump(mode="json")
            math_inputs[qid] = math
            # Original candidate is preserved as a typed projection. All prior
            # identity, A4/A5 and actual-Core gates still run on this object.
            return received["candidate"]
    out = previous(value, raw, packet, provider=ScheduleProvider() if provider else None, **kwargs)
    checks = {}
    for row in out["candidate_results"]:
        qid = row["query_id"]
        if qid not in envelopes:
            continue
        if row["status"] not in ("UNVERIFIED_CANDIDATE", "UNDETERMINED_UNVERIFIED"):
            checks[qid] = dict(status="BLOCKED_CANDIDATE_REJECTED", core_certified=False)
            continue
        env = envelopes[qid]
        checks[qid] = inspect_two_worlds(math_inputs[qid], env["candidate"], env["two_world_schedule"])
    out.update(version=VERSION, candidate_prompt_version=VERSION,
        candidate_envelopes=envelopes, candidate_envelope_errors=errors,
        schedule_diagnostics=checks, schedule_diagnostics_are_core_certificates=False,
        schedule_inspection_does_not_verify_candidate_text=True)
    return out

