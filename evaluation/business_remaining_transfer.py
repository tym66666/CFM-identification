"""Apply explicit remaining-rule evidence to existing D2 and cluster arm entries.

The caller selects an existing typed entry; this module is not an automatic
router or a new identification method. No science is inferred from model text.
"""
from copy import deepcopy
import json
from . import business_d2_submission as d2
from . import business_arm_submission as cluster
from . import business_materials as materials
from .business_d1_staged import Remaining, project_target_candidate
from .business_materials_undecided_allocation import REMAINING_INSTRUCTION
from cfm_id_llm.providers.declared_outcome_contract import annotate_outcome_contract

from cfm_id.workflows.legacy_network.remaining_transfer import VERSION
from cfm_id.workflows.legacy_network.remaining_transfer import ENTRY_D2
from cfm_id.workflows.legacy_network.remaining_transfer import ENTRY_CLUSTER

from cfm_id.workflows.legacy_network.remaining_transfer import INSTRUCTION


from cfm_id.workflows.legacy_network.remaining_transfer import _entry


from cfm_id.workflows.legacy_network.remaining_transfer import make_request


from cfm_id.workflows.legacy_network.remaining_transfer import project_reading


from cfm_id.workflows.legacy_network.remaining_transfer import identify_reading


def normalize_reading(bundle, provider, entry):
    system, user = make_request(bundle, entry)
    raw = provider.generate_json(system_prompt=system, user_prompt=user)
    return identify_reading(bundle, raw, entry)
