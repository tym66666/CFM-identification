"""Bind complete cluster probability tables locally, as with network/roster files.

The model must still read the design and independence declaration. A table of
marginal probabilities never establishes independent draws or a causal license.
"""
from copy import deepcopy
import json
from . import business_materials_compact_json as previous
from .business_materials_target_precedence import output_schema as prior_schema
from .business_materials_base import bundle_value
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_probability_tables import VERSION
from cfm_id.workflows.legacy_network.materials_probability_tables import SYSTEM

from cfm_id.workflows.legacy_network.materials_probability_tables import output_schema

from cfm_id.workflows.legacy_network.materials_probability_tables import make_request

from cfm_id.workflows.legacy_network.materials_probability_tables import expand

from cfm_id.workflows.legacy_network.materials_probability_tables import project

from cfm_id.workflows.legacy_network.materials_probability_tables import evaluate_draft
