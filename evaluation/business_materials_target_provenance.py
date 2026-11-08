"""Target-document provenance and lossless retention of incomplete readings.

Document roles constrain citation provenance, not semantic entailment. Partial
scenarios cannot become identified targets until the operation is specified.
"""
from copy import deepcopy
import json
from pydantic import ValidationError
from . import business_materials_independence as previous
from . import business_materials_base as base
from .business_materials_intake import sources, prompt_materials
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_target_provenance import VERSION
from cfm_id.workflows.legacy_network.materials_target_provenance import SYSTEM


from cfm_id.workflows.legacy_network.materials_target_provenance import target_sources


from cfm_id.workflows.legacy_network.materials_target_provenance import output_schema


def make_request(value):
    bundle = base.bundle_value(value)
    m = prompt_materials(bundle)
    m["validated_file_bindings"] = dict(network_file="network_edges.csv", partition_file="units.csv", group_column="unit_group")
    m["target_statement_sources"] = target_sources(bundle)
    return SYSTEM, json.dumps({**m, "output_schema": output_schema(bundle)}, ensure_ascii=False)


from cfm_id.workflows.legacy_network.materials_target_provenance import normalize


from cfm_id.workflows.legacy_network.materials_target_provenance import project


from cfm_id.workflows.legacy_network.materials_target_provenance import evaluate_draft
