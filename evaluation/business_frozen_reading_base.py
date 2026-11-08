"""Frozen reading contract for an opt-in cross-business development evaluation.

Adds a schema-level distinction between unknown peer scope and an inapplicable
scope. Never repairs fields or grants science. Existing Core routes are reused.
"""
import json
from copy import deepcopy
from . import business_evidence_entries as entries
from . import business_staged_d1_d2 as staged

from cfm_id.workflows.legacy_network.frozen_reading_base import VERSION


from cfm_id.workflows.legacy_network.frozen_reading_base import make_request


from cfm_id.workflows.legacy_network.frozen_reading_base import cross_field_issues


from cfm_id.workflows.legacy_network.frozen_reading_base import identify


def normalize(bundle,provider,entry,envelope=None):
    s,u=make_request(bundle,entry,envelope)
    return identify(bundle,provider.generate_json(system_prompt=s,user_prompt=u),entry,envelope)
