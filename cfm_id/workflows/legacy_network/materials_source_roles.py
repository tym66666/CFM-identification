"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import json
import cfm_id.workflows.legacy_network.materials_target_provenance as previous
from cfm_id.materials import sources
from cfm_id.materials import prompt_materials
from cfm_id.workflows.legacy_network.materials_base import bundle_value


VERSION = "business-materials-v0.23.5"


SYSTEM = previous.SYSTEM + """
分开做两步，不能混淆来源范围：
第一步study：从全部材料读取设计事实，study_protocol.md、design_addendum.txt和设计表都是可用来源。
study.design_sources、study.exposure_source、study.independence_source不受target_statement_sources限制。
“两组选择彼此独立”“两组第二阶段的选择彼此独立”都明确声明分组抽签独立；跨组有边或存在相互影响不否定抽签独立。
原文明确声明独立就填declared_independent=true并引用该原句，即使业务目标尚不清楚、文件只是合成材料或科学准入尚未完成。
原文没有声明才填null。没有声明与声明尚未认证是两件不同的事；你只摘录声明，不负责认证。
第二步questions：只有population_source和remaining_source受到target_statement_sources的目标文档范围限制。
最后逐项核对：是否漏读明确独立声明、是否把处理状态当评价人群、是否把历史设计当目标的其余安排、是否补入材料未说的条件。
"""


project = previous.project


output_schema = previous.output_schema


def make_request(value):
    bundle = bundle_value(value)
    m = prompt_materials(bundle)
    m["validated_file_bindings"] = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    m["target_statement_sources"] = previous.target_sources(bundle)
    m["source_role_rules"] = {
        "study_fields_use_all_materials": list(sources(bundle)) + [
            n for n in ("cluster_randomization.csv",) if n in bundle["tables"]],
        "only_question_population_and_remaining_use_target_document": list(previous.target_sources(bundle)),
    }
    return SYSTEM, json.dumps({**m, "output_schema": output_schema(bundle)}, ensure_ascii=False)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    r = previous.evaluate_draft(value, raw, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    r["version"] = VERSION
    return r
