"""D3/D4 language adapter to existing R1a/R1b, with explicit synthetic science.

No new theorem, support calculator, certificate format, or production approval.
The prior D1/D2 experiment stays frozen and independently replayable.
"""
from fractions import Fraction
import json
from typing import Literal
from pydantic import Field, StrictBool, StrictInt, ValidationError

from .business_core_pilot_base import (
    Closed, Target, State, canonical_hash, target_coordinates, _target_blocker, _network)
from .business_reading_base import Question, Complete, Conditional, _selection, question_slots
from .business_reading_provenance import anchor_scenarios
from .business_reading import coordinate_form, output_schema as previous_schema, SYSTEM as PREVIOUS_SYSTEM
from .business_core_source_refs import source_catalog

VERSION = "business-groups-v0.22.0"
SYSTEM = PREVIOUS_SYSTEM.replace(
    "只有study的三个来源、population_source、remaining_source需要选择句号编号。",
    "只有study的四个来源字段、population_source、remaining_source需要选择原句编号。"
).replace(
    "unresolved只记录目标未说清的事项；总体信息是否真实、数值如何计算、数据如何交付由独立环节处理。",
    "目标坐标未说清时使用相应字段的“不明确”或null，不输出unresolved字段。"
) + """
本次研究设计只读分组抽签：
“组内固定名额”指两组各自在组内均匀抽取给定人数；不是整个公司统一抽固定人数。
“整组开关”指每组抽一次，抽中全组采用，没抽中全组不采用；不能当成组内各人独立抽签。
groups按原文列出各组完整成员；quotas或probabilities必须与groups逐组对应，不能从实际采用名单倒推。
draws_independent只表示各组抽签彼此独立，必须由原文明确说明；未说明填null，不等于组间没有网络联系。
整组开关的各组概率未给全时，在对应位置填null，不默认1/2；组内固定名额的probabilities填null。
两组固定名额的quotas填两个名额，整组开关的quotas填null。未明确的分组或设计也不得补齐。
题目可以要求在旧试验中抽不出的新安排；仍准确提取该安排，能否识别由数学模块判断。
"""


class GroupReading(Closed):
    units: StrictInt = Field(ge=3, le=80, description="研究对象数量，编号统一使用01、02、…")
    graph: Literal["ring", "star"] = Field(description="环形ring；中心连接所有外围且外围不互连为star")
    center: str | None = Field(description="星形的中心编号；环形填null")
    design: Literal["组内固定名额", "整组开关", "不明确"]
    groups: list[list[str]] | None
    quotas: list[StrictInt | None] | None
    probabilities: list[str | None] | None
    draws_independent: StrictBool | None
    exposure: Literal["strict_majority", "exact_treated_neighbor_count", "any_treated_neighbor"]
    outcome: str = Field(description="逐字使用业务题中的结果变量名称，不补时间或单位")
    graph_source: str
    partition_source: str | None
    design_source: str | None
    exposure_source: str


class NumericDraft(Closed):
    study: GroupReading
    targets: list[Target] = Field(min_length=1, max_length=6)


def output_schema(question):
    schema = previous_schema(question)
    study = GroupReading.model_json_schema()
    ids = list(source_catalog(question))
    for name in ("graph_source", "partition_source", "design_source", "exposure_source"):
        item = {"type": "string", "enum": ids}
        study["properties"][name] = ({"anyOf": [item, {"type": "null"}]}
                                    if name in ("partition_source", "design_source") else item)
    schema["properties"]["study"] = study
    return schema


def make_request(question):
    if not question_slots(question):
        raise ValueError("EXPLICIT_QUESTION_SENTENCE_REQUIRED")
    return SYSTEM, json.dumps(dict(business_question=question, source_catalog=source_catalog(question),
        question_slots=question_slots(question), output_schema=output_schema(question)), ensure_ascii=False)


