"""One explicit question-level remaining-allocation declaration.

The current Core adapter has one common remaining rule per target. Request that
rule once; never silently copy a missing answer from another model field.
"""
from copy import deepcopy
import json
from . import business_materials_singleton_population as previous
from .business_materials_base import bundle_value
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_remaining_declaration import VERSION
from cfm_id.workflows.legacy_network.materials_remaining_declaration import SYSTEM


from cfm_id.workflows.legacy_network.materials_remaining_declaration import output_schema


from cfm_id.workflows.legacy_network.materials_remaining_declaration import make_request


from cfm_id.workflows.legacy_network.materials_remaining_declaration import expand


from cfm_id.workflows.legacy_network.materials_remaining_declaration import project


from cfm_id.workflows.legacy_network.materials_remaining_declaration import evaluate_draft
