"""Ground remaining-rule evidence in whole source clauses, not unrelated text.

The span is a candidate citation. Exact membership and a contradiction veto are
necessary checks, never a general proof of semantic entailment or causality.
"""
from copy import deepcopy
import json
import re
from . import business_materials_optional_tables as base
from . import business_materials_undecided_allocation as prior
from .business_materials_base import bundle_value
from .business_materials_target_provenance import target_sources
from .business_core_pilot_base import canonical_hash

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import VERSION

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import clause_choices

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import make_request

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import normalize

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import project

from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import evaluate_draft