def study_coordinates(reading):
    """Exact reordering of coupled group records; never impute a missing rate."""
    d = reading.model_dump(exclude={"graph_source", "partition_source", "design_source", "exposure_source"})
    if d["probabilities"] is not None:
        try:
            d["probabilities"] = [None if p is None else str(Fraction(p)) for p in d["probabilities"]]
        except (ValueError, ZeroDivisionError):
            raise ValueError("INVALID_PROBABILITY_FORMAT") from None
    if d["groups"] is not None:
        n = len(d["groups"])
        for field in ("quotas", "probabilities"):
            if d[field] is not None and len(d[field]) != n:
                raise ValueError("GROUP_PARAMETER_LENGTH_MISMATCH")
        order = sorted(range(n), key=lambda i: tuple(sorted(d["groups"][i])))
        d["groups"] = [sorted(d["groups"][i]) for i in order]
        for field in ("quotas", "probabilities"):
            if d[field] is not None:
                d[field] = [d[field][i] for i in order]
    return d


def study_blocker(d, reading):
    if d["design"] == "不明确" or d["groups"] is None or not reading.partition_source or not reading.design_source:
        return "NEEDS_INPUT", "GROUP_DESIGN_DETAILS_MISSING"
    if d["draws_independent"] is not True:
        return "NEEDS_INPUT", "INDEPENDENT_GROUP_DRAWS_NOT_DECLARED"
    expected = {f"{i:02d}" for i in range(1, d["units"] + 1)}
    members = [n for g in d["groups"] for n in g]
    if not d["groups"] or any(not g for g in d["groups"]) or len(members) != len(set(members)) or set(members) != expected:
        return "REJECTED", "PARTITION_MUST_COVER_EACH_UNIT_ONCE"
    if (d["graph"] == "ring" and d["center"] is not None) or (d["graph"] == "star" and d["center"] not in expected):
        return "REJECTED", "GRAPH_CENTER_INVALID"
    if d["design"] == "组内固定名额":
        if len(d["groups"]) != 2:
            return "UNSUPPORTED", "THIS_ADAPTER_REQUIRES_TWO_QUOTA_GROUPS"
        if d["probabilities"] is not None:
            return "REJECTED", "QUOTA_DESIGN_HAS_BERNOULLI_PARAMETERS"
        if d["quotas"] is None or any(q is None for q in d["quotas"]):
            return "NEEDS_INPUT", "GROUP_QUOTAS_MISSING"
        if any(q < 0 or q > len(g) for q, g in zip(d["quotas"], d["groups"])):
            return "REJECTED", "GROUP_QUOTA_OUT_OF_RANGE"
    else:
        if d["quotas"] is not None:
            return "REJECTED", "CLUSTER_DESIGN_HAS_FIXED_QUOTAS"
        if d["probabilities"] is None or any(p is None for p in d["probabilities"]):
            return "NEEDS_INPUT", "CLUSTER_PROBABILITIES_MISSING"
        if any(not 0 <= Fraction(p) <= 1 for p in d["probabilities"]):
            return "REJECTED", "CLUSTER_PROBABILITY_OUT_OF_RANGE"
    return None


