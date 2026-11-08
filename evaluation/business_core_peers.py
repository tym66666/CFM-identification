"""Retain known outcome population even for unsupported optimization goals."""
from .business_core_peers_base import (
    E3, CORE_FILE, Study, Question, load_bundle, core_partner_table, project,
    preview_submission, identify_submission, make_request as previous_request)

VERSION = 'business-core-peers-v0.51.1'


from cfm_id.workflows.legacy_network.core_peers import make_request


def normalize_submission(bundle, provider):
    system, user = make_request(bundle)
    result = preview_submission(bundle, provider.generate_json(system_prompt=system, user_prompt=user))
    result['reading_prompt_version'] = VERSION
    return result
