"""OFFLINE fixtures and semantic references. Never import in the API runner.

These are explicitly revised synthetic inputs, not the original NBIB21 score.
Population operators and causal licenses are separate synthetic declarations,
not inferred from prose or finite samples, and are never sent to the model.
"""
from copy import deepcopy
from .business_core_source_refs import source_catalog
from .business_reading_base import question_slots


def _world(own, neighbors, count=None):
    return dict(setting="局部条件", own=own, neighbors=neighbors,
                neighbor_count=count, remaining_source="s06")


def _question(first, second=None, population=None):
    return dict(operation="水平" if second is None else "差值",
                population=dict(selection="全体" if population is None else "指定",
                                ids=[] if population is None else population),
                aggregation="等权平均" if population is None or len(population) > 1 else "单个",
                population_source=None, first=first, second=second)


def _plan(nodes):
    return _question(dict(setting="完整安排", treated=dict(selection="指定", ids=nodes)))


def _case(cid, design, questions, reference_questions, *, missing_probability=False,
          missing_information=False, probabilities=None, quotas=None, exposure="any_treated_neighbor",
          original=None):
    if design == "组内固定名额":
        groups = [["01", "02", "03", "04"], ["05", "06", "07", "08"]]
        quotas = quotas or [2, 1]
        partition = "甲组是01、02、03、04，乙组是05、06、07、08。"
        rule = f"两组分别抽签，彼此独立；甲组在四人中等机会抽出{quotas[0]}人，乙组在四人中等机会抽出{quotas[1]}人，抽中的开通AI助手，其余不开通。"
        probabilities = None
    else:
        groups = [["01", "02"], ["03", "04"], ["05", "06"], ["07", "08"]]
        probabilities = probabilities or ["1/2", "1/3", "2/3", "1/4"]
        partition = "四个小组的成员依次是（01、02）、（03、04）、（05、06）、（07、08）。"
        if missing_probability:
            probabilities = [*probabilities[:3], None]
            rate = "前三组抽中的概率依次为1/2、1/3、2/3，第四组的概率暂时没找到"
        else:
            rate = "四组抽中的概率依次为" + "、".join(probabilities)
        rule = f"各组独立抽一次签，抽中就全组开通AI助手，没抽中就全组不开通；{rate}。"
        quotas = None
    exposure_sentence = ("我们用邻居里开通的人数记录周边情况，结果看处理量。"
                         if exposure == "exact_treated_neighbor_count" else
                         "我们只把邻居情况分成至少一人开通、一个人也没开通两类，结果看处理量。")
    sentences = [
        "我们有8个作业点，编号01到08。",
        "试验前就确定了协作关系：01连02、02连03，一直到07连08，再由08连回01，除此以外没有联系，试验期间关系不变。",
        partition, rule, exposure_sentence,
        "下面如果只限定某个作业点自己和邻居的情况，其余安排就沿用原来的抽签规则，在满足这些条件的安排中取平均。",
    ]
    if missing_information:
        sentences.append("我们手头只有这一次试验的8行数据，没有另外确认总体信息是否可用。")
    text = "".join(sentences + questions)
    slots = list(question_slots(text))
    refs = deepcopy(reference_questions)
    for sid, q in zip(slots, refs):
        q["population_source"] = sid
    study = dict(units=8, graph="ring", center=None, design=design, groups=groups,
                 quotas=quotas, probabilities=probabilities, draws_independent=True,
                 exposure=exposure, outcome="处理量",
                 graph_source="s02", partition_source="s03", design_source="s04", exposure_source="s05")
    coordinates = {k: v for k, v in study.items() if not k.endswith("_source")}
    return dict(
        case_id=cid, original_case_id=original,
        revision_note="新版合成业务：8个节点、明确网络/分组/目标；独立报告，未覆盖原21题的复杂材料。",
        business_question=text,
        reading_reference=dict(study=study, questions=dict(zip(slots, refs))),
        packet=dict(mode="SYNTHETIC_BENCHMARK_ONLY", study=coordinates,
                    science=dict(
                        population_information="" if missing_information else
                        "EXPLICIT SYNTHETIC population operator declaration, independent of the finite sample",
                        causal_licenses="EXPLICIT SYNTHETIC randomized design and consistency licenses",
                        mean_signature_sufficiency=None)))


