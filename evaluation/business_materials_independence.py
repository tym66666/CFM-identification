"""Require cited independence declarations and clarify single-scenario goals."""
from copy import deepcopy
import json
from pydantic import ValidationError
from . import business_materials_file_roles as previous
from . import business_materials_base as base
from .business_materials_intake import prompt_materials, sources
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_independence import VERSION
from cfm_id.workflows.legacy_network.materials_independence import SYSTEM


from cfm_id.workflows.legacy_network.materials_independence import output_schema


def make_request(value):
    bundle = base.bundle_value(value)
    m = prompt_materials(bundle)
    m["validated_file_bindings"] = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    return SYSTEM, json.dumps({**m, "output_schema": output_schema(bundle)}, ensure_ascii=False)


from cfm_id.workflows.legacy_network.materials_independence import expand


from cfm_id.workflows.legacy_network.materials_independence import project


from cfm_id.workflows.legacy_network.materials_independence import evaluate_draft
