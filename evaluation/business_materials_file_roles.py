"""Bind validated file roles locally; extract declarations, never approvals."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictBool, ValidationError
from . import business_materials_base as previous
from .business_core_pilot_base import Closed, canonical_hash
from .business_materials_intake import prompt_materials

VERSION = "business-materials-v0.23.1"
from cfm_id.workflows.legacy_network.materials_file_roles import SYSTEM


from cfm_id.workflows.legacy_network.materials_file_roles import MaterialStudy


from cfm_id.workflows.legacy_network.materials_file_roles import output_schema


def make_request(value):
    bundle = previous.bundle_value(value)
    materials = prompt_materials(bundle)
    materials["validated_file_bindings"] = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    return SYSTEM, json.dumps({**materials, "output_schema": output_schema(bundle)}, ensure_ascii=False)


from cfm_id.workflows.legacy_network.materials_file_roles import expand


def project(value, raw):
    return previous.project(value, expand(raw))


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    try:
        expanded = expand(raw)
    except (ValueError, ValidationError):
        return dict(version=VERSION, status="REJECTED", reason_code="READING_SCHEMA_INVALID",
            results=[], core_called=False, production_admission=False, candidate_generator_called=False,
            estimation_called=False, policy_called=False, nonidentification_proven=False,
            semantic_correctness_verified=False, model_draft_sha256=canonical_hash(raw))
    result = previous.evaluate_draft(value, expanded, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION, model_draft_sha256=canonical_hash(raw),
                  structural_bindings="validated_local_csv_coordinates_not_model_reconstruction")
    return result
