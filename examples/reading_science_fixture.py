"""Explicit synthetic science for the frozen reading regression cases.

This is a test reviewer, never a production approval service. Expected business
coordinates and scientific conditions are authored separately from model output.
Only the three cases in SCIENTIFIC_PROTOCOLS.json can receive this test review.
"""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

from cfm_id.business_entry import preview
from cfm_id.intent_submission import (
    ReviewedIntentSubmissionV057, reviewed_projection, submission_worksheet,
)
from cfm_id_bridge.scientific_binding import actual_scientific_licenses
from evaluation.business_core_pilot_base import canonical_hash, target_coordinates
from evaluation.business_d1_submission import project, compile_inquiry
from examples.materials_candidate_fixture import (
    BusinessCase, SemanticClaim, EvidenceQuote, TargetDraft, TargetKind,
    DraftProblemSpec, UnitsVariablesDraft, StructureDraft, InformationDesignDraft,
    AssignmentFamily, PopulationInformationLevel, BusinessInquiryV010,
    MultiQueryDraftV010, QuerySemanticsV010, audit_business_quality,
    BusinessQueryReviewV011, approve_multiquery, v29_review_from_v011,
    ScientificAdmissionV29, canonical_sha256, formal_target_fingerprint_v29,
    independently_review_fixture, independently_confirm_business_intent_v292,
    independently_review_evidence_v292, FormalQueryBindingV29,
    unapproved_crosswalk_worksheet_v012, ApprovedBusinessMathCrosswalkV012,
    RealCoreCoveragePortV012, MaterialsCandidateApprovalV035,
    ReviewedMaterialsContextV035,
)

DATA = Path(__file__).resolve().parents[1] / 'evaluation/reading_accuracy_cases'
PROTOCOL_FILE = DATA / 'references/SCIENTIFIC_PROTOCOLS.json'


def protocol(name):
    """A separately frozen specification; no model result is an input."""
    all_protocols = json.loads(PROTOCOL_FILE.read_text(encoding='utf8'))
    if name not in all_protocols['cases']:
        raise ValueError('NO_SCIENTIFIC_PROTOCOL_FOR_THIS_CASE')
    return deepcopy(all_protocols['cases'][name])


def public_bundle(name):
    return json.loads((DATA / 'public' / name / 'public_bundle.json').read_text(encoding='utf8'))


def expected_design(p):
    return dict(design='逐单位抽签', declared_independent=True,
        probability_source='design_probabilities.csv', exposure=p['exposure'],
        outcome='service_metric', units=len(p['node_order']),
        probabilities={n: '1/2' for n in p['node_order']})


def expected_target(p):
    return dict(kind='comparison', nodes=p['population'], aggregation='equal_mean',
        situation=[1, 1], reference=[0, 1], remaining='original_randomization',
        treated_nodes=None, unresolved=[])


def expected_coordinates(p):
    return dict(classification='EffectsInquiryV21', kind='DIRECT',
        node_weights=[[n, str(Fraction(1, len(p['population'])))] for n in p['population']],
        reference_exposure=1, comparison_exposure=1, spillover_own_treatment=1)


def expected_terms(p):
    return {(n, a, 1): Fraction(1 if a else -1, len(p['population']))
            for n in p['population'] for a in (0, 1)}


