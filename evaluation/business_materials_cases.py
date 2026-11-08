"""OFFLINE semantic references and explicitly conditional synthetic fixtures.

Never imported by online extraction/evaluation. Original public files stay intact.
"""
from copy import deepcopy
from .business_materials_intake import load_bundle, sources
from .business_materials_base import Study, study_coordinates
from .business_core_pilot_base import canonical_hash

CLARIFICATIONS = {
    "NBIB-003": """只评价名册中的全部72家门店，每家店权重相同。
在门店自己不发券时，相邻门店至少一家发券，比一家也不发券时，营业额平均高多少？
其余门店的安排沿用原商圈抽签规则，在满足上面条件的方案中平均。""",
    "NBIB-020": """评价全部48个仓库，按仓库等权平均。
如果按照candidate_policies.csv里的half_within_each_cluster名单，让每个区域一半仓库上线、其余不上线，全网络平均缺货小时会是多少？""",
    "NBIB-021": """评价名册中的全部64个站点，最终对每个站点的差值等权平均。
在邻居过半使用补货系统时，每个站点自己使用相对于不使用的缺货小时差多少，差值按使用减不使用计算？
在自己不使用时，邻居过半使用相对于未过半使用的缺货小时差多少，差值按过半减未过半计算？
其余安排仍沿用原两组抽签规则，在满足各情形条件的安排中平均。""",
}
ADDENDA = {
    "NBIB-020": "本条修订合成案例补充说明：四个区域的抽签彼此独立，每区仍以1/2概率整组上线。",
    "NBIB-021": "本条修订合成案例补充说明：units.csv的unit_group=0对应甲组，unit_group=1对应乙组。",
}


def ref(bundle, needle):
    matches = [k for k, v in sources(bundle).items() if needle in v]
    if len(matches) != 1:
        raise ValueError((needle, matches))
    return matches[0]


def world(own, neighbors, remaining):
    return dict(setting="局部条件", own=own, neighbors=neighbors, neighbor_count=None, remaining_source=remaining)


def question(pop_source, first, second=None, *, ids=None):
    return dict(operation="差值" if second is not None else "水平",
                population=dict(selection="全体" if ids is None else "指定", ids=[] if ids is None else ids),
                aggregation="等权平均" if ids is None or len(ids) > 1 else "单个",
                population_source=pop_source, first=first, second=second)


