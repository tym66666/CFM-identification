"""Accept an unambiguous singleton population alias without inventing targets."""
from copy import deepcopy
import json
from . import business_materials_source_roles as previous
from .business_materials_base import bundle_value
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_singleton_population import VERSION
from cfm_id.workflows.legacy_network.materials_singleton_population import SYSTEM


from cfm_id.workflows.legacy_network.materials_singleton_population import output_schema


from cfm_id.workflows.legacy_network.materials_singleton_population import make_request


from cfm_id.workflows.legacy_network.materials_singleton_population import normalize


from cfm_id.workflows.legacy_network.materials_singleton_population import project


from cfm_id.workflows.legacy_network.materials_singleton_population import evaluate_draft
