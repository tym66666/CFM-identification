"""Independent review binding for the explicit fixed-assignment contract.

Source locations establish provenance, not semantic entailment. A reviewer must
separately confirm that the selected original-study statements support the
reported allocation facts. This record does not approve A4 observables, A5
assumptions, a theorem route, or an identification result. It is not a digital
signature and does not authenticate a reviewer outside the calling application.

Existing intent and scientific reviews remain mandatory downstream. No review
flag is inferred from model output, a source ID, or a compatible typed design.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator

from cfm_id_llm.schemas import StrictModel
from cfm_id_bridge.scientific_binding import sha
from .source_locations import build_catalog, resolve_sources


_Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
_FACT_FIELDS = {
    'mechanism', 'fixed_count', 'maximum_count', 'uniform_subset_declared',
    'reported_conflict', 'source_ids',
}


class ReviewedAssignmentFacts(StrictModel):
    """Separately supplied semantic review, bound to the complete submission."""

    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    contract: Literal['fixed-assignment']
    bundle_sha256: _Hash
    wrapper_sha256: _Hash
    reading_sha256: _Hash
    catalog_sha256: _Hash
    resolved_sources_sha256: _Hash
    packet_sha256: _Hash
    context_sha256: _Hash
    studies_sha256: dict[str, _Hash] = Field(min_length=1)
    reviewer: str = Field(min_length=3, max_length=200)
    evidence: str = Field(min_length=12, max_length=2000)
    reviewed_original_assignment_and_sources: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_original_assignment_and_sources', 'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        # Literal[True] alone can accept the integer 1 through Python equality.
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_BOOLEAN_REVIEW_REQUIRED')
        return value


def _inspection(bundle, wrapper):
    from .fixed_assignment import inspect_assignment

    if (type(wrapper) is not dict or set(wrapper) != {'reading', 'reported_assignment'}
            or type(wrapper['reading']) is not dict
            or type(wrapper['reported_assignment']) is not dict
            or set(wrapper['reported_assignment']) != _FACT_FIELDS):
        raise ValueError('EXACT_FIXED_ASSIGNMENT_WRAPPER_REQUIRED')
    inspection = inspect_assignment(bundle, wrapper)
    if inspection.get('state') != 'REVIEW_REQUIRED':
        raise ValueError('ORIGINAL_ASSIGNMENT_NOT_READY_FOR_REVIEW')
    facts = inspection['facts']
    if hasattr(facts, 'model_dump'):
        facts = facts.model_dump(mode='json')
    if type(facts) is not dict or set(facts) != _FACT_FIELDS:
        raise ValueError('EXACT_VALIDATED_ASSIGNMENT_FACTS_REQUIRED')
    catalog = build_catalog(bundle['documents'])
    resolved = resolve_sources(bundle['documents'], facts['source_ids'])
    if resolved != inspection['resolved_sources']:
        raise ValueError('SOURCE_RESOLUTION_DISAGREES')
    return facts, catalog, resolved


def _studies(context):
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21

    bindings = context.core_port.bindings
    if not bindings:
        raise ValueError('BOUND_FIXED_POLICY_STUDY_REQUIRED')
    studies = {}
    for qid, binding in bindings.items():
        if not isinstance(qid, str) or not qid or type(binding.inquiry) is not FixedPolicyInquiryV21:
            raise ValueError('EXACT_FIXED_POLICY_INQUIRY_REQUIRED')
        studies[qid] = binding.inquiry.study
    return studies


class ReviewedQuestionBoundAssignmentFacts(ReviewedAssignmentFacts):
    """Explicitly approves the original ID-bound candidate and its source view."""
    contract: Literal['fixed-assignment-id']
    question_binding_sha256: _Hash
    resolved_wrapper_sha256: _Hash


def assignment_worksheet(bundle, wrapper, packet, context, *, contract='fixed-assignment'):
    """Create bindings only; no reviewer identity, evidence, or approval flags.

    The entire study is bound in addition to the existing context snapshot:
    fixed-policy target coordinates alone do not include the assignment law.
    """
    from .intent_submission import _context_snapshot

    source_view = None
    inspected = wrapper
    if contract == 'fixed-assignment-id':
        from .question_bound_assignment import resolve_reading
        inspected, source_view = resolve_reading(bundle, wrapper)
    elif contract != 'fixed-assignment':
        raise ValueError('UNKNOWN_ASSIGNMENT_REVIEW_CONTRACT')
    _, catalog, resolved = _inspection(bundle, inspected)
    context_snapshot = _context_snapshot(context)
    studies = _studies(context)
    sheet = dict(
        contract=contract, bundle_sha256=sha(bundle),
        wrapper_sha256=sha(wrapper), reading_sha256=sha(wrapper['reading']),
        catalog_sha256=sha(catalog), resolved_sources_sha256=sha(resolved),
        packet_sha256=sha(packet), context_sha256=sha(context_snapshot),
        studies_sha256={qid: sha(study) for qid, study in studies.items()},
    )
    if source_view is not None:
        sheet.update(question_binding_sha256=sha(source_view), resolved_wrapper_sha256=sha(inspected))
    return sheet


def _compatible_studies(bundle, wrapper, facts, studies):
    from pfn_pipeline.network_inquiry_shadow import NetworkStudyContextV17
    from pfn_pipeline._internal.identification.schemas import CompleteRandomizationDesignV1

    nodes = bundle['node_order']
    if (type(nodes) is not list or not nodes or len(set(nodes)) != len(nodes)
            or any(not isinstance(node, str) or not node for node in nodes)):
        raise ValueError('EXACT_PUBLIC_ROSTER_REQUIRED')
    count, maximum = facts['fixed_count'], facts['maximum_count']
    if (facts['mechanism'] != 'FIXED_QUOTA_RANDOM'
            or facts['uniform_subset_declared'] is not True
            or facts['reported_conflict'] is not False
            or type(count) is not int or not 0 <= count <= len(nodes)):
        raise ValueError('COMPLETE_UNIFORM_FIXED_QUOTA_FACTS_REQUIRED')
    if maximum is not None and (type(maximum) is not int or not count <= maximum <= len(nodes)):
        raise ValueError('FIXED_QUOTA_CONFLICTS_WITH_REPORTED_LIMIT')
    questions = wrapper['reading'].get('questions')
    if type(questions) is not dict or not set(studies).issubset(questions):
        raise ValueError('ASSIGNMENT_REVIEW_QUERY_BINDING_MISMATCH')
    if len({sha(study) for study in studies.values()}) != 1:
        raise ValueError('MULTIPLE_ORIGINAL_STUDIES_REQUIRE_SEPARATE_FACT_REVIEWS')
    for study in studies.values():
        if (type(study) is not NetworkStudyContextV17
                or study.observation_regime != 'experimental'
                or list(study.node_order) != nodes):
            raise ValueError('EXPERIMENTAL_STUDY_AND_ROSTER_REQUIRED')
        design = study.design()
        if type(design) is not CompleteRandomizationDesignV1:
            raise ValueError('UNIFORM_COMPLETE_RANDOMIZATION_DESIGN_REQUIRED')
        if type(design.m) is not int or design.m != count:
            raise ValueError('REPORTED_AND_TYPED_FIXED_COUNTS_DISAGREE')


def validate_assignment_review(bundle, wrapper, packet, context, record, *, contract='fixed-assignment'):
    """Revalidate a separate review against current facts, sources and science.

    A successful receipt allows the caller to continue the existing review
    chain; this function never invokes Core or grants scientific admission.
    """
    record_type = (ReviewedAssignmentFacts if contract == 'fixed-assignment' else
        ReviewedQuestionBoundAssignmentFacts if contract == 'fixed-assignment-id' else None)
    if record_type is None or type(record) is not record_type:
        raise ValueError('SEPARATE_ASSIGNMENT_FACTS_REVIEW_REQUIRED')
    explicit = {'reviewer', 'evidence', 'reviewed_original_assignment_and_sources', 'synthetic_fixture'}
    if not explicit.issubset(record.model_fields_set):
        raise ValueError('EXPLICIT_ASSIGNMENT_FACTS_REVIEW_REQUIRED')
    reviewed = record_type.model_validate(record.model_dump(mode='python'))
    expected = assignment_worksheet(bundle, wrapper, packet, context, contract=contract)
    if any(getattr(reviewed, key) != value for key, value in expected.items()):
        raise ValueError('ASSIGNMENT_FACTS_REVIEW_STALE')
    inspected = wrapper
    if contract == 'fixed-assignment-id':
        from .question_bound_assignment import resolve_reading
        inspected, _ = resolve_reading(bundle, wrapper)
    facts, _, resolved = _inspection(bundle, inspected)
    studies = _studies(context)
    _compatible_studies(bundle, inspected, facts, studies)
    return dict(
        status='ASSIGNMENT_FACTS_REVIEWED', contract=contract,
        review_sha256=sha(reviewed), facts_sha256=sha(facts),
        resolved_sources_sha256=sha(resolved), studies_sha256=expected['studies_sha256'],
        reviewer=reviewed.reviewer, scientific_approval=False, core_called=False,
    )