def fixture(cid, *, variant="original"):
    clarification = CLARIFICATIONS[cid] if variant != "original" else None
    addendum = ADDENDA.get(cid) if variant != "original" else None
    if variant == "single-store":
        clarification = """只评价名册中编号为unit_037的那家门店。
如果这家店自己不发券、相邻门店至少一家发券，它的平均营业额是多少？
其余门店的安排仍按原商圈抽签规则，在满足这些条件的方案中平均。"""
    elif variant == "whole-regions":
        clarification = """评价全部48个仓库，按仓库等权平均。
如果只让units.csv中unit_group为0或1的两个区域全体仓库上线，另外两个区域全体不上线，全网络平均缺货小时会是多少？"""
    elif variant == "single-station":
        clarification = """只看名册里unit_031这个站点。
如果它自己使用系统，而且邻居中超过一半也使用，它平均会有多少缺货小时？
其他站点仍遵循原两组抽签规则，在满足上述条件的方案中平均。"""
    elif variant == "cross-neighbor-scope":
        clarification = """只评价试验前与其他商圈至少一家门店有转介联系的门店，每家店权重相同；没有跨商圈联系的门店不在这次评价范围内。
在门店自己不发券时，相邻门店至少一家发券，比一家也不发券时，营业额平均高多少？
其余门店的安排沿用原商圈抽签规则，在满足上面条件的方案中平均。"""
    bundle = load_bundle(cid, clarification=clarification, design_addendum=addendum)
    params = [dict(group_id=g, quota=(16 if g == "0" else 12) if cid == "NBIB-021" else None,
                   probability=None if cid == "NBIB-021" else "1/2") for g in sorted(bundle["structure"]["groups"])]
    design_source = ref(bundle, "固定两条各32站" if cid == "NBIB-021" else
                         "试验前已固定六个商圈" if cid == "NBIB-003" else "48仓库固定四个区域")
    ds = [design_source]
    if cid != "NBIB-021":
        ds.append("cluster_randomization.csv")
    if addendum:
        ds.append(ref(bundle, "本条修订合成案例补充说明"))
    exposure = "strict_majority" if cid == "NBIB-021" else "any_treated_neighbor" if cid == "NBIB-003" else None
    study = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group",
        design="组内固定名额" if cid == "NBIB-021" else "整组开关", group_parameters=params,
        draws_independent=None if cid == "NBIB-020" and variant == "original" else True,
        design_sources=ds, exposure=exposure,
        exposure_source=design_source if exposure else None,
        outcome="store_revenue" if cid == "NBIB-003" else "warehouse_stockout")
    if variant == "original":
        qs = {k: dict(operation="不明确", population=dict(selection="不明确", ids=[]),
                      aggregation="不明确", population_source=None, first=None, second=None)
              for k in bundle["question_slots"]}
    elif cid == "NBIB-020":
        treated = dict(selection="指定分组", ids=["0", "1"]) if variant == "whole-regions" else dict(selection="政策名单", ids=["half_within_each_cluster"])
        qs = {"q1": question(ref(bundle, "评价全部48个仓库"), dict(setting="完整安排", treated=treated))}
    else:
        remaining = ref(bundle, "其余门店的安排" if cid == "NBIB-003" else
                        "其他站点仍遵循" if variant == "single-station" else "其余安排仍沿用")
        if variant in ("single-store", "single-station"):
            pop = ref(bundle, "只评价名册中编号" if cid == "NBIB-003" else "只看名册里")
            qs = {"q1": question(pop, world("不开通" if cid == "NBIB-003" else "开通",
                                            "至少一个" if cid == "NBIB-003" else "超过一半", remaining),
                                  ids=["unit_037" if cid == "NBIB-003" else "unit_031"])}
        elif cid == "NBIB-003":
            pop = ref(bundle, "只评价试验前" if variant == "cross-neighbor-scope" else "只评价名册中的全部72")
            qs = {"q1": question(pop, world("不开通", "至少一个", remaining),
                                world("不开通", "一个也没有", remaining))}
            if variant == "cross-neighbor-scope":
                qs["q1"]["population"] = dict(selection="有跨组邻居", ids=[])
        else:
            pop = ref(bundle, "评价名册中的全部64")
            qs = {"q1": question(pop, world("开通", "超过一半", remaining), world("不开通", "超过一半", remaining)),
                  "q2": question(pop, world("不开通", "超过一半", remaining), world("不开通", "至多一半", remaining))}
    reference = dict(study=study, questions=qs)
    packet = dict(mode="SYNTHETIC_BENCHMARK_ONLY", bundle_sha256=canonical_hash(bundle),
        study=study_coordinates(Study.model_validate(study), bundle),
        science=dict(population_information=None if variant == "original" else "EXPLICIT CONDITIONAL SYNTHETIC population operator",
                     causal_licenses=None if variant == "original" else "EXPLICIT CONDITIONAL SYNTHETIC causal licenses"))
    return dict(case_id=cid + "-" + variant, source_case_id=cid, variant=variant,
                bundle=bundle, reading_reference=reference, packet=packet,
                score_mode="ORIGINAL_EXPLORATORY_NO_TARGET_TRUTH" if variant == "original" else "FROZEN_COORDINATE_REFERENCE")


def fixtures():
    return [fixture(cid, variant=v) for v in ("original", "clarified") for cid in ("NBIB-003", "NBIB-020", "NBIB-021")] + [
        fixture("NBIB-003", variant="single-store"), fixture("NBIB-020", variant="whole-regions"),
        fixture("NBIB-021", variant="single-station"), fixture("NBIB-003", variant="cross-neighbor-scope")]
