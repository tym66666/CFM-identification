"""Finite D2/E1 mean-box contract; declarations never grant scientific review.

This deliberately admits exact listed A4 means only. It cannot discard a full
law, a coupling restriction, unreviewed material, or a finite-sample uncertainty.
The theorem and its realization proof are in docs/BOUNDED_POLICY_MATH_ZH.md.
"""
from fractions import Fraction as F
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline.identification_policy_r2 import (
    _normalized_inputs, _validate_study_target, R2PolicyUnavailable, REQUIRED,
)
from pfn_pipeline._internal.identification.schemas import CompleteRandomizationDesignV1

VERSION = 'bounded-policy-mean-1'
MAX_N = 12  # Independent exhaustive replay is an explicit software domain.
Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Text = Annotated[str, Field(min_length=3, max_length=4000)]


class BoundedPolicyUnavailable(ValueError):
    def __init__(self, state, reason):
        self.state, self.reason = state, reason
        super().__init__(reason)


def fail(state, reason):
    raise BoundedPolicyUnavailable(state, reason)


def rational(value):
    # No float conversion, infinities, booleans or silent canonicalization.
    if type(value) is not str or not 0 < len(value) <= 100:
        raise ValueError('CANONICAL_RATIONAL_STRING_REQUIRED')
    try:
        q = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('FINITE_RATIONAL_REQUIRED') from exc
    if str(q) != value:
        raise ValueError('CANONICAL_RATIONAL_STRING_REQUIRED')
    return q


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True,
                              str_strip_whitespace=False)

    @field_validator('*')
    @classmethod
    def no_blank_strings(cls, value):
        if type(value) is str and not value.strip():
            raise ValueError('NONBLANK_DECLARATION_REQUIRED')
        return value


class ExactMean(StrictRecord):
    node: str
    own: int = Field(ge=0, le=1)
    exposure: int = Field(ge=0, le=1)
    value: str

    @field_validator('value')
    @classmethod
    def fraction(cls, v):
        rational(v)
        return v


class NodeBounds(StrictRecord):
    node: str
    lower: str
    upper: str

    @field_validator('lower', 'upper')
    @classmethod
    def fraction(cls, v):
        rational(v)
        return v


class BoundedMeanInformation(StrictRecord):
    version: Literal['bounded-policy-mean-1']
    inquiry_sha256: Hash
    source_id: str = Field(min_length=1, max_length=4000)
    source_sha256: Hash
    information_scope: Literal['EXACT_LISTED_SIGNATURE_MEANS_ONLY']
    model_scope: Literal['SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY']
    availability: Literal['EXACT_POPULATION_VALUE']
    values: list[ExactMean] = Field(min_length=1)
    bounds: list[NodeBounds] = Field(min_length=1)
    bounds_kind: Literal['CONDITIONAL_MEAN', 'ALMOST_SURE_OUTCOME']
    bounds_scope: Literal['ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT']
    outcome_definition: Text
    outcome_unit: str = Field(min_length=1, max_length=4000)
    outcome_period: str = Field(min_length=1, max_length=4000)
    a4_provenance: Text
    bounds_provenance: Text


class ReviewedBoundedPolicy(StrictRecord):
    version: Literal['bounded-policy-mean-1']
    query_id: str
    bundle_sha256: Hash
    reading_sha256: Hash
    context_sha256: Hash
    packet_sha256: Hash
    inquiry_sha256: Hash
    information_sha256: Hash
    reviewer: Text
    evidence: Text
    reviewed_complete_a4_information: Literal[True]
    reviewed_scientific_bounds_and_scope: Literal[True]
    reviewed_no_additional_coupling_constraints: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_complete_a4_information',
                     'reviewed_scientific_bounds_and_scope',
                     'reviewed_no_additional_coupling_constraints',
                     'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_INDEPENDENT_REVIEW_REQUIRED')
        return value


