"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import cfm_id.workflows.legacy_network.frozen_reading_base as prior
import cfm_id.workflows.legacy_network.condition_evidence as evidence
import cfm_id.workflows.legacy_network.evidence_entries as entries
import cfm_id.workflows.legacy_network.staged_d1_d2 as staged


make_request=prior.make_request


def identify(bundle,raw,entry,envelope=None):
    if prior.cross_field_issues(raw):return prior.identify(bundle,raw,entry,envelope)
    def consumer(projected):
        if entry=='STAGED_CORE_PEERS':return entries.peers.identify_submission(bundle,entries.staged.compose_reading(bundle,envelope,projected))
        if entry=='D2_ARM' and envelope is not None:projected=staged.compose(bundle,entry,envelope,projected)
        if entry=='D1_EFFECTS':return entries.d1.identify_submission(bundle,projected)
        return entries.transfer.identify_reading(bundle,projected,entry)
    r=evidence.guarded_dispatch(bundle,raw,consumer)
    r.update(frozen_reading_version='business-frozen-reading-v0.55.1',cross_field_issues=[])
    return r
