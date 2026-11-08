"""v2.9.1 independently reviewable, exact business/scientific binding contract.

An approval is a *recorded, separately supplied scientific assertion*, never an
LLM inference, a signature, or empirical proof of exchangeability.  Compare the
actual immutable target/A4/A5 scope on EACH invocation and fail closed.
"""
from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from fractions import Fraction
from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from cfm_id_llm.schemas import StrictModel
from cfm_id_llm.orchestration_schemas import canonical_sha256
from pfn_pipeline._internal.identification.schemas import IdentificationSpec

_SHA = r"^[0-9a-f]{64}$"


def canonical_data(value: Any):
    """Strict canonical serialization, with no arbitrary class imports or code execution."""
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, Enum):
        return canonical_data(value.value)
    if hasattr(value, 'model_dump'):
        return canonical_data(value.model_dump(mode='json'))
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: canonical_data(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ValueError('Nonstring field in typed source snapshot')
        return {k:canonical_data(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_data(v) for v in value]
    raise ValueError(f'Unsupported typed scientific snapshot value: {type(value).__name__}')


def sha(value):
    return canonical_sha256(canonical_data(value))


def scientific_target_coordinates(inquiry) -> dict:
    """Exact A1 coordinates, independently extracted from core-owned typed input."""
    from pfn_pipeline.identification_business import (
        ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21, FinitePolicyInquiryV21,
        ObservationalPolicyInquiryV23, ObservationalEffectsInquiryV26,
        ObservationalExposureAdjustedEffectsInquiryV27P2,
        ObservationalNodewiseAdjustedEffectsInquiryV28,
    )
    if type(inquiry) is ArmInquiryV21:
        spec = IdentificationSpec.model_validate(inquiry.task.identification_spec)
        net=spec.network_exposure
        q=spec.query
        group=spec.randomized_network_arm_theorem_contract
        return dict(classification='RANDOMIZED_ARM',node_order=list(net.node_ids),
            node_id=q.target_node_id,own_treatment=q.own_treatment_value,
            exposure_state=q.exposure_value,exposure_grouping=group.grouping,
            exposure_core=canonical_data(group.core_collaborators),
            treatment=q.treatment,outcome=q.outcome,context=spec.support_domain.get('context_symbol'),
            assignment_design=canonical_data(group.design))
    if type(inquiry) in (FixedPolicyInquiryV21,ObservationalPolicyInquiryV23):
        return dict(classification='FIXED_POLICY',node_order=list(inquiry.target.node_order),
            assignment=list(inquiry.target.policy_assignment),
            unit_weights=list(inquiry.target.unit_weights),
            treatment=inquiry.study.treatment_variable,outcome=inquiry.target.outcome,
            context=inquiry.target.context,study_scope=inquiry.study.shared_scope_digest)
    if type(inquiry) is FinitePolicyInquiryV21:
        return dict(classification='FINITE_POLICY',
            probabilities=list(inquiry.policy_probabilities),
            component_target_digests=[c.target_fingerprint for c in inquiry.components])
    if type(inquiry) in (EffectsInquiryV21,ObservationalEffectsInquiryV26,
                        ObservationalExposureAdjustedEffectsInquiryV27P2,
                        ObservationalNodewiseAdjustedEffectsInquiryV28):
        if len(inquiry.requests)!=1:
            raise ValueError('Only a single effect can bind to a single business target')
        req=inquiry.requests[0]
        study=getattr(inquiry,'study',None)
        return dict(classification=type(inquiry).__name__,
            study_scope=study.shared_scope_digest if study else inquiry.batch.batch_sha256,
            kind=req.kind,node_weights=[[n,str(w)] for n,w in req.node_weights],
            reference_exposure=req.reference_exposure,
            comparison_exposure=req.comparison_exposure,
            spillover_own_treatment=req.spillover_own_treatment,
            exposure_fingerprint=(inquiry.signature.signature_fingerprint if hasattr(inquiry,'signature') else None))
    raise TypeError('Unknown typed inquiry for approved A1 coordinates')


def _raw_a4_sources(inquiry):
    from pfn_pipeline.identification_business import ArmInquiryV21
    if type(inquiry) is ArmInquiryV21:
        spec=IdentificationSpec.model_validate(inquiry.task.identification_spec)
        objects=spec.information_signature.objects
        return [o.randomized_arm_observable for o in objects if o.randomized_arm_observable is not None]
    found=[]
    for attr in ('a4_source','source'):
        if hasattr(inquiry,attr):
            found.append(getattr(inquiry,attr))
    for attr in ('r1b_sources','r2_sources'):
        if hasattr(inquiry,attr):
            found.extend(getattr(inquiry,attr))
    if hasattr(inquiry,'components'):
        for c in inquiry.components:
            found.extend(getattr(c,'sources',()))
    return [x for x in found if x is not None]


def _raw_a5(inquiry):
    from pfn_pipeline.identification_business import ArmInquiryV21
    if type(inquiry) is ArmInquiryV21:
        return list(IdentificationSpec.model_validate(inquiry.task.identification_spec).assumptions)
    found=list(getattr(inquiry,'assumptions',()))
    for attr in ('r2_sufficiency','sufficiency','license'):
        x=getattr(inquiry,attr,None)
        if x is not None:
            found.append(x)
    if hasattr(inquiry,'batch'):
        spec=IdentificationSpec.model_validate(inquiry.batch.template.identification_spec)
        found.extend(spec.assumptions)
    if hasattr(inquiry,'components'):
        for c in inquiry.components:
            found.extend(getattr(c,'assumptions',()))
    return found


def actual_scientific_sources(inquiry) -> tuple[dict, ...]:
    entries=[]
    for x in _raw_a4_sources(inquiry):
        if isinstance(x,dict):
            id_=x.get('source_id')
            operator=x.get('operator')
        else:
            id_=getattr(x,'source_id',None)
            operator=getattr(x,'operator',None)
        if not id_ or not operator:
            raise ValueError('Typed A4 source lacks source_id/operator')
        entries.append(dict(source_id=str(id_),operator=str(operator),typed_source_sha256=sha(x)))
    entries.sort(key=lambda x:(x['source_id'],x['operator'],x['typed_source_sha256']))
    if not entries:
        raise ValueError('At least one separately approved typed A4 operator required')
    return tuple(entries)


def actual_scientific_licenses(inquiry) -> tuple[dict, ...]:
    records=[]
    for x in _raw_a5(inquiry):
        name=x.get('name') if isinstance(x,dict) else getattr(x,'name',None)
        if not name:
            name='SCOPED_LICENSE:'+type(x).__name__
        records.append(dict(name=str(name),typed_assumption_sha256=sha(x)))
    records.sort(key=lambda x:(x['name'],x['typed_assumption_sha256']))
    if not records:
        raise ValueError('At least one explicitly scoped typed A5 assumption required')
    return tuple(records)


class ApprovedScienceBindingV291(StrictModel):
    """Structurally reviewed A1/A4/A5, supplied *separately* from the LLM.

    Missing/legacy v2.9 review MUST NOT certify POINT. Reviewer claims are not
    digitally signed or evidence that causal assumptions hold in the real world.
    """
    schema_version: Literal['causal-idfm-scientific-binding-v2.9.1']='causal-idfm-scientific-binding-v2.9.1'
    business_review_sha256: str = Field(pattern=_SHA)
    approved_target_sha256: str = Field(pattern=_SHA)
    approved_business_quote: str = Field(min_length=4,max_length=2000)
    approved_target_coordinates: dict
    approved_a4_reference: str = Field(min_length=8)
    approved_a4_sources: tuple[dict, ...] = Field(min_length=1)
    approved_a5_reference: str = Field(min_length=8)
    approved_a5_licenses: tuple[dict, ...] = Field(min_length=1)
    approved_theorem_route: str = Field(min_length=4,max_length=120)
    scope_digest: str = Field(pattern=_SHA)
    reviewer: str = Field(min_length=3,max_length=200)
    scientific_review_evidence: str = Field(min_length=8,max_length=700)
    reviewer_confirmed_exact_coordinates: Literal[True]
    reviewer_confirmed_sources_and_licenses: Literal[True]

    @model_validator(mode='after')
    def validate_structures(self):
        if any(set(x)!={'source_id','operator','typed_source_sha256'} or not x['source_id'] or
               not x['operator'] or not isinstance(x['typed_source_sha256'],str) or
               len(x['typed_source_sha256'])!=64 for x in self.approved_a4_sources):
            raise ValueError('Invalid typed A4 source binding')
        if any(set(x)!={'name','typed_assumption_sha256'} or not x['name'] or
               not isinstance(x['typed_assumption_sha256'],str) or
               len(x['typed_assumption_sha256'])!=64 for x in self.approved_a5_licenses):
            raise ValueError('Invalid typed A5 license binding')
        return self


def proposed_binding_snapshot_v291(inquiry, *, business_review_sha256: str,
                                   target_sha256: str, business_quote: str,
                                   a4_reference: str, a5_reference: str,
                                   theorem_route: str, reviewer: str, evidence: str):
    """Produce an *UNAPPROVED* structured review worksheet, never a license.

    The caller must independently check these coordinates and source documents,
    and separately submit an ApprovedScienceBindingV291. This helper does not
    validate that narrative semantics or external claims are correct.
    """
    coords=scientific_target_coordinates(inquiry)
    scope=sha({'coordinates':coords,'review':business_review_sha256,
               'target':target_sha256})
    return dict(business_review_sha256=business_review_sha256,
        approved_target_sha256=target_sha256,approved_business_quote=business_quote,
        approved_target_coordinates=coords,approved_a4_reference=a4_reference,
        approved_a4_sources=actual_scientific_sources(inquiry),
        approved_a5_reference=a5_reference,approved_a5_licenses=actual_scientific_licenses(inquiry),
        approved_theorem_route=theorem_route,scope_digest=scope,
        reviewer=reviewer,scientific_review_evidence=evidence)


def verify_approved_science_v291(admission, inquiry, reviewed, query):
    approval=admission.approved_scientific_binding
    if approval is None:
        raise ValueError('V291_STRUCTURED_SCIENTIFIC_BINDING_REQUIRED')
    if approval.business_review_sha256 != sha(reviewed.human_review):
        raise ValueError('V291_BUSINESS_REVIEW_BINDING_MISMATCH')
    if approval.approved_target_sha256 != canonical_sha256(query.target):
        raise ValueError('V291_REVIEWED_TARGET_BINDING_MISMATCH')
    if approval.approved_business_quote not in [e.quote for e in query.target.description.evidence]:
        raise ValueError('V291_BUSINESS_EVIDENCE_QUOTE_MISMATCH')
    actual=scientific_target_coordinates(inquiry)
    if canonical_data(approval.approved_target_coordinates)!=canonical_data(actual):
        raise ValueError('V291_BUSINESS_MATH_COORDINATES_MISMATCH')
    scope=sha({'coordinates':actual,'review':approval.business_review_sha256,
               'target':approval.approved_target_sha256})
    if approval.scope_digest!=scope:
        raise ValueError('V291_TARGET_SCOPE_BINDING_MISMATCH')
    if approval.approved_a4_reference!=admission.a4_population_operator_reference:
        raise ValueError('V291_A4_REVIEWED_REFERENCE_MISMATCH')
    if tuple(approval.approved_a4_sources)!=actual_scientific_sources(inquiry):
        raise ValueError('V291_TYPED_A4_SOURCE_MISMATCH')
    if approval.approved_a5_reference!=admission.a5_assumption_reference:
        raise ValueError('V291_A5_REVIEWED_REFERENCE_MISMATCH')
    if tuple(approval.approved_a5_licenses)!=actual_scientific_licenses(inquiry):
        raise ValueError('V291_TYPED_A5_LICENSE_MISMATCH')
    if approval.reviewer!=admission.scientific_reviewer:
        raise ValueError('V291_SCIENTIFIC_REVIEWER_MISMATCH')
    # Route-specific approval is checked after theorem runs as well. Never
    # silently substitute R3-signature for R3-full or R1b for R2.
    if approval.approved_theorem_route not in _family_routes(admission.formal_family):
        raise ValueError('V291_UNAPPROVED_THEOREM_ROUTE')
    if admission.formal_family=='R2_FIXED_POLICY':
        names={x['name'] for x in approval.approved_a5_licenses}
        if not any(x.startswith('SCOPED_LICENSE:MeanSignatureSufficiency') for x in names):
            raise ValueError('V291_R2_MEAN_SIGNATURE_LICENSE_REQUIRED')
    if admission.formal_family.startswith('R3_'):
        names={x['name'] for x in approval.approved_a5_licenses}
        if not ({'full_vector_conditional_exchangeability'}<=names or
                any('Scoped' in x for x in names)):
            raise ValueError('V291_R3_EXCHANGEABILITY_OR_SCOPED_LICENSE_REQUIRED')
    return approval


def _family_routes(family):
    return {
        'R1A_ARM':{'R1A_RANDOMIZED_ARM'},
        'R1A_EFFECT':{'R1A_COMPOSITION'},
        'R1B_FIXED_POLICY':{'R1B_FULL_ASSIGNMENT'},
        'R2_FIXED_POLICY':{'R2_MEAN_SIGNATURE'},
        'R1B_FINITE_POLICY':{'R1B_FINITE_POLICY'},
        'R3_POLICY':{'R3_FULL_ASSIGNMENT','R3_MEAN_SIGNATURE'},
        'R3_P_STANDARDIZED':{'R3_P_STANDARDIZED_EFFECTS'},
        'R3_EXPOSURE_ADJUSTED':{'R3_EXPOSURE_ADJUSTED_EFFECTS'},
        'R3_NODEWISE_ADJUSTED':{'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'},
    }[family]
