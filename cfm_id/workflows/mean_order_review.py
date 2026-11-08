"""Opt-in full-wire review binding around the existing synthetic business chain.

This record is an independently supplied assertion, not identity authentication,
a digital signature, semantic truth, a mathematical certificate, or production
admission. It never creates a legacy review or changes the candidate.
"""
from copy import deepcopy
from typing import Literal
from pydantic import field_validator
from cfm_id_bridge.scientific_binding import sha
from cfm_id import mean_order_business as legacy
from cfm_id.bounded_policy_contract import StrictRecord, Hash, Text
from cfm_id_llm.readers import mean_order as protocol

VERSION='factored-order-review-1'

class ReviewedFactoredReading(StrictRecord):
    version: Literal['factored-order-review-1']
    protocol_version: Literal['factored-order-reading-1']
    bundle_sha256: Hash
    full_wire_sha256: Hash
    canonical_sha256: Hash
    projection_receipt_sha256: Hash
    legacy_review_sha256: Hash
    reviewer: Text
    evidence: Text
    reviewed_full_wire_semantics_and_sources: Literal[True]
    reviewed_projection_and_losses: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_full_wire_semantics_and_sources',
                     'reviewed_projection_and_losses','synthetic_fixture',mode='before')
    @classmethod
    def explicit_true(cls,v):
        if type(v) is not bool or v is not True:
            raise ValueError('EXPLICIT_INDEPENDENT_FACTORED_REVIEW_REQUIRED')
        return v

def worksheet(bundle,wire,*,legacy_review):
    """A binding snapshot only; it never checks or grants scientific permission."""
    if type(legacy_review) is not legacy.ReviewedMeanOrderBusiness:
        raise ValueError('EXACT_LEGACY_REVIEW_REQUIRED')
    old=legacy.ReviewedMeanOrderBusiness.model_validate(legacy_review.model_dump())
    canonical=protocol.to_canonical(bundle,wire)
    receipt=protocol.projection_receipt(bundle,wire,canonical)
    if old.bundle_sha256!=sha(bundle) or old.candidate_sha256!=sha(canonical):
        raise ValueError('LEGACY_REVIEW_DOES_NOT_BIND_THIS_PROJECTION')
    return dict(version=VERSION,protocol_version=protocol.VERSION,bundle_sha256=sha(bundle),
        full_wire_sha256=sha(wire),canonical_sha256=sha(canonical),
        projection_receipt_sha256=sha(receipt),legacy_review_sha256=sha(old))

def validate_review(bundle,wire,*,legacy_review,review):
    if type(review) is not ReviewedFactoredReading:
        raise ValueError('EXACT_TYPED_FACTORED_REVIEW_REQUIRED')
    current=worksheet(bundle,wire,legacy_review=legacy_review)
    r=ReviewedFactoredReading.model_validate(review.model_dump())
    if any(getattr(r,k)!=v for k,v in current.items()):
        raise ValueError('FACTORED_REVIEW_STALE_OR_DIFFERENT')
    return sha(r)

def prepare(bundle,wire,*,query_id,science=None,packet=None,context=None):
    public=dict(entry='EXPERIMENTAL_FACTORED_MEAN_ORDER_BUSINESS',factored_version=VERSION,
        wire_candidate=deepcopy(wire),factored_review_checked=False)
    try:
        canonical=protocol.to_canonical(bundle,wire)
        receipt=protocol.projection_receipt(bundle,wire,canonical)
        out=legacy.prepare(bundle,canonical,query_id=query_id,science=science,packet=packet,context=context)
        return dict(out,**public,projection_receipt=receipt)
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(public,state='CHECK_BLOCKED',reason_code='INVALID_FACTORED_READING',
            core_called=False,bounded_backend_called=False,bounded_certificate_replayed=False,
            scientific_approval=False,production_admission=False,estimation_handoff_allowed=False,
            business_route_registered=False)

def submit(bundle,wire,*,query_id,science=None,packet=None,context=None,
           assignment_review=None,review=None,factored_review=None,synthetic_protocol_selected=False):
    # Work on a snapshot so mutable caller dictionaries cannot change halfway
    # between the new binding check and the existing binding check.
    bundle=deepcopy(bundle);wire=deepcopy(wire)
    out=prepare(bundle,wire,query_id=query_id,science=science,packet=packet,context=context)
    if out['state']!='REVIEW_REQUIRED':return out
    if synthetic_protocol_selected is not True or review is None or factored_review is None:
        return dict(out,reason_code='SEPARATE_FACTORED_AND_LEGACY_REVIEWS_REQUIRED')
    try:
        token=validate_review(bundle,wire,legacy_review=review,review=factored_review)
        result=legacy.submit(bundle,out['reading_candidate'],query_id=query_id,science=science,
            packet=packet,context=context,assignment_review=assignment_review,review=review,
            synthetic_protocol_selected=True)
        return dict(result,entry=out['entry'],factored_version=VERSION,
            wire_candidate=deepcopy(wire),projection_receipt=out['projection_receipt'],
            factored_review_checked=True,factored_review_sha256=token)
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(out,state='CHECK_BLOCKED',reason_code='FACTORED_REVIEW_BINDING_REJECTED')
