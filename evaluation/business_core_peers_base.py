"""Business adapter for pre-treatment core peers and independently reviewed goals.

This version deliberately leaves the mathematical Core and earlier frozen
adapters untouched. A source citation is provenance, not semantic entailment.
"""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from . import business_d1_submission as d1
from .business_core_pilot_base import Target, State, canonical_hash, target_coordinates, _target_blocker
from .business_d2_submission import Question as OldQuestion
from .business_d1_staged import Remaining, project_target_candidate
from .business_materials_intake import PUBLIC, _rows, sources, prompt_materials
from .business_materials_base import bundle_value, select
from .business_materials_target_provenance import target_sources
from .business_materials_whole_clause_evidence import clause_choices

from cfm_id.workflows.legacy_network.core_peers_base import VERSION
from cfm_id.workflows.legacy_network.core_peers_base import E3
from cfm_id.workflows.legacy_network.core_peers_base import CORE_FILE


from cfm_id.workflows.legacy_network.core_peers_base import Study


from cfm_id.workflows.legacy_network.core_peers_base import Question


def load_bundle(case_id, *, public_root=PUBLIC, **kwargs):
    b = d1.load_bundle(case_id, public_root=public_root, **kwargs)
    if CORE_FILE in b['tables']:
        data = (Path(public_root) / case_id / CORE_FILE).read_bytes()
        if sha256(data).hexdigest() != b['file_inventory'][CORE_FILE]['sha256']:
            raise ValueError('CORE_FILE_CHANGED')
        headers, rows = _rows(data.decode('utf-8-sig'))
        if not {'node_id', 'core_partner_node_id'} <= set(headers):
            raise ValueError('CORE_COLUMNS_MISSING')
        b['tables'][CORE_FILE]['rows'] = [{k: r[k] for k in ('node_id', 'core_partner_node_id')} for r in rows]
        b['core_partner_binding'] = dict(source=CORE_FILE, file_sha256=sha256(data).hexdigest(),
                                        table_sha256=canonical_hash(b['tables'][CORE_FILE]))
    else:
        b['core_partner_binding'] = None
    core_partner_table(b)
    return b


from cfm_id.workflows.legacy_network.core_peers_base import core_partner_table


from cfm_id.workflows.legacy_network.core_peers_base import SYSTEM


from cfm_id.workflows.legacy_network.core_peers_base import make_request


from cfm_id.workflows.legacy_network.core_peers_base import project


from cfm_id.workflows.legacy_network.core_peers_base import preview_submission


from cfm_id.workflows.legacy_network.core_peers_base import _aggregate


def normalize_submission(bundle, provider):
    system, user = make_request(bundle)
    return preview_submission(bundle, provider.generate_json(system_prompt=system, user_prompt=user))


from cfm_id.workflows.legacy_network.core_peers_base import compile_inquiry


from cfm_id.workflows.legacy_network.core_peers_base import identify_submission
