"""Only expose a table-binding shortcut when that input actually has the table."""
import json
from . import business_materials_compact_json as without_table
from . import business_materials_probability_tables as with_table
from .business_materials_base import bundle_value

from cfm_id.workflows.legacy_network.materials_optional_tables import VERSION

from cfm_id.workflows.legacy_network.materials_optional_tables import make_request

from cfm_id.workflows.legacy_network.materials_optional_tables import project

from cfm_id.workflows.legacy_network.materials_optional_tables import evaluate_draft
