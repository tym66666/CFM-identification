"""Case-independent input compiler for the finite bounded-policy contract.

Public text goes to the existing reader. Scientific declarations and external
review remain separate. Compilation creates no identification result and cannot
replace any of the existing business, A4/A5, assignment or certificate reviews.
Only explicitly selected synthetic research protocols are currently admitted.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator

from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context,
)
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline.identification_policy_r2 import (
    REQUIRED, declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency,
)
from pfn_pipeline._internal.identification.schemas import Assumption
from . import question_bound_assignment as ids
from . import bounded_policy as existing_entry
from .bounded_policy_contract import (
    VERSION, MAX_N, Hash, Text, StrictRecord, ExactMean, NodeBounds,
    BoundedMeanInformation, BoundedPolicyUnavailable, validate_model, fail,
)

INTAKE_VERSION = 'bounded-policy-intake-1'
ALL_ARRANGEMENTS = 'ALL_BINARY_ASSIGNMENTS_ALL_STUDY_NODES'
CONDITION_NAMES = frozenset(REQUIRED) | {'mean_signature_sufficiency'}


class StudyDeclaration(StrictRecord):
    network_id: str = Field(min_length=1)
    node_order: list[str] = Field(min_length=1)
    undirected_edges: list[list[str]]
    treatment_variable: str = Field(min_length=1)
    outcome_variable: str = Field(min_length=1)
    outcome_kind: Literal['binary', 'continuous']
    context_reference: str = Field(min_length=1)
    design: str
    fixed_count: int = Field(ge=0)
    graph_timing: str
    grouping: str
    protocol_provenance: Text
    network_provenance: Text


class ConditionDeclaration(StrictRecord):
    name: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    statement: Text
    evidence: Text


class InformationDeclaration(StrictRecord):
    source_id: str = Field(min_length=1)
    operator: str
    availability: str
    information_scope: str
    model_scope: str
    values: list[ExactMean]
    bounds: list[NodeBounds]
    bounds_kind: Literal['CONDITIONAL_MEAN', 'ALMOST_SURE_OUTCOME']
    bounds_scope: str
    outcome_definition: Text
    outcome_unit: str = Field(min_length=1)
    outcome_period: str = Field(min_length=1)
    a4_provenance: Text
    bounds_provenance: Text


class BoundedPolicyDeclaration(StrictRecord):
    version: Literal['bounded-policy-intake-1']
    study: StudyDeclaration
    information: InformationDeclaration
    conditions: list[ConditionDeclaration]
    # Explicitly inventory additional restrictions; never silently discard them.
    additional_constraints: list[Text]


class ReviewedBoundedDeclaration(StrictRecord):
    version: Literal['bounded-policy-intake-1']
    query_id: str
    bundle_sha256: Hash
    reading_sha256: Hash
    declaration_sha256: Hash
    target_coordinates_sha256: Hash
    reviewer: Text
    evidence: Text
    condition_decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]
    reviewed_business_target: Literal[True]
    reviewed_network_and_original_design: Literal[True]
    reviewed_exact_a4_information: Literal[True]
    reviewed_bounds_and_outcome_semantics: Literal[True]
    reviewed_complete_model_without_extra_constraints: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_business_target', 'reviewed_network_and_original_design',
        'reviewed_exact_a4_information', 'reviewed_bounds_and_outcome_semantics',
        'reviewed_complete_model_without_extra_constraints', 'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_EXTERNAL_REVIEW_REQUIRED')
        return value


@dataclass(frozen=True)
class CompiledBoundedContract:
    inquiry: FixedPolicyInquiryV21
    information: BoundedMeanInformation
    review_receipt: dict


def _declaration(value):
    if type(value) is BoundedPolicyDeclaration:
        value = value.model_dump()
    if type(value) is not dict:
        fail('CHECK_BLOCKED', 'DECLARATION_OBJECT_REQUIRED')
    return BoundedPolicyDeclaration.model_validate(value)


def _inspect(bundle, raw, query_id, declaration):
    d = _declaration(declaration)
    view = ids.preview(bundle, raw)
    if set(bundle['question_slots']) != {query_id}:
        fail('UNSUPPORTED', 'SINGLE_FIXED_POLICY_QUERY_REQUIRED')
    if view['state'] != 'REVIEW_REQUIRED':
        fail(view['state'], view.get('reason_code') or 'BUSINESS_READING_NOT_READY')
    if view.get('assignment_review', {}).get('state') != 'REVIEW_REQUIRED':
        fail('NEEDS_INPUT', 'ORIGINAL_ASSIGNMENT_FACTS_REQUIRED')
    coordinates = view['proposed_targets'][query_id]
    st, info = d.study, d.information
    nodes = st.node_order
    if (len(set(nodes)) != len(nodes) or any(not n.strip() for n in nodes)
            or nodes != bundle['node_order']):
        fail('CHECK_BLOCKED', 'PUBLIC_AND_DECLARED_ROSTER_MISMATCH')
    if len(nodes) > MAX_N:
        fail('UNSUPPORTED', 'FINITE_REPLAY_NODE_LIMIT_EXCEEDED')
    if (st.design != 'complete_randomization_binary_v1'
            or st.grouping != 'strict_majority_ties_low'):
        fail('UNSUPPORTED', 'BOUNDED_D2_E1_FINITE_DOMAIN_REQUIRED')
    if st.graph_timing != 'DECLARED_PRETREATMENT_FIXED':
        fail('NEEDS_INPUT', 'FIXED_PRETREATMENT_GRAPH_REQUIRED')
    if st.fixed_count > len(nodes) or st.fixed_count != raw['reported_assignment']['fixed_count']:
        fail('CHECK_BLOCKED', 'DECLARED_AND_REPORTED_QUOTA_DISAGREE')
    edges = st.undirected_edges
    if (any(len(e) != 2 or e[0] == e[1] or not set(e) <= set(nodes) for e in edges)
            or len({frozenset(e) for e in edges}) != len(edges)):
        fail('CHECK_BLOCKED', 'EXPLICIT_SIMPLE_UNDIRECTED_GRAPH_REQUIRED')
    names = [c.name for c in d.conditions]
    if len(set(names)) != len(names):
        fail('CHECK_BLOCKED', 'DUPLICATE_SCIENTIFIC_CONDITION')
    if set(names) - CONDITION_NAMES or d.additional_constraints:
        fail('UNSUPPORTED', 'ADDITIONAL_CONSTRAINTS_REQUIRE_JOINT_SOLVER')
    if CONDITION_NAMES - set(names):
        fail('NEEDS_INPUT', 'EXPLICIT_SCIENTIFIC_CONDITIONS_REQUIRED')
    for c in d.conditions:
        scope = ALL_ARRANGEMENTS if c.name == 'mean_signature_sufficiency' else 'STUDY_CONTEXT'
        if c.scope != scope:
            fail('NEEDS_INPUT', 'SCIENTIFIC_CONDITION_SCOPE_INCOMPLETE')
    if (info.operator != 'NODE_SIGNATURE_MEANS'
            or info.information_scope != 'EXACT_LISTED_SIGNATURE_MEANS_ONLY'
            or info.model_scope != 'SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY'):
        fail('UNSUPPORTED', 'MEAN_ONLY_MODEL_REQUIRED_NO_INFORMATION_DOWNGRADE')
    if info.availability != 'EXACT_POPULATION_VALUE':
        fail('NEEDS_INPUT', 'EXACT_POPULATION_VALUES_REQUIRED_NO_SAMPLE_SUBSTITUTION')
    if info.bounds_scope != 'ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT':
        fail('NEEDS_INPUT', 'ALL_ARRANGEMENT_SCIENTIFIC_BOUNDS_REQUIRED')
    cells = [(v.node, v.own, v.exposure) for v in info.values]
    if (not cells or len(set(cells)) != len(cells)
            or any(c[0] not in nodes for c in cells)):
        fail('NEEDS_INPUT', 'UNIQUE_EXPLICIT_A4_MEAN_LIST_REQUIRED')
    if len(info.bounds) != len(nodes) or {b.node for b in info.bounds} != set(nodes):
        fail('NEEDS_INPUT', 'EXPLICIT_ALL_NODE_BOUNDS_REQUIRED')
    sheet = dict(version=INTAKE_VERSION, query_id=query_id, bundle_sha256=sha(bundle),
        reading_sha256=sha(raw), declaration_sha256=sha(d),
        target_coordinates_sha256=sha(coordinates))
    return d, coordinates, sheet


def prepare(bundle, raw, *, query_id, declaration):
    """An unapproved worksheet; never runs a solver or manufactures review flags."""
    out = dict(intake_version=INTAKE_VERSION, state='REVIEW_REQUIRED',
        core_called=False, bounded_backend_called=False, scientific_approval=False,
        production_admission=False, estimation_handoff_allowed=False)
    try:
        d, coordinates, sheet = _inspect(bundle, raw, query_id, declaration)
        out.update(worksheet=sheet, proposed_target=deepcopy(coordinates),
            declared_conditions=[c.model_dump() for c in d.conditions],
            declaration=d.model_dump(), reason_code='INDEPENDENT_DECLARATION_REVIEW_REQUIRED')
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_BOUNDED_DECLARATION_OR_READING')
    return out


def compile_reviewed(bundle, raw, *, query_id, declaration, review=None,
                     synthetic_protocol_selected=False):
    """Translate explicit reviewed declarations into existing typed objects.

