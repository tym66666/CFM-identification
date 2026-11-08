"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from __future__ import annotations
from fractions import Fraction
from hashlib import sha256
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class State(Closed):
    own: StrictInt = Field(ge=0, le=1, description="本人的处理状态：开通/安装/使用=1，没有=0")
    peers: StrictInt = Field(ge=0, description="邻居状态：按题中定义计数或0/1；不能将恰好一个改成至少一个")
    quote: str = Field(min_length=2, description="支持本人和邻居状态的连续原句")


class Target(Closed):
    question_quote: str = Field(min_length=2, description="该子问题的原句，逐字连续引用")
    kind: Literal["arm", "comparison", "fixed_plan", "optimization", "unclear"]
    nodes: list[str] | None = Field(description="结果取平均的对象编号列表；不确定填null。人群不等于假设处理情形")
    aggregation: Literal["single", "equal_mean"] | None = Field(description="单个对象或等权平均；总和、未说明权重不能擅改平均")
    population_quote: str | None = Field(description="原文中明确评价范围和平均方式的连续原句")
    situation: State | None = Field(description="arm的条件；comparison中被减数，即情形甲")
    reference: State | None = Field(description="comparison中减数，即情形乙；其他目标填null")
    remaining: Literal["original_randomization"] | None = Field(description="臂均值或比较中，其余分配遵循原抽签的条件分布；非明确说明则null")
    remaining_quote: str | None = Field(description="支持上述其余分配含义的原句，其他目标填null")
    treated_nodes: list[str] | None = Field(description="fixed_plan中全部获处理对象编号，其他人明确不处理；其他目标填null")
    plan_quote: str | None = Field(description="固定推广方案的完整原句；不能从优化问题捏造一个方案")
    unresolved: list[str] = Field(description="仅列无法确定研究目标坐标的信息：评价谁、哪两种情形、平均方式、指定方案或其余分配规则。目标明确则[]。不在这里审查数据交付、假设真实性、数值计算或总体分布的具体数值；这些由独立环节处理")


def target_coordinates(target: Target):
    return {
        "kind": target.kind, "nodes": target.nodes, "aggregation": target.aggregation,
        "situation": None if target.situation is None else [target.situation.own, target.situation.peers],
        "reference": None if target.reference is None else [target.reference.own, target.reference.peers],
        "remaining": target.remaining, "treated_nodes": target.treated_nodes,
        "unresolved": target.unresolved,
    }


def _target_blocker(t, nodes, d):
    if t.unresolved or t.kind == "unclear":
        return "NEEDS_INPUT", "TARGET_UNRESOLVED"
    if t.kind == "optimization":
        return "UNSUPPORTED", "POLICY_OPTIMIZATION_OUTSIDE_IDENTIFICATION"
    if (not t.nodes or len(set(t.nodes)) != len(t.nodes) or not set(t.nodes) <= set(nodes)
            or not t.population_quote or t.aggregation is None):
        return "NEEDS_INPUT", "POPULATION_AND_AGGREGATION_REQUIRED"
    if (t.aggregation == "single") != (len(t.nodes) == 1):
        return "NEEDS_INPUT", "POPULATION_AGGREGATION_MISMATCH"
    if t.kind in ("arm", "comparison"):
        if t.remaining != "original_randomization" or not t.remaining_quote:
            return "NEEDS_INPUT", "REMAINING_ALLOCATION_UNRESOLVED"
        if not t.situation or (t.kind == "comparison" and not t.reference):
            return "NEEDS_INPUT", "EXPLICIT_TARGET_STATES_REQUIRED"
        if t.treated_nodes is not None or t.plan_quote is not None or (t.kind == "arm" and t.reference):
            return "NEEDS_INPUT", "CONFLICTING_TARGET_FIELDS"
        if t.kind == "arm" and len(t.nodes) != 1:
            return "UNSUPPORTED", "GROUP_ARM_ADAPTER_NOT_IMPLEMENTED"
        states = [s for s in (t.situation, t.reference) if s]
        if d["exposure"] != "exact_treated_neighbor_count" and any(s.peers > 1 for s in states):
            return "NEEDS_INPUT", "EXPOSURE_STATE_OUT_OF_RANGE"
    else:
        if t.treated_nodes is None or not t.plan_quote:
            return "NEEDS_INPUT", "FIXED_PLAN_REQUIRED"
        if len(set(t.treated_nodes)) != len(t.treated_nodes) or not set(t.treated_nodes) <= set(nodes):
            return "NEEDS_INPUT", "INVALID_FIXED_PLAN_NODES"
        if t.situation or t.reference or t.remaining or t.remaining_quote:
            return "NEEDS_INPUT", "CONFLICTING_TARGET_FIELDS"
    return None
