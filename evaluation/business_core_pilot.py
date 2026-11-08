"""Readable peer relations -> deterministic existing-Core exposure codes.

No source correction, no gold lookup, no LLM retry and no scientific admission.
The previous numeric extraction interface remains replayable in v020.
"""
import json
from typing import Literal
from pydantic import Field, StrictInt
from .business_core_pilot_base import (
    Closed, Reading, Target, ModelDraft, SYSTEM, canonical_hash,
    evaluate_draft as evaluate_numeric_draft,
)

VERSION = "business-core-pilot-v0.20.2"


class ReadableState(Closed):
    own: StrictInt = Field(ge=0, le=1, description="本人的处理状态：开通/安装/使用=1，没有=0")
    peer_relation: Literal["more_than_half", "at_most_half", "at_least_one", "none", "exact_count"] = Field(
        description="邻居条件的文字含义：超过一半、至多一半、至少一个、一个也没有、恰好若干个。不要计算或填写Core状态编号")
    peer_count: StrictInt | None = Field(
        description="仅exact_count填写明确的人数/站数，其他关系必须null；超过一半不是具体人数")
    quote: str = Field(min_length=2, description="连续引用原文。本人和邻居条件分隔时可引用完整问题，禁止用省略号拼接")


class ReadableTarget(Target):
    situation: ReadableState | None
    reference: ReadableState | None


class ReadableDraft(Closed):
    study: Reading
    targets: list[ReadableTarget] = Field(min_length=1, max_length=6)


READABLE_SYSTEM = SYSTEM + """
邻居条件使用peer_relation表达原文含义，让本地程序处理0/1编码。不要将“超过一半”换算成具体人数。
所有引用必须连续，可引用整个问题句，即使句子同时包含两个比较情形。不得插入原文没有的省略号、标点或连接词。
"""


def make_request(business_question):
    return READABLE_SYSTEM, json.dumps({
        "business_question": business_question,
        "output_schema": ReadableDraft.model_json_schema(),
    }, ensure_ascii=False)


def numeric_projection(raw):
    draft = ReadableDraft.model_validate(raw)
    projected = draft.model_dump()
    exposure = draft.study.exposure
    mapping = {
        "strict_majority": {"more_than_half": 1, "at_most_half": 0},
        "any_treated_neighbor": {"at_least_one": 1, "none": 0},
    }
    for target in projected["targets"]:
        for key in ("situation", "reference"):
            value = target[key]
            if value is None:
                continue
            relation, count = value["peer_relation"], value["peer_count"]
            if exposure == "exact_treated_neighbor_count":
                if relation != "exact_count" or type(count) is not int or count < 0:
                    raise ValueError("PEER_RELATION_CONFLICTS_WITH_EXPOSURE")
                peers = count
            else:
                if count is not None or relation not in mapping[exposure]:
                    raise ValueError("PEER_RELATION_CONFLICTS_WITH_EXPOSURE")
                peers = mapping[exposure][relation]
            target[key] = dict(own=value["own"], peers=peers, quote=value["quote"])
    return ModelDraft.model_validate(projected).model_dump()


def evaluate_draft(business_question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        # Do not let any proposed semantic representation supply permission.
        return evaluate_numeric_draft(business_question, {}, packet,
                                      synthetic_protocol_selected=False)
    numeric = numeric_projection(raw)
    result = evaluate_numeric_draft(business_question, numeric, packet,
                                    synthetic_protocol_selected=True)
    result.update(version=VERSION, model_draft_sha256=canonical_hash(raw),
                  projection_version="readable-peer-relation-to-core-code-v1",
                  normalized_draft_sha256=canonical_hash(numeric))
    return result
