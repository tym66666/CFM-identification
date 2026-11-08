"""Opt-in full-materials reader to existing D3/D4 R1a/R1b.

The model selects table references and business coordinates. Local deterministic
loading supplies the declared graph/partition/policy, never an answer or license.
"""
from fractions import Fraction
import json
from typing import Literal
from pydantic import Field, StrictBool, StrictInt, ValidationError
from .business_core_pilot_base import Closed, Target, State, canonical_hash, target_coordinates, _target_blocker
from .business_groups_base import _arm, assignment
from .business_materials_intake import sources, prompt_materials, validate_tables, goal_slots

from cfm_id.workflows.legacy_network.materials_base import VERSION
from cfm_id.workflows.legacy_network.materials_base import SYSTEM


from cfm_id.workflows.legacy_network.materials_base import GroupParameter


from cfm_id.workflows.legacy_network.materials_base import Study


from cfm_id.workflows.legacy_network.materials_base import Selection


from cfm_id.workflows.legacy_network.materials_base import Complete


from cfm_id.workflows.legacy_network.materials_base import Conditional


from cfm_id.workflows.legacy_network.materials_base import Question


from cfm_id.workflows.legacy_network.materials_base import bundle_value


from cfm_id.workflows.legacy_network.materials_base import output_schema


def make_request(value):
    bundle = bundle_value(value)
    return SYSTEM, json.dumps({**prompt_materials(bundle), "output_schema": output_schema(bundle)}, ensure_ascii=False)


from cfm_id.workflows.legacy_network.materials_base import select


from cfm_id.workflows.legacy_network.materials_base import study_coordinates


from cfm_id.workflows.legacy_network.materials_base import project


from cfm_id.workflows.legacy_network.materials_base import compile_inquiry


from cfm_id.workflows.legacy_network.materials_base import evaluate_draft
