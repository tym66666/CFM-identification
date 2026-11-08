"""Accept omitted question numbering while preserving all semantic words.

Only validation metadata may be normalized. The raw output and its semantic
projection remain unchanged; no general substring matching is introduced.
"""
from copy import deepcopy
import re
from . import business_condition_evidence_base as prior

from cfm_id.workflows.legacy_network.condition_evidence import VERSION
from cfm_id.workflows.legacy_network.condition_evidence import _NUMBERING
augment_request=prior.augment_request


from cfm_id.workflows.legacy_network.condition_evidence import project_evidence


from cfm_id.workflows.legacy_network.condition_evidence import guarded_dispatch
