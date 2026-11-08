"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import cfm_id.workflows.legacy_network.condition_evidence_base as evidence
import cfm_id.workflows.legacy_network.d1_submission as d1
import cfm_id.workflows.legacy_network.core_peers_base as peers
import cfm_id.workflows.legacy_network.core_peers_staged as staged
import cfm_id.workflows.legacy_network.remaining_transfer as transfer


def base_request(bundle, entry, envelope=None):
    if entry == 'STAGED_CORE_PEERS':
        return staged.target_request(bundle, envelope)
    if entry == 'D1_EFFECTS':
        return d1.make_request(bundle)
    return transfer.make_request(bundle, entry)


def make_request(bundle, entry, envelope=None):
    return evidence.augment_request(*base_request(bundle, entry, envelope))


def identify(bundle, raw, entry, envelope=None, packet=None, *, context=None, synthetic_protocol_selected=False):
    def consumer(projected):
        options = dict(context=context, synthetic_protocol_selected=synthetic_protocol_selected)
        if entry == 'STAGED_CORE_PEERS':
            return peers.identify_submission(bundle, staged.compose_reading(bundle, envelope, projected), packet, **options)
        if entry == 'D1_EFFECTS':
            return d1.identify_submission(bundle, projected, packet, **options)
        return transfer.identify_reading(bundle, projected, entry, packet, **options)
    return evidence.guarded_dispatch(bundle, raw, consumer)
