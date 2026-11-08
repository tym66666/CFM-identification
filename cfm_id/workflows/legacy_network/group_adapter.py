"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from fractions import Fraction
import json
from typing import Literal
from pydantic import Field, StrictBool, StrictInt, ValidationError


def assignment(d):
    if d["design"] == "组内固定名额":
        return dict(kind="two_group_fixed_quota_binary_v1", groups=d["groups"], treated_quotas=d["quotas"])
    return dict(kind="cluster_bernoulli_binary_v2_4", clusters=d["groups"], cluster_probabilities=d["probabilities"])


def _arm(d, net, node, own, peers):
    from pfn_pipeline.identification import make_two_group_quota_arm_task, make_cluster_bernoulli_arm_task
    opts = dict(node_id=node, own_treatment_value=own, exposure_value=peers,
                exposure_definition=d["exposure"], source="EXPLICIT_SYNTHETIC_GROUP_PROTOCOL",
                evidence="Independent declared population information; not a sample estimate",
                synthetic=True, admitted=True, query_authority="TRUSTED_FIXTURE")
    if d["design"] == "组内固定名额":
        return make_two_group_quota_arm_task(net, groups=tuple(tuple(g) for g in d["groups"]),
                                             treated_quotas=tuple(d["quotas"]), **opts)
    return make_cluster_bernoulli_arm_task(net, clusters=d["groups"],
                                          cluster_probabilities=d["probabilities"], **opts)
