"""Small explicit research-route interface, not a new mathematical Core.

Adapters retain their native contracts, review types and independent verifiers.
No discovery, keyword dispatch, scientific approval, or estimation handoff.
"""
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Protocol
from cfm_id_bridge.scientific_binding import sha


@dataclass(frozen=True)
class RouteCapability:
    route_id: str
    model_family: str
    target_kind: str
    information_kind: str
    proof_kind: str
    scope: str


class ResearchRoute(Protocol):
    capability: RouteCapability
    def prepare(self,problem:Any)->dict: ...
    def submit(self,problem:Any,review:Any)->dict: ...
    def certificate(self,result:dict)->dict|None: ...
    def replay(self,problem:Any,certificate:dict)->bool: ...
    def claim(self,certificate:dict)->dict: ...
    def verify_claim(self,certificate:dict,claim:dict)->bool: ...


STOPS={'NEEDS_INPUT','REVIEW_REQUIRED','UNSUPPORTED','CHECK_BLOCKED'}
PROVED={'POINT','PARTIAL','INCOMPATIBLE'}


def run_route(adapter:ResearchRoute,problem,*,review=None,research_protocol_selected=False):
    """Execute only the caller's explicit adapter; never create a review object.

Conformance checks are defense in depth, not proof of an adapter's soundness or
reviewer identity. Native mathematical verification remains mandatory.
"""
    out=dict(route_id=adapter.capability.route_id,model_family=adapter.capability.model_family,
        state='CHECK_BLOCKED',mathematical_claim=None,certificate=None,
        independent_replay=False,backend_called=False,production_admission=False,
        estimation_handoff_allowed=False)
    try:
        snapshot=deepcopy(problem);identity=sha(snapshot);out['problem_sha256']=identity
        prepared=adapter.prepare(snapshot)
        if prepared.get('state') not in STOPS or any(prepared.get(k) for k in
            ('backend_called','core_called','bounded_backend_called','certificate_replayed',
             'bounded_certificate_replayed','scientific_approval','production_admission','estimation_handoff_allowed')):
            raise ValueError('PREPARE_CROSSED_REVIEW_BOUNDARY')
        if adapter.certificate(prepared) is not None:raise ValueError('PREPARE_RETURNED_CERTIFICATE')
        if sha(snapshot)!=identity:raise ValueError('PREPARE_MUTATED_INPUT')
        out['worksheet']=deepcopy(prepared.get('worksheet'))
        if prepared['state']!='REVIEW_REQUIRED' or research_protocol_selected is not True or review is None:
            out.update(state=prepared['state'],reason_code=prepared.get('reason_code'))
            return out
        native=adapter.submit(snapshot,deepcopy(review))
        out['native_result']=deepcopy(native)
        out['backend_called']=any(native.get(k) is True for k in ('backend_called','core_called','bounded_backend_called'))
        if sha(snapshot)!=identity:raise ValueError('SUBMIT_MUTATED_INPUT')
        if native.get('production_admission') is not False or native.get('estimation_handoff_allowed') is not False:
            raise ValueError('RESEARCH_ROUTE_PROMOTED_TO_PRODUCTION')
        state=native.get('state');certificate=adapter.certificate(native)
        if state in STOPS:
            if certificate is not None:raise ValueError('STOP_STATE_RETURNED_CERTIFICATE')
            out.update(state=state,reason_code=native.get('reason_code'));return out
        if state not in PROVED or type(certificate) is not dict:raise ValueError('MISSING_TYPED_MATHEMATICAL_EVIDENCE')
        evidence=deepcopy(certificate)
        claim=adapter.claim(evidence)
        if type(claim) is not dict or claim.get('kind')!=state:raise ValueError('CLAIM_STATE_MISMATCH')
        if adapter.verify_claim(evidence,claim) is not True:raise ValueError('CLAIM_EVIDENCE_MISMATCH')
        if adapter.replay(snapshot,evidence) is not True:raise ValueError('INDEPENDENT_REPLAY_FAILED')
        if sha(snapshot)!=identity or evidence!=certificate:raise ValueError('REPLAY_MUTATED_INPUT_OR_EVIDENCE')
        out.update(state=state,mathematical_claim=claim,certificate=evidence,independent_replay=True)
        return out
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        out.update(state='CHECK_BLOCKED',reason_code=str(exc),mathematical_claim=None,certificate=None,independent_replay=False)
        return out
