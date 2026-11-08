"""v2.9.2 independent, human-reviewed business-target coordinates.

This contract is NOT generated from, signed by, or automatically approved by a
formal mathematical inquiry. It is supplied separately by the business reviewer
and must be checked before invoking a causal identification theorem.

It cannot prove that a human correctly understood arbitrary natural language.
It does ensure the approved science cannot silently CHANGE independently
confirmed policy assignments, arm conditions, or effect coordinates.
"""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from cfm_id_llm.schemas import StrictModel
from cfm_id_llm.orchestration_schemas import canonical_sha256
from .scientific_binding import scientific_target_coordinates, canonical_data, sha

SHA_PATTERN = r'^[0-9a-f]{64}$'
REQUIRED_COORDINATES = {
    'RANDOMIZED_ARM': frozenset(('classification','node_order','node_id','own_treatment','exposure_state')),
    'FIXED_POLICY': frozenset(('classification','node_order','assignment','unit_weights')),
    'FINITE_POLICY': frozenset(('classification','probabilities','component_target_digests')),
}
EFFECT_KEYS = frozenset(('classification','kind','node_weights','reference_exposure',
                          'comparison_exposure','spillover_own_treatment'))


class ApprovedBusinessIntentV292(StrictModel):
    schema_version: Literal['causal-idfm-approved-business-intent-v2.9.2'] = 'causal-idfm-approved-business-intent-v2.9.2'
    case_id: str = Field(min_length=1)
    query_id: str = Field(pattern=r'^q[1-9][0-9]{0,2}$')
    input_sha256: str = Field(pattern=SHA_PATTERN)
    draft_sha256: str = Field(pattern=SHA_PATTERN)
    target_sha256: str = Field(pattern=SHA_PATTERN)
    business_review_sha256: str = Field(pattern=SHA_PATTERN)
    business_quote: str = Field(min_length=4)
    # Explicitly curated from the business request, NOT copied from typed science.
    binding_coordinates: dict
    business_reviewer: str = Field(min_length=3)
    independent_business_review_evidence: str = Field(min_length=12)
    reviewer_confirmed_coordinates: Literal[True]  # no default approval

    @model_validator(mode='after')
    def check_explicit_contract(self):
        c=self.binding_coordinates
        if type(c) is not dict or not all(isinstance(k,str) for k in c):
            raise ValueError('BUSINESS_COORDINATES_TYPED_OBJECT_REQUIRED')
        category=c.get('classification')
        required=REQUIRED_COORDINATES.get(category,EFFECT_KEYS)
        if not required.issubset(c):
            raise ValueError('BUSINESS_COORDINATES_INCOMPLETE')
        if set(c) != required:
            raise ValueError('BUSINESS_COORDINATES_UNREVIEWED_EXTRA_KEYS')
        if category=='FIXED_POLICY':
            nodes=c['node_order']; z=c['assignment']; weights=c['unit_weights']
            if not nodes or len(nodes)!=len(z) or len(weights)!=len(nodes):
                raise ValueError('BUSINESS_POLICY_LENGTH_MISMATCH')
            if len(set(nodes))!=len(nodes) or any(type(t) is not int or t not in (0,1) for t in z):
                raise ValueError('BUSINESS_POLICY_INVALID_BINARY_ASSIGNMENT')
        if category=='RANDOMIZED_ARM':
            if c['node_id'] not in c['node_order'] or type(c['own_treatment']) is not int or c['own_treatment'] not in (0,1):
                raise ValueError('BUSINESS_ARM_COORDINATES_INVALID')
        return self


def verify_business_intent_v292(contract: ApprovedBusinessIntentV292, reviewed, q, inquiry):
    """Fail closed on provenance, business quote, coordinates, and query identity."""
    report=reviewed.report
    if (contract.case_id!=report.case_id or contract.query_id!=q.query_id or
        contract.input_sha256!=report.input_sha256 or contract.draft_sha256!=report.draft_sha256 or
        contract.target_sha256!=canonical_sha256(q.target) or
        contract.business_review_sha256!=sha(reviewed.human_review)):
        raise ValueError('V292_BUSINESS_INTENT_STALE_OR_UNRELATED')
    quotes=[e.quote for e in q.business_goal.evidence]
    if contract.business_quote not in quotes:
        raise ValueError('V292_BUSINESS_INTENT_QUOTE_MISMATCH')
    if contract.business_reviewer!=reviewed.human_review.reviewed_by:
        raise ValueError('V292_INDEPENDENT_BUSINESS_REVIEWER_MISMATCH')
    actual=scientific_target_coordinates(inquiry)
    expected=contract.binding_coordinates
    if (expected['classification']!=actual.get('classification') or
       any(canonical_data(v)!=canonical_data(actual.get(k)) for k,v in expected.items())):
        raise ValueError('V292_BUSINESS_INTENT_COORDINATES_MISMATCH')
    return sha(contract)