def fixtures():
    d3q = [
        "对01、04、05、08这四个点，在邻居至少一人开通的情况下，各点自己开通比自己不开通多多少处理量，再把这四个差值等权取平均？",
        "对01、04、05、08这四个点，在自己不开通的情况下，各点有邻居开通比一个邻居也没开通多多少处理量，再把这四个差值等权取平均？",
    ]
    d3ref = [_question(_world("开通", "至少一个"), _world("不开通", "至少一个"), ["01", "04", "05", "08"]),
             _question(_world("不开通", "至少一个"), _world("不开通", "一个也没有"), ["01", "04", "05", "08"])]
    cs = [
        _case("D3-effects", "组内固定名额", d3q, d3ref, original="NBIB-021"),
        _case("D4-arm", "整组开关", [
            "如果01自己不开通，但邻居至少有一人开通，01的平均处理量是多少？"
        ], [_question(_world("不开通", "至少一个"), population=["01"])], original="NBIB-003"),
        _case("D4-split-plan", "整组开关", [
            "如果只给01、03、05、07开通，其余全部不开通，全体8个作业点的平均处理量是多少？"
        ], [_plan(["01", "03", "05", "07"])], original="NBIB-020"),
        _case("D3-fixed-plan", "组内固定名额", [
            "如果只给01、03、05开通，其余全部不开通，全体8个作业点的平均处理量是多少？"
        ], [_plan(["01", "03", "05"])]),
        _case("D4-whole-plan", "整组开关", [
            "如果第一组和第三组全部开通，第二组和第四组全部不开通，全体8个作业点的平均处理量是多少？"
        ], [_plan(["01", "02", "05", "06"])]),
        _case("D3-over-quota", "组内固定名额", [
            "如果只给01、02、03、05开通，其余全部不开通，全体8个作业点的平均处理量是多少？"
        ], [_plan(["01", "02", "03", "05"])]),
        _case("D4-missing-probability", "整组开关", [
            "如果01自己不开通，但邻居至少有一人开通，01的平均处理量是多少？"
        ], [_question(_world("不开通", "至少一个"), population=["01"])], missing_probability=True),
        _case("D4-finite-data-only", "整组开关", [
            "如果01自己不开通，但邻居至少有一人开通，01的平均处理量是多少？"
        ], [_question(_world("不开通", "至少一个"), population=["01"])], missing_information=True),
        _case("D3-changed-quota", "组内固定名额", [
            "假如下次确定由01、05、07用助手，别的点都不用，八个作业点的处理量平均会是多少？"
        ], [_plan(["01", "05", "07"])], quotas=[1, 2]),
        _case("D4-changed-rates", "整组开关", [
            "我们只关心01：它不用助手、两个邻居中有人用时，它的平均处理量会是多少？"
        ], [_question(_world("不开通", "至少一个"), population=["01"])],
              probabilities=["1/3", "1/3", "2/3", "1/2"]),
        _case("D3-exact-count-offline", "组内固定名额", [
            "如果01自己开通，而且恰好一个邻居开通，01的平均处理量是多少？"
        ], [_question(_world("开通", "恰好人数", 1), population=["01"])],
              exposure="exact_treated_neighbor_count"),
        _case("D4-impossible-arm-offline", "整组开关", [
            "如果01自己开通，而且一个邻居也没开通，01的平均处理量是多少？"
        ], [_question(_world("开通", "一个也没有"), population=["01"])]),
        _case("D3-all-points-effects-offline", "组内固定名额", [
            "在邻居至少一人开通的情况下，每个作业点自己开通比自己不开通多多少处理量，然后对全体8个作业点等权取平均？",
            "在自己不开通的情况下，每个作业点有邻居开通比一个邻居也没开通多多少处理量，然后对全体8个作业点等权取平均？",
        ], [_question(_world("开通", "至少一个"), _world("不开通", "至少一个")),
            _question(_world("不开通", "至少一个"), _world("不开通", "一个也没有"))]),
    ]
    assert all(len(c["reading_reference"]["questions"]) == len(question_slots(c["business_question"])) for c in cs)
    return cs