def project(question, raw):
    expanded = anchor_scenarios(question, coordinate_form(raw))
    reading = GroupReading.model_validate(expanded["study"])
    sources = source_catalog(question)
    for name in ("graph_source", "partition_source", "design_source", "exposure_source"):
        ref = getattr(reading, name)
        if ref is not None and ref not in sources:
            raise ValueError("SOURCE_REFERENCE_NOT_FOUND")
    def quote(ref):
        if ref is not None and ref not in sources:
            raise ValueError("SOURCE_REFERENCE_NOT_FOUND")
        return None if ref is None else sources[ref]
    def state(world):
        if world.own == "不明确" or world.neighbors == "不明确":
            return None
        if reading.exposure == "exact_treated_neighbor_count":
            if world.neighbors != "恰好人数" or type(world.neighbor_count) is not int or world.neighbor_count < 0:
                raise ValueError("PEER_RELATION_CONFLICTS_WITH_EXPOSURE")
            peers = world.neighbor_count
        else:
            values = {"strict_majority": {"超过一半": 1, "至多一半": 0},
                      "any_treated_neighbor": {"至少一个": 1, "一个也没有": 0}}[reading.exposure]
            if world.neighbor_count is not None or world.neighbors not in values:
                raise ValueError("PEER_RELATION_CONFLICTS_WITH_EXPOSURE")
            peers = values[world.neighbors]
        return State(own=1 if world.own == "开通" else 0, peers=peers, quote=quote(world.source))
    targets = []
    changes = []
    for sid in question_slots(question):
        q = Question.model_validate(expanded["questions"][sid])
        pop = _selection(q.population, reading.units, population=True)
        agg = {"等权平均": "equal_mean", "单个": "single", "不明确": None}[q.aggregation]
        if pop and len(pop) == 1 and agg == "equal_mean":
            agg = "single"
            changes.append(dict(question=sid, equivalence="equal_mean_over_explicit_singleton"))
        t = dict(question_quote=sources[sid], kind="unclear", nodes=pop, aggregation=agg,
                 population_quote=quote(q.population_source), situation=None, reference=None,
                 remaining=None, remaining_quote=None, treated_nodes=None, plan_quote=None, unresolved=[])
        if q.operation in ("选最优", "不明确"):
            if q.first is not None or q.second is not None:
                raise ValueError("UNRESOLVED_OR_OPTIMIZATION_WITH_FIXED_ANSWER")
            t["kind"] = "optimization" if q.operation == "选最优" else "unclear"
        elif q.first is None:
            if q.second is not None:
                raise ValueError("SECOND_WITHOUT_FIRST")
            t["unresolved"].append("FIRST_SCENARIO_MISSING")
        elif q.operation == "水平" and q.second is not None:
            raise ValueError("LEVEL_WITH_EXTRA_SCENARIO")
        elif q.operation == "差值" and q.second is None:
            t["unresolved"].append("SECOND_SCENARIO_MISSING")
        elif isinstance(q.first, Complete):
            if q.second is not None:
                raise ValueError("COMPLETE_ARRANGEMENT_CONTRAST_ADAPTER_UNSUPPORTED")
            t.update(kind="fixed_plan", treated_nodes=_selection(q.first.treated, reading.units),
                     plan_quote=quote(q.first.source))
        elif q.second is not None and not isinstance(q.second, Conditional):
            raise ValueError("MIXED_SCENARIO_CONTRAST_ADAPTER_UNSUPPORTED")
        else:
            t["kind"] = "comparison" if q.operation == "差值" else "arm"
            remaining = []
            for key, w in (("situation", q.first), ("reference", q.second)):
                if w is not None:
                    t[key] = state(w)
                    if t[key] is None:
                        t["unresolved"].append("LOCAL_CONDITION_INCOMPLETE")
                    remaining.append(quote(w.remaining_source))
            if remaining and all(remaining):
                t.update(remaining="original_randomization", remaining_quote=remaining[0])
        targets.append(Target.model_validate(t))
    return NumericDraft(study=reading, targets=targets).model_dump(), changes


from cfm_id.workflows.legacy_network.group_adapter import assignment


from cfm_id.workflows.legacy_network.group_adapter import _arm


