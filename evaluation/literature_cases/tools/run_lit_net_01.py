"""Run LIT-NET-01 through the existing structured network-effect entry.

This is an explicit synthetic-review fixture. It does not call an LLM and does
not replace the paper reference. It turns the public case files into a
source-bound BusinessCase, supplies a hand-authored A0/fact draft, and runs the
repository's normal dispatch, science review and certificate replay.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from cfm_id import business_case
from cfm_id import business_dispatch as dispatch
from cfm_id import business_intake as intake
from cfm_id_llm import network_effect_reading as reading
from cfm_id_llm.compact_reference_contract import request_context, split_user
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from examples.business_dispatch_reference import approve


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-01"
OUT = ROOT / "evaluation" / "literature_cases" / "research_only" / "LIT-NET-01" / "structured_runs"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf8")


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def read_edges(path: Path) -> list[list[str]]:
    with path.open(encoding="utf8", newline="") as fh:
        return [[row["unit_a"], row["unit_b"]] for row in csv.DictReader(fh)]


def load_variant(variant: str) -> dict:
    folder = CASE / variant
    question = read_text(folder / "business_question.md")
    protocol = read_text(folder / "study_protocol.md")
    if variant == "missing_condition":
        edges = read_edges(folder / "network_partial.csv")
        complete = False
        network_text = (
            "只保留部分合作关系记录，共30条无向边；完整网络未提供，"
            "不能确认其余边，也不能对全部门店计算同伴暴露。"
        )
    else:
        edges = read_edges(folder / "network_edges.csv")
        complete = True
        network_text = (
            "完整无向合作边共120条，已列在关系表中；除此之外没有合作边。"
            "网络在处理前固定。"
        )
    nodes = [f"node-{i}" for i in range(60)]
    assignment_text = (
        "60家门店分别独立抽签，每家的启用概率均为1/2；"
        "完整处理向量的原设计是60个独立Bernoulli分布的乘积。"
    )
    exposure_text = (
        "同伴高使用S_i=1定义为完整网络中严格超过一半合作门店启用；"
        "至多一半包括平票为S_i=0。"
    )
    population_text = "评价完整名单中的全部60家门店，每家在最终效应中等权1/60。"
    remaining_text = (
        "在每个比较端满足本店处理和同伴暴露条件的完整安排中，"
        "按原试点独立Bernoulli(1/2)设计条件平均其余门店安排，"
        "不替换成全体使用或全体不使用的政策价值。"
    )
    context_text = "同一试点期、同一处理前网络与20项特征背景，结果为本期经营表现评分。"
    science_text = (
        "研究拟采用：完整处理向量与所有完整安排下的潜在结果独立；"
        "观察结果等于实际安排下的潜在结果；条件一阶矩存在且有限；网络在处理前固定。"
    )
    information_text = (
        "在识别层面声明可使用全部60家门店、四个(T_i,S_i)组合的符号总体条件平均结果；"
        "这些是总体信息，不是30家回访样本均值。"
    )
    docs = {
        "study": (
            "研究对象为60家门店，编号node-0到node-59；"
            "处理T_i=1表示本期启用AI经营助手，T_i=0表示不启用；"
            "结果为本期经营表现评分，连续数值。"
        ),
        "network": network_text,
        "assignment": assignment_text,
        "exposure": exposure_text,
        "population": population_text,
        "remaining": remaining_text,
        "context": context_text,
        "science": science_text,
        "information": information_text,
    }
    return dict(
        variant=variant,
        question=question,
        docs=docs,
        nodes=nodes,
        edges=edges,
        complete=complete,
    )


def claim(text: str, *documents: str) -> dict:
    return dict(state="STATED", value=text, refs=[])


def questions(data: dict) -> list[tuple[str, str, str]]:
    if data["variant"] == "changed_target":
        return [(
            "q1",
            "SPILLOVER_EFFECT",
            "在本店使用助手的条件下，合作门店至多一半使用相比合作门店超过一半使用，"
            "本店经营表现评分平均增加多少？计算“至多一半”减“超过一半”。",
        )]
    return [
        (
            "q1",
            "DIRECT_EFFECT",
            "在合作门店至多一半使用助手的条件下，本店使用助手相比本店不使用助手，"
            "经营表现评分平均增加多少？计算使用减不使用。",
        ),
        (
            "q2",
            "SPILLOVER_EFFECT",
            "在本店使用助手的条件下，合作门店超过一半使用相比至多一半使用，"
            "本店经营表现评分平均增加多少？计算过半减至多一半。",
        ),
        (
            "q3",
            "LOCAL_TOTAL_EFFECT",
            "本店使用且合作门店超过一半使用，相比本店不使用且合作门店至多一半使用，"
            "经营表现评分平均增加多少？计算前者减后者。",
        ),
    ]


def a0_reference(session, data: dict) -> dict:
    docs = data["docs"]
    request = intake.prepare_request(session)
    rows = split_user(request["user_prompt"])[1]["source_catalog"]

    def c(text: str, *documents: str) -> dict:
        refs = [
            r["ref"]
            for r in rows
            if r["source_id"] in documents and text in r.get("quote", "")
        ]
        return dict(state="STATED", value=text, refs=refs)

    common = dict(
        analysis_unit=c("60家门店", "study"),
        treatment=c("AI经营助手", "study"),
        outcome=c("经营表现评分", "study"),
        assignment_family="INDEPENDENT_BERNOULLI",
        assignment_law=c(docs["assignment"], "assignment"),
        unit_network=c(docs["network"], "network"),
        variable_causal_graph="UNKNOWN",
    )
    queries = []
    for qid, kind, text in questions(data):
        goal = c(text, "business_question")
        sem = dict(
            target_population=c(docs["population"], "population"),
            intervention=goal,
            comparator=goal,
            neighbor_exposure=c(docs["exposure"], "exposure"),
            aggregation=c("等权1/60", "population"),
            time_horizon=c("同一试点期", "context"),
            policy_assignment="NOT_APPLICABLE",
            standardization_distribution=c(docs["remaining"], "remaining"),
        )
        queries.append(dict(kind=kind, goal=goal, semantics=sem))
    return dict(
        common=common,
        queries=queries,
        reference_context=request_context(request["user_prompt"]),
    )


def declaration(value: bool, doc: str, refs) -> dict:
    return dict(value=value, source_ids=refs(doc))


def coordinates(qid: str, kind: str) -> tuple[tuple[int, int], tuple[int, int]]:
    if qid == "q1" and kind == "DIRECT_EFFECT":
        return (1, 0), (0, 0)
    if qid == "q2":
        return (1, 1), (1, 0)
    if qid == "q3":
        return (1, 1), (0, 0)
    # changed_target: reverse of the original spillover
    return (1, 0), (1, 1)


def fact_reference(entry: dict, data: dict) -> dict:
    refs = reading.reference_catalog(entry["bundle"], binding=entry["fact_binding_sha256"])

    def ids(doc: str) -> list[str]:
        return [k for k, v in refs["aliases"].items() if v["doc_id"] == doc]

    qid = entry["query_id"]
    kind = entry["selected_query"]["target"]["kind"]
    first, second = coordinates(qid, kind)
    nodes = data["nodes"]
    return dict(
        version=reading.VERSION,
        reference_context=refs["context"],
        study=dict(
            nodes=nodes,
            edges=[list(e) for e in data["edges"]],
            graph_kind="SIMPLE_UNDIRECTED",
            edge_list_complete=data["complete"],
            treatment="本期启用AI经营助手；T_i=1表示启用，T_i=0表示不启用",
            outcome="本期经营表现评分，连续数值，评分越高表示表现越好",
            outcome_kind="CONTINUOUS",
            context=data["docs"]["context"],
            source_ids=ids("study") + ids("network") + ids("context"),
        ),
        assignment=dict(
            kind="INDEPENDENT_BERNOULLI",
            probabilities={n: "1/2" for n in nodes},
            fixed_count=None,
            source_ids=ids("assignment"),
        ),
        target=dict(
            kind=kind,
            operation="FIRST_MINUS_SECOND",
            first=dict(own=first[0], exposure=first[1], source_ids=ids("__question__") + ids("exposure")),
            second=dict(own=second[0], exposure=second[1], source_ids=ids("__question__") + ids("exposure")),
            population=nodes,
            aggregation="EQUAL_MEAN",
            population_fixed_before_assignment=declaration(True, "population", ids),
            remaining_assignment="ORIGINAL_DESIGN_CONDITIONAL",
            remaining_source_ids=ids("remaining"),
            shared_outcome_and_context=declaration(True, "context", ids),
            source_ids=ids("__question__") + ids("population"),
        ),
        exposure=dict(kind="STRICT_MAJORITY_TIES_LOW", source_ids=ids("exposure")),
        design_facts=dict(
            assignment_rule_available=declaration(True, "assignment", ids),
            network_fixed_before_treatment=declaration(True, "network", ids),
        ),
        scientific_statements={
            k: dict(status="PROPOSED", source_ids=ids("science"))
            for k in ("assignment_outcome_independence", "consistency", "finite_conditional_means")
        },
        information=[dict(
            operator="NODE_ARM_MEANS",
            availability="SYMBOLIC_POPULATION_OPERATOR",
            outcome_nodes=nodes,
            arm_cells=[dict(node=n, own=a, exposure=e) for n in nodes for a in (0, 1) for e in (0, 1)],
            source_ids=ids("information"),
        )],
        additional_restrictions=[],
        unresolved=[],
    )


def approval_records(plan: dict) -> dict:
    return dict(
        plan_review=approve(plan["plan_worksheet"]),
        native_reviews={
            row["method"]: dict(
                reading_review=approve(row["reading_worksheet"]),
                science_review=approve(row["science_worksheet"]),
            )
            for row in plan["methods"]
        },
        research_protocol_selected=True,
    )


def run_variant(variant: str) -> dict:
    data = load_variant(variant)
    docs = data["docs"]
    case = BusinessCase(
        case_id=f"LIT-NET-01-{variant}",
        business_question=data["question"],
        sources=[SourceDocument(source_id=k, text=v) for k, v in docs.items()],
    )
    session = intake.start(
        case,
        reading_format="compact",
        fact_format="short_refs",
        a0_reference_contract="compact-source-paragraphs-1",
    )
    session = intake.receive_candidate(session, a0_reference(session, data), request_sha256=session.request_sha256)

    submissions = {}
    plan_rows = []
    for qid, _kind, _text in questions(data):
        qreview = approve(dispatch.prepare_reader(session, qid)["query_worksheet"])
        entry = dispatch.prepare_reader(session, qid, query_review=qreview)
        if entry["state"] != "READY_TO_READ":
            plan_rows.append(dict(query_id=qid, state=entry["state"], reason=entry.get("reason_code")))
            continue
        raw = fact_reference(entry, data)
        options = dict(query_review=qreview, candidate=raw, request_sha256=entry["request_sha256"])
        plan = dispatch.inspect_methods(session, qid, **options)
        plan_rows.append(dict(query_id=qid, state=plan["state"], reason=plan.get("reason_code"), plan=plan))
        if plan["state"] == "REVIEW_REQUIRED":
            submissions[qid] = dict(options, **{k: v for k, v in approval_records(plan).items() if k != "research_protocol_selected"})

    if submissions:
        result = business_case.execute_case(
            session,
            submissions,
            case_review=approve(business_case.prepare_case(session)["case_worksheet"]),
            research_protocol_selected=True,
        )
    else:
        result = dict(state="NEEDS_INPUT", reason_code="NO_QUERY_READY", results=[])

    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "source_documents.json", docs)
    write_json(folder / "plans.json", plan_rows)
    write_json(folder / "result.json", result)
    return dict(variant=variant, state=result.get("state"), results=[
        dict(query_id=row.get("query_id"), state=row.get("result", {}).get("state"),
             replay=row.get("result", {}).get("independent_replay"))
        for row in result.get("results", [])
    ], plans=[dict(query_id=row["query_id"], state=row["state"], reason=row.get("reason")) for row in plan_rows])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    args = parser.parse_args(argv)
    variants = ["original", "missing_condition", "changed_target"] if args.variant == "all" else [args.variant]
    rows = [run_variant(v) for v in variants]
    summary = dict(api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
