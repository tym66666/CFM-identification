"""Opt-in evidence gate for existing reviewed entries; no automatic routing."""
from . import business_condition_evidence_base as evidence
from . import business_d1_submission as d1
from . import business_core_peers_base as peers
from . import business_core_peers_staged as staged
from . import business_remaining_transfer as transfer


from cfm_id.workflows.legacy_network.evidence_entries import base_request


from cfm_id.workflows.legacy_network.evidence_entries import make_request


def reviewed_representation(bundle, raw, entry, envelope=None):
    projected, receipt = evidence.project_evidence(bundle, raw)
    if not receipt['passed']:
        raise ValueError('TARGET_CONDITION_EVIDENCE_REJECTED')
    if entry == 'STAGED_CORE_PEERS':
        return staged.compose_reading(bundle, envelope, projected)
    if entry == 'D1_EFFECTS':
        return projected
    return transfer.project_reading(bundle, projected, entry)[0]


from cfm_id.workflows.legacy_network.evidence_entries import identify


def normalize(bundle, provider, entry, envelope=None):
    system, user = make_request(bundle, entry, envelope)
    raw = provider.generate_json(system_prompt=system, user_prompt=user)
    return identify(bundle, raw, entry, envelope)