def compile_inquiry(d, target, science):
    from pfn_pipeline.identification_business import ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21
    net = _network(d)
    nodes = tuple(net.node_ids)
    if target.kind == "arm":
        return ArmInquiryV21(_arm(d, net, target.nodes[0], target.situation.own, target.situation.peers))
    if target.kind == "comparison":
        from pfn_pipeline.identification_batch import identify_randomized_network_batch
        from pfn_pipeline.identification_composition import EffectQueryV18
        from pfn_pipeline.identification_a4_shadow import declare_a4_source
        s, r = target.situation, target.reference
        if (s.own, r.own) == (1, 0):
            kind = "DIRECT" if s.peers == r.peers else "TOTAL"
        elif s.own == r.own and s.peers != r.peers:
            kind = "SPILLOVER"
        else:
            raise ValueError("CONTRAST_ORIENTATION_ADAPTER_UNSUPPORTED")
        batch = identify_randomized_network_batch(_arm(d, net, target.nodes[0], s.own, s.peers))
        cells = tuple((n, a, e) for n in nodes for a in (0, 1) for e in batch.exposure_states
                      if batch.cell(n, a, e)["status"] == "POINT")
        src = declare_a4_source(batch.template, source_id="SYNTHETIC_GROUP_ARM_MEANS",
            operator="NODE_ARM_MEANS", provenance=science["population_information"], admission="ADMITTED",
            availability="SYMBOLIC_POPULATION_OPERATOR", regime="experimental",
            outcome_nodes=nodes, node_order=nodes, arm_cells=cells)
        query = EffectQueryV18(kind, tuple((n, "1") for n in target.nodes), r.peers, s.peers,
            spillover_own_treatment=s.own, cohort_authority="TRUSTED_FIXTURE", cohort_evidence=target.population_quote)
        return EffectsInquiryV21(batch, src, (query,))
    from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context, declare_network_a4_source
    from pfn_pipeline._internal.identification.schemas import Assumption
    from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
    study = declare_network_study(network_id=net.network_id, node_order=nodes,
        undirected_edges=tuple(net.undirected_edges), treatment_variable="access", outcome_variable=d["outcome"],
        outcome_kind="continuous", context_reference="W=synthetic_pre", observation_regime="experimental",
        assignment_design=assignment(d), protocol_provenance="EXPLICIT SYNTHETIC GROUP DESIGN",
        network_provenance="EXPLICIT SYNTHETIC FIXED NETWORK", graph_timing_claim="DECLARED_PRETREATMENT_FIXED")
    fixed = fixed_policy_target_from_context(study, tuple(int(n in target.treated_nodes) for n in nodes),
        authority="TRUSTED_FIXTURE", unit_weights=tuple(str(Fraction(1, len(target.nodes))) if n in target.nodes else "0" for n in nodes))
    assumptions = tuple(Assumption(name=n, source="demo_specification", confirmed=True, status="ADMITTED",
                                  evidence=[science["causal_licenses"]]) for n in REQUIRED)
    src = declare_network_a4_source(study, source_id="SYNTHETIC_GROUP_FULL_LAW", operator="NODE_FULL_LAW",
        provenance=science["population_information"], admission="ADMITTED",
        availability="SYMBOLIC_POPULATION_OPERATOR", outcome_nodes=nodes)
    return FixedPolicyInquiryV21(study, fixed, assumptions, r1b_sources=(src,))