def synthetic_context(name, bundle, candidate):
    """Review a saved live reading against a separately defined test protocol.

    Callers must still explicitly select this protocol at submit(). No approval
    is inferred by the normal business preview or supplied to the first LLM.
    """
    p = protocol(name)
    if canonical_hash(bundle) != p['public_bundle_sha256']:
        raise ValueError('FROZEN_PUBLIC_MATERIALS_CHANGED')
    out = preview(bundle, candidate, 'D1_EFFECTS')
    if out['state'] != 'REVIEW_REQUIRED':
        raise ValueError('READING_NOT_READY_FOR_SCIENTIFIC_REVIEW')
    projected = reviewed_projection(bundle, candidate, 'D1_EFFECTS')
    _, design, targets = project(bundle, projected)
    if (list(bundle['question_slots']) != ['q1'] or design != expected_design(p)
            or [target_coordinates(t) for t in targets] != [expected_target(p)]):
        raise ValueError('INDEPENDENT_BUSINESS_PROTOCOL_MISMATCH')
    science_refs = dict(population_information=p['a4']['reference'],
                        causal_licenses=p['a5']['reference'])
    packet = dict(mode='SYNTHETIC_BENCHMARK_ONLY', bundle_sha256=canonical_hash(bundle),
                  study=expected_design(p), science=science_refs,
                  independent_protocol_sha256=canonical_hash(p))

    text = '\n'.join(bundle['documents'].values())
    case = BusinessCase(case_id='SYNTHETIC_READING_SCIENCE_' + name, business_question=text)

    def claim(quote):
        if not quote or quote not in text:
            raise ValueError('PUBLIC_QUOTE_NOT_FOUND')
        return SemanticClaim(value=quote, basis='EXPLICIT_TEXT',
            evidence=[EvidenceQuote(source_id='business_question', quote=quote)])

    goal = bundle['question_slots']['q1']
    goal_lines = bundle['documents'][bundle['active_goal_document']].splitlines()
    study_lines = bundle['documents']['study_protocol.md'].splitlines()
    target = TargetDraft(kind=TargetKind.DIRECT_EFFECT, description=claim(goal))
    shared = DraftProblemSpec(target=target,
        units_variables=UnitsVariablesDraft(analysis_unit=claim(p['unit_word']),
            treatment=claim(p['tool_word']), outcome=claim('service_metric')),
        structure=StructureDraft(unit_network=claim('无向协作边'),
            network_pretreatment_status=claim('试点前冻结的无向协作边'),
            exposure_mapping=claim(study_lines[3])),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.INDEPENDENT_BERNOULLI,
            assignment_law=claim(study_lines[1]),
            population_information_level=PopulationInformationLevel.UNRESOLVED))
    query = BusinessInquiryV010(query_id='q1', target=target, business_goal=claim(goal),
        semantics=QuerySemanticsV010(target_population=claim(goal_lines[0]),
            aggregation=claim(goal_lines[0]), intervention=claim(goal), comparator=claim(goal),
            neighbor_exposure=claim(goal), standardization_distribution=claim(goal_lines[-1])))
    quality = audit_business_quality(case,
        MultiQueryDraftV010(shared_draft=shared, primary_query_id='q1', queries=[query]),
        provider='SYNTHETIC_REVIEW_OF_SAVED_LIVE_READING', prompt_version='material-reading-science')
    review = BusinessQueryReviewV011(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.draft_sha256, confirmed_query_ids=['q1'],
        reviewed_by='Synthetic protocol test reviewer', decision='CONFIRMED',
        review_note='Compared the actual saved model response with separately specified target and science; synthetic only')
    reviewed = approve_multiquery(case, quality.legacy_audit,
        v29_review_from_v011(review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    inquiry = compile_inquiry(design, targets[0], bundle, science_refs)
    if sorted(x['name'] for x in actual_scientific_licenses(inquiry)) != sorted(p['a5']['licenses']):
        raise ValueError('SCIENTIFIC_LICENSE_SCOPE_MISMATCH')
    if (inquiry.a4_source.operator != p['a4']['operator']
            or set(inquiry.a4_source.arm_cells) != {
                (n, a, e) for n in p['node_order'] for a in (0, 1) for e in (0, 1)}):
        raise ValueError('POPULATION_INFORMATION_SCOPE_MISMATCH')
    science = ScientificAdmissionV29(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256, query_id='q1',
        target_sha256=canonical_sha256(target), formal_family='R1A_EFFECT',
        formal_target_fingerprint=formal_target_fingerprint_v29(inquiry),
        math_target_description=goal, math_target_crosswalk_confirmed=True,
        scientific_reviewer='Synthetic protocol test scientist',
        evidence_reference=p['protocol_id'],
        a4_population_operator_reference=science_refs['population_information'],
        a4_scientifically_admitted=True, a5_assumption_reference=science_refs['causal_licenses'],
        a5_scientifically_admitted=True,
        scientific_review_note='Explicit hypothetical population arm means and five declared licenses. No exposure sufficiency or sample-to-population upgrade.',
        is_synthetic_fixture=True)
    science = independently_review_fixture(science, inquiry, reviewed, 'q1', 'R1A_COMPOSITION')
    intent = independently_confirm_business_intent_v292(reviewed, 'q1', expected_coordinates(p),
        evidence='Separately frozen population, equal weights, own 1-minus-0 at exposure 1 and original design standardization')
    binding = FormalQueryBindingV29(science, inquiry, intent,
        independently_review_evidence_v292(science, inquiry))
    crosswalk = unapproved_crosswalk_worksheet_v012(case=case, quality=quality,
        business_review=review, query_id='q1', formal_binding=binding,
        reviewer='Synthetic protocol crosswalk reviewer',
        evidence='Explicit independent protocol compared to the saved model reading; sources, licenses and target all match')
    crosswalk.update(reviewer_confirmed_business_to_math=True, reviewer_confirmed_a4_a5_and_route=True)
    port = RealCoreCoveragePortV012(bindings={'q1': binding},
        crosswalks={'q1': ApprovedBusinessMathCrosswalkV012.model_validate(crosswalk)})
    approval = MaterialsCandidateApprovalV035(bundle_sha256=canonical_hash(bundle),
        model_draft_sha256=canonical_hash(projected), science_packet_sha256=canonical_hash(packet),
        gateway_case_sha256=canonical_sha256(case), gateway_quality_sha256=canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(), reviewed_query_ids=['q1'], reviewed_a4_levels={},
        reviewer='Synthetic protocol materials reviewer',
        review_evidence='Actual saved response matched separately declared public target and hypothetical scientific protocol',
        reviewed_materials_to_gateway=True, synthetic_fixture=True)
    context = ReviewedMaterialsContextV035(case, quality, review, port, approval)
    outer = fresh_outer_review(bundle, candidate, packet, context)
    return packet, context, outer


def fresh_outer_review(bundle, candidate, packet, context):
    """Explicit test-only review record; inner scientific checks still apply."""
    return ReviewedIntentSubmissionV057(
        **submission_worksheet(bundle, candidate, 'D1_EFFECTS', packet, context),
        reviewer='Synthetic intent and conditions reviewer',
        evidence='Synthetic test protocol independently checks target coordinates and scientific scope',
        reviewed_intent_and_conditions=True, synthetic_fixture=True)
