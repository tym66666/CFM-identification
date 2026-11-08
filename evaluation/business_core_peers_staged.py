"""Make the history-versus-target distinction explicit without repairing outputs."""
from .business_core_peers_staged_base import bind_study, validate_envelope, compose_reading, study_request
from .business_core_peers_staged_base import target_request as previous_request
from .business_core_peers_base import preview_submission

VERSION='business-core-peers-staged-v0.52.3'


from cfm_id.workflows.legacy_network.core_peers_staged import target_request


def normalize_targets(bundle,envelope,provider):
    system,user=target_request(bundle,envelope)
    candidate=provider.generate_json(system_prompt=system,user_prompt=user)
    result=preview_submission(bundle,compose_reading(bundle,envelope,candidate))
    result.update(reading_prompt_version=VERSION,study_envelope=envelope,target_candidate=candidate)
    return result