def evaluate_numeric(question, numeric, packet, *, synthetic_protocol_selected=False):
    result = dict(version=VERSION, mode="SYNTHETIC_BENCHMARK_ONLY", results=[],
        business_question_sha256=canonical_hash(question), draft_sha256=canonical_hash(numeric),
        packet_sha256=canonical_hash(packet), semantic_correctness_verified=False,
        production_admission=False, candidate_generator_called=False, estimation_called=False,
        policy_called=False, nonidentification_proven=False)
    if synthetic_protocol_selected is not True:
        return {**result, "status": "REVIEW_REQUIRED", "reason_code": "EXPLICIT_SYNTHETIC_SELECTION_REQUIRED"}
    if packet["mode"] != "SYNTHETIC_BENCHMARK_ONLY":
        raise ValueError("Synthetic packet required")
    draft = NumericDraft.model_validate(numeric)
    sources = source_catalog(question)
    if (any(getattr(draft.study, n) is not None and getattr(draft.study, n) not in sources
            for n in ("graph_source", "partition_source", "design_source", "exposure_source")) or
            [t.question_quote for t in draft.targets] != list(question_slots(question).values())):
        return {**result, "status": "REJECTED", "reason_code": "NUMERIC_SOURCE_BINDING_INVALID"}
    for t in draft.targets:
        quotes = [t.population_quote, t.remaining_quote, t.plan_quote,
                  *(s.quote for s in (t.situation, t.reference) if s is not None)]
        if any(q is not None and q not in sources.values() for q in quotes):
            return {**result, "status": "REJECTED", "reason_code": "NUMERIC_SOURCE_BINDING_INVALID"}
    d = study_coordinates(draft.study)
    result["business_variable_binding"] = dict(
        outcome=d["outcome"], arm_core_outcome_symbol="outcome",
        treatment_coding="按题述处理：开通=1，不开通=0", arm_core_treatment_symbol="treatment")
    blocker = study_blocker(d, draft.study)
    if blocker:
        return {**result, "status": blocker[0], "reason_code": blocker[1]}
    if d != packet["study"]:
        return {**result, "status": "NEEDS_INPUT", "reason_code": "STUDY_READING_CONFLICTS_WITH_PROTOCOL"}
    science = packet["science"]
    from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome
    for i, t in enumerate(draft.targets, 1):
        row = dict(query_id=f"q{i}", proposed_target=target_coordinates(t), core_called=False, certificate_replay=False)
        blocker = _target_blocker(t, [f"{n:02d}" for n in range(1, d["units"] + 1)], d)
        if blocker is None and (not science["population_information"] or not science["causal_licenses"]):
            blocker = "NEEDS_INPUT", "INDEPENDENT_POPULATION_INFORMATION_AND_LICENSES_REQUIRED"
        if blocker:
            row.update(status=blocker[0], reason_code=blocker[1])
        else:
            try:
                inquiry = compile_inquiry(d, t, science)
            except ValueError as exc:
                if str(exc) != "CONTRAST_ORIENTATION_ADAPTER_UNSUPPORTED":
                    raise
                row.update(status="UNSUPPORTED", reason_code=str(exc))
            else:
                outcome = identify_network_business_query(inquiry)
                row.update(core_called=True, status=outcome.status, core=outcome.summary())
                if outcome.status == "POINT":
                    if replay_verified_business_outcome(outcome) is not True:
                        raise RuntimeError("Independent certificate replay failed")
                    row["certificate_replay"] = True
        result["results"].append(row)
    return {**result, "status": "COMPLETED_CONDITIONAL_SYNTHETIC_EVALUATION"}


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return evaluate_numeric(question, {}, packet, synthetic_protocol_selected=False)
    try:
        numeric, changes = project(question, raw)
        # These local validations must not be mistaken for a Core exception.
        study_coordinates(NumericDraft.model_validate(numeric).study)
    except (ValueError, ValidationError) as exc:
        reason = "GROUP_READING_SCHEMA_INVALID" if isinstance(exc, ValidationError) else str(exc)
        baseline = evaluate_numeric(question, {}, packet, synthetic_protocol_selected=False)
        status = ("REVIEW_REQUIRED" if reason == "QUESTION_COVERAGE_MISMATCH"
                  else "UNSUPPORTED" if reason.endswith("ADAPTER_UNSUPPORTED") else "REJECTED")
        return {**baseline, "status": status, "reason_code": reason, "model_draft_sha256": canonical_hash(raw)}
    result = evaluate_numeric(question, numeric, packet, synthetic_protocol_selected=True)
    result.update(prompt_version=VERSION, model_draft_sha256=canonical_hash(raw),
        normalized_draft_sha256=canonical_hash(numeric), exact_equivalences_applied=changes,
        source_reference_precision_verified=False)
    return result