def validate_model(inquiry, information):
    """Shared input validation only; no support calculation or bound solving.

Existing R2 validation is reused without modifying it. The independent replay
shares this typed contract, but no solver, exposure classifier or count engine.
"""
    if type(inquiry) is not FixedPolicyInquiryV21 or type(information) is not BoundedMeanInformation:
        fail('CHECK_BLOCKED', 'TYPED_BOUNDED_MODEL_REQUIRED')
    info = BoundedMeanInformation.model_validate(information.model_dump())
    if info.inquiry_sha256 != sha(inquiry):
        fail('CHECK_BLOCKED', 'BOUNDED_INFORMATION_STALE')
    if inquiry.r1b_sources or len(inquiry.r2_sources) != 1:
        fail('UNSUPPORTED', 'EXACT_SINGLE_MEAN_INFORMATION_CONTRACT_REQUIRED')
    try:
        st, target, sig, suff, sources = _normalized_inputs(
            inquiry.study, inquiry.target, inquiry.r2_signature,
            inquiry.r2_sufficiency, inquiry.r2_sources, inquiry.assumptions)
        _validate_study_target(st, target, sig, suff)
    except R2PolicyUnavailable as exc:
        fail('NEEDS_INPUT', exc.reason_code)
    if (type(st.design()) is not CompleteRandomizationDesignV1
            or sig.grouping != 'strict_majority_ties_low'
            or len(st.node_order) > MAX_N):
        fail('UNSUPPORTED', 'BOUNDED_D2_E1_FINITE_DOMAIN_REQUIRED')
    if st.outcome_kind not in ('continuous', 'binary'):
        fail('UNSUPPORTED', 'OUTCOME_REALIZATION_NOT_ADAPTED')
    if (len(inquiry.assumptions) != len(REQUIRED)
            or {a.name for a in inquiry.assumptions} != set(REQUIRED)):
        fail('UNSUPPORTED', 'ADDITIONAL_A5_REQUIRES_JOINT_CONSTRAINT_SOLVER')
    if set(suff.covered_nodes) != set(st.node_order):
        fail('NEEDS_INPUT', 'ALL_MODEL_NODES_REQUIRE_MEAN_SUFFICIENCY')
    source = sources[0]
    if source.operator != 'NODE_SIGNATURE_MEANS':
        fail('UNSUPPORTED', 'FULL_LAW_CANNOT_BE_DOWNGRADED_TO_MEAN_BOX')
    if (source.availability != 'EXACT_POPULATION_VALUE'
            or source.admission not in ('ADMITTED', 'CERTIFIED')):
        fail('NEEDS_INPUT', 'REVIEWED_EXACT_POPULATION_MEANS_REQUIRED')
    if (source.study_scope_digest != st.shared_scope_digest
            or source.protocol_digest != st.protocol_digest
            or source.node_order != st.node_order
            or source.outcome != st.outcome_variable or source.context != st.context_reference
            or source.signature_fingerprint != sig.signature_fingerprint
            or info.source_id != source.source_id or info.source_sha256 != sha(source)):
        fail('CHECK_BLOCKED', 'EXACT_A4_SOURCE_SCOPE_REQUIRED')
    known = {(v.node, v.own, v.exposure): rational(v.value) for v in info.values}
    if len(known) != len(info.values) or set(known) != set(source.signature_cells):
        fail('NEEDS_INPUT', 'COMPLETE_EXACT_A4_VALUE_LIST_REQUIRED')
    bounds = {b.node: (rational(b.lower), rational(b.upper)) for b in info.bounds}
    if len(bounds) != len(info.bounds) or set(bounds) != set(st.node_order):
        fail('NEEDS_INPUT', 'EXPLICIT_ALL_NODE_BOUNDS_REQUIRED')
    if st.outcome_kind == 'binary':
        if info.bounds_kind == 'ALMOST_SURE_OUTCOME':
            # Bounds on a binary realization restrict {0,1}, not just its mean.
            # For example 1/4 <= Y <= 3/4 admits NO binary outcome, while the
            # same bounds on E[Y] are feasible. Do not conflate the contracts.
            allowed = {n: [v for v in (F(0), F(1)) if lo <= v <= hi]
                       for n, (lo, hi) in bounds.items()}
            if any(not values for values in allowed.values()):
                fail('INCOMPATIBLE', 'EMPTY_BINARY_OUTCOME_SUPPORT')
            bounds = {n: (min(values), max(values)) for n, values in allowed.items()}
        else:
            bounds = {n: (max(F(0), lo), min(F(1), hi)) for n, (lo, hi) in bounds.items()}
    if any(lo > hi for lo, hi in bounds.values()):
        fail('INCOMPATIBLE', 'EMPTY_BOUND_RANGE')
    if any(not bounds[n][0] <= value <= bounds[n][1] for (n, _, _), value in known.items()):
        fail('INCOMPATIBLE', 'A4_MEAN_OUTSIDE_SCIENTIFIC_BOUNDS')
    return st, target, known, bounds


def input_digest(inquiry, information):
    return sha(dict(version=VERSION, inquiry=inquiry, information=information))