This returns inputs, not POINT/PARTIAL. The old submission chain must still
approve the complete business/science context and replay the resulting proof.
"""
    d, coordinates, sheet = _inspect(bundle, raw, query_id, declaration)
    if synthetic_protocol_selected is not True or type(review) is not ReviewedBoundedDeclaration:
        fail('REVIEW_REQUIRED', 'SEPARATE_DECLARATION_REVIEW_REQUIRED')
    r = ReviewedBoundedDeclaration.model_validate(review.model_dump())
    if any(getattr(r, k) != v for k, v in sheet.items()):
        fail('CHECK_BLOCKED', 'DECLARATION_REVIEW_STALE')
    if set(r.condition_decisions) != CONDITION_NAMES:
        fail('REVIEW_REQUIRED', 'EACH_SCIENTIFIC_CONDITION_REQUIRES_SEPARATE_DECISION')
    if 'REJECTED' in r.condition_decisions.values():
        fail('CHECK_BLOCKED', 'SCIENTIFIC_CONDITION_NOT_ADMITTED')
    if 'PENDING' in r.condition_decisions.values():
        fail('REVIEW_REQUIRED', 'SCIENTIFIC_CONDITION_REVIEW_PENDING')
    s, data = d.study, d.information
    study = declare_network_study(network_id=s.network_id, node_order=tuple(s.node_order),
        undirected_edges=tuple(tuple(e) for e in s.undirected_edges),
        treatment_variable=s.treatment_variable, outcome_variable=s.outcome_variable,
        outcome_kind=s.outcome_kind, context_reference=s.context_reference,
        observation_regime='experimental', assignment_design={'kind':s.design, 'm':s.fixed_count},
        protocol_provenance=s.protocol_provenance, network_provenance=s.network_provenance,
        graph_timing_claim=s.graph_timing)
    # Actual model coordinates are preserved; no reference target is substituted.
    target = fixed_policy_target_from_context(study, tuple(coordinates['assignment']),
        unit_weights=tuple(coordinates['unit_weights']), authority='TRUSTED_FIXTURE')
    signature = declare_policy_signature(study, grouping=s.grouping)
    licenses = {c.name: Assumption(name=c.name, source='demo_specification',
        confirmed=True, status='ADMITTED', evidence=[c.evidence, r.evidence],
        details=c.statement + ' / Scope: ' + c.scope) for c in d.conditions}
    sufficiency = admit_mean_signature_sufficiency(study, signature,
        covered_nodes=tuple(s.node_order), assumption=licenses['mean_signature_sufficiency'])
    source = declare_signature_population_source(study, signature, source_id=data.source_id,
        operator=data.operator, outcome_nodes=tuple(s.node_order), admission='ADMITTED',
        availability=data.availability, provenance=data.a4_provenance,
        signature_cells=tuple((v.node,v.own,v.exposure) for v in data.values))
    inquiry = FixedPolicyInquiryV21(study, target, tuple(licenses[n] for n in sorted(REQUIRED)),
        r2_signature=signature, r2_sufficiency=sufficiency, r2_sources=(source,))
    payload = data.model_dump(exclude={'operator'})
    payload.update(version=VERSION, inquiry_sha256=sha(inquiry), source_sha256=sha(source))
    info = BoundedMeanInformation.model_validate(payload)
    validate_model(inquiry, info)
    return CompiledBoundedContract(inquiry, info, dict(sheet,
        review_sha256=sha(r), inquiry_sha256=sha(inquiry), information_sha256=sha(info),
        approval_kind='EXTERNAL_SYNTHETIC_ASSERTION_NOT_IDENTITY_AUTHENTICATION',
        identification_completed=False, production_admission=False))


def submit(bundle, raw, *, query_id, declaration, declaration_review=None,
           packet=None, context=None, bounded_review=None, submission_review=None,
           assignment_review=None, synthetic_protocol_selected=False):
    """Feed the compiled contract through every existing review and replay gate."""
    out = prepare(bundle, raw, query_id=query_id, declaration=declaration)
    if out['state'] != 'REVIEW_REQUIRED':
        return out
    try:
        compiled = compile_reviewed(bundle, raw, query_id=query_id,
            declaration=declaration, review=declaration_review,
            synthetic_protocol_selected=synthetic_protocol_selected)
        if context is None:
            fail('REVIEW_REQUIRED', 'EXISTING_BUSINESS_AND_SCIENCE_REVIEW_CHAIN_REQUIRED')
        if sha(context.core_port.bindings[query_id].inquiry) != sha(compiled.inquiry):
            fail('CHECK_BLOCKED', 'COMPILED_AND_INDEPENDENTLY_REVIEWED_INQUIRY_DIFFER')
        result = existing_entry.submit(bundle, raw, query_id=query_id, packet=packet,
            context=context, information=compiled.information, bounded_review=bounded_review,
            submission_review=submission_review, assignment_review=assignment_review,
            synthetic_protocol_selected=synthetic_protocol_selected)
        result['declaration_review_receipt'] = compiled.review_receipt
        return result
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='BOUNDED_DECLARATION_REVIEW_REJECTED')
    return out


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Prepare an unapproved bounded-policy worksheet; no API calls.')
    for name in ('bundle','candidate','declaration','query-id','output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    try:
        def read(path):
            return json.loads(Path(path).read_text(encoding='utf-8-sig'))
        result = prepare(read(args.bundle), read(args.candidate), query_id=args.query_id,
                         declaration=read(args.declaration))
        with Path(args.output).open('x', encoding='utf8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(2, 'INPUT_OR_OUTPUT_ERROR; check inputs and use a new output path.\n')
    print(json.dumps({'state':result['state'], 'http_calls':0, 'core_called':False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
