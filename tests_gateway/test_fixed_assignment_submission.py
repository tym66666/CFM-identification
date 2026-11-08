"""Fixed-assignment facts -> separate review -> existing Core integration.

All examples are independent synthetic fixtures. There is no API, key, or
local_results dependency, and no reference is substituted for a model reply.
Both mathematical invocation sites are observed, not only the bridge alias.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import json
import unittest
from unittest.mock import patch

import cfm_id_bridge.bridge as bridge
import pfn_pipeline.identification_business as core
from cfm_id import business_entry
from cfm_id.assignment_review import ReviewedAssignmentFacts, assignment_worksheet
from cfm_id.intent_submission import submit, submission_worksheet, ReviewedIntentSubmissionV057
from cfm_id.source_locations import build_catalog
from examples import intent_routes_fixture as routes
from examples import intent_target_variants_fixture as variants


CONTRACT = 'fixed-assignment'


def assignment_sources(bundle):
    """The independently authored experiment line, not the future target."""
    line = bundle['documents']['study.txt'].splitlines()[2]
    found = [sid for sid, value in build_catalog(bundle['documents']).items()
             if value['doc_id'] == 'study.txt' and value['text'].rstrip('\r\n') == line]
    if len(found) != 1:
        raise AssertionError('EXACT_INDEPENDENT_DESIGN_LINE_REQUIRED')
    return found


def wrapper(bundle, reading, count):
    return dict(reading=deepcopy(reading), reported_assignment=dict(
        mechanism='FIXED_QUOTA_RANDOM', fixed_count=count, maximum_count=None,
        uniform_subset_declared=True, reported_conflict=False,
        source_ids=assignment_sources(bundle)))


def approved_assignment(bundle, raw, packet, context):
    return ReviewedAssignmentFacts(**assignment_worksheet(bundle, raw, packet, context),
        reviewer='Independent synthetic assignment reviewer',
        evidence='Checked original experimental rule, exact source locations and independently frozen typed design',
        reviewed_original_assignment_and_sources=True, synthetic_fixture=True)


def quota_full_fixture():
    """Independent R1b example: uniform two of five and a supported full list."""
    f = routes
    nodes = tuple('ABCDE')
    goal = '问题1：下周只让A和D使用排班工具，B、C、E不用。五个小组平均按时完成件数是多少？每组权重相同。'
    lines = [
        '有A、B、C、D、E五个小组，研究排班工具与按时完成件数。',
        '处理前冻结的无向协作边为A—B、B—C、C—D、D—E，没有其他边。',
        '原试验每轮从五个小组均匀随机选两个使用排班工具，其余三组不用，全部十份两组名单等概率。',
        '合作对象严格超过一半使用工具记为高暴露，其余为低；这个分组不排除其他人的影响。',
        '仅为合成业务说明，有限样本没有被声明为已知总体信息。',
    ]
    bundle = dict(case_id='FIXED_ASSIGNMENT_R1B_SYNTHETIC', node_order=list(nodes),
                  documents={'study.txt': '\n'.join(lines), 'goal.txt': goal},
                  question_slots={'q1': goal})
    assignment = (1, 0, 0, 1, 0)
    reading = dict(intents={'q1': dict(kind='水平', quote=goal)}, questions={'q1': dict(
        first=dict(zip(nodes, assignment)), second=None, population=list(nodes), aggregation='等权平均')})
    study = f.declare_network_study(network_id=bundle['case_id'], node_order=nodes,
        undirected_edges=tuple(zip(nodes[:-1], nodes[1:])), treatment_variable='tool',
        outcome_variable='completed', outcome_kind='continuous', context_reference='W',
        observation_regime='experimental', assignment_design={'kind': 'complete_randomization_binary_v1', 'm': 2},
        protocol_provenance=lines[2], network_provenance=lines[1], graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    target = f.fixed_policy_target_from_context(study, assignment, authority='TRUSTED_FIXTURE')
    inquiry = f.FixedPolicyInquiryV21(study, target, f._assumptions(), r1b_sources=(f._full_source(study),))
    coords = dict(classification='FIXED_POLICY', node_order=list(nodes), assignment=list(assignment), unit_weights=['1/5']*5)
    text = '\n'.join(bundle['documents'].values())
    case = f.BusinessCase(case_id=bundle['case_id'], business_question=text)

    def claim(quote):
        if quote not in text:
            raise AssertionError('SYNTHETIC_QUOTE_NOT_IN_BUNDLE')
        return f.SemanticClaim(value=quote, basis='EXPLICIT_TEXT',
            evidence=[f.EvidenceQuote(source_id='business_question', quote=quote)])

    target_draft = f.TargetDraft(kind=f.TargetKind.FIXED_POLICY_VALUE, description=claim(goal))
    shared = f.DraftProblemSpec(target=target_draft,
        units_variables=f.UnitsVariablesDraft(analysis_unit=claim(lines[0]), treatment=claim('排班工具'), outcome=claim('按时完成件数')),
        structure=f.StructureDraft(unit_network=claim(lines[1]), network_pretreatment_status=claim(lines[1]), exposure_mapping=claim(lines[3])),
        information_design=f.InformationDesignDraft(assignment_family=f.AssignmentFamily.COMPLETE_RANDOMIZATION,
            assignment_law=claim(lines[2]), population_information_level=f.PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=claim(lines[4])))
    query = f.BusinessInquiryV010(query_id='q1', target=target_draft, business_goal=claim(goal),
        semantics=f.QuerySemanticsV010(target_population=claim(goal), intervention=claim(goal),
                                      aggregation=claim(goal), policy_assignment=claim(goal)))
    quality = f.audit_business_quality(case, f.MultiQueryDraftV010(shared_draft=shared, primary_query_id='q1', queries=[query]),
        provider='INDEPENDENT_SYNTHETIC_ASSIGNMENT_TEST', prompt_version='fixed-assignment-test')
    business_review = f.BusinessQueryReviewV011(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.draft_sha256, confirmed_query_ids=['q1'], reviewed_by='Independent synthetic reviewer',
        decision='CONFIRMED', review_note='The target is A and D treated with five equal weights; no model facts used as science')
    reviewed = f.approve_multiquery(case, quality.legacy_audit,
        f.v29_review_from_v011(business_review, legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science = f.ScientificAdmissionV29(case_id=case.case_id, input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256, query_id='q1', target_sha256=f.canonical_sha256(target_draft),
        formal_family='R1B_FIXED_POLICY', formal_target_fingerprint=f.formal_target_fingerprint_v29(inquiry),
        math_target_description=goal, math_target_crosswalk_confirmed=True, scientific_reviewer='Independent synthetic scientist',
        evidence_reference='FIXED_ASSIGNMENT_TEST_PROTOCOL', a4_population_operator_reference='FIXED_ASSIGNMENT_TEST_A4',
        a4_scientifically_admitted=True, a5_assumption_reference='FIXED_ASSIGNMENT_TEST_A5', a5_scientifically_admitted=True,
        scientific_review_note='Independent hypothetical uniform quota, consistency and population operator; not production approval',
        is_synthetic_fixture=True)
    science = f.independently_review_fixture(science, inquiry, reviewed, 'q1', 'R1B_FULL_ASSIGNMENT')
    intent = f.independently_confirm_business_intent_v292(reviewed, 'q1', coords,
        evidence='Independent complete target list and equal population weights')
    binding = f.FormalQueryBindingV29(science, inquiry, intent, f.independently_review_evidence_v292(science, inquiry))
    sheet = f.unapproved_crosswalk_worksheet_v012(case=case, quality=quality, business_review=business_review,
        query_id='q1', formal_binding=binding, reviewer='Independent synthetic reviewer',
        evidence='Predeclared target, experiment law, symbolic population means and named licenses')
    sheet.update(reviewer_confirmed_business_to_math=True, reviewer_confirmed_a4_a5_and_route=True)
    port = f.RealCoreCoveragePortV012(bindings={'q1': binding},
        crosswalks={'q1': f.ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    packet = dict(mode='SYNTHETIC_BENCHMARK_ONLY', bundle_sha256=f.canonical_hash(bundle), queries={'q1': dict(
        study_sha256=f.sha(study), a4_sources_sha256=f.sha(f.actual_scientific_sources(inquiry)),
        a5_licenses_sha256=f.sha(f.actual_scientific_licenses(inquiry)),
        a4_reference=science.a4_population_operator_reference, a5_reference=science.a5_assumption_reference)})
    approval = f.MaterialsCandidateApprovalV035(bundle_sha256=f.canonical_hash(bundle), model_draft_sha256=f.canonical_hash(reading),
        science_packet_sha256=f.canonical_hash(packet), gateway_case_sha256=f.canonical_sha256(case),
        gateway_quality_sha256=f.canonical_sha256(quality), gateway_review_sha256=business_review.fingerprint(),
        reviewed_query_ids=['q1'], reviewed_a4_levels={}, reviewer='Independent synthetic reviewer',
        review_evidence='Independent target and scientific fixture checked without replacing any reading',
        reviewed_materials_to_gateway=True, synthetic_fixture=True)
    context = f.ReviewedMaterialsContextV035(case, quality, business_review, port, approval)
    outer = f.reviewed_submission(bundle, reading, 'FIXED_POLICY', packet, context)
    return bundle, wrapper(bundle, reading, 2), packet, context, outer


class FixedAssignmentSubmissionTests(unittest.TestCase):
    def fixture(self, route='r1b'):
        if route == 'r1b':
            return quota_full_fixture()
        if route == 'r2':
            bundle = routes.public_bundle('randomized_signature')
            reading = routes.gold_reading('randomized_signature')
            packet, context, review = routes.synthetic_context('randomized_signature', bundle, reading)
        elif route == 'zero':
            bundle = variants.public_bundle('signature_unsupported_all')
            reading = variants.gold_reading('signature_unsupported_all')
            packet, context, review = variants.synthetic_context('signature_unsupported_all', bundle, reading)
        else:
            raise AssertionError('UNKNOWN_TEST_ROUTE')
        return bundle, wrapper(bundle, reading, 4), packet, context, review

    def submit_observed(self, bundle, raw, packet_input, context_input, review, assignment_review, **overrides):
        before_bundle, before_raw = deepcopy(bundle), deepcopy(raw)
        direct_results = []
        original = core.identify_network_business_query

        def direct(inquiry):
            result = original(inquiry)
            direct_results.append(result)
            return result

        kwargs = dict(packet=packet_input, context=context_input, submission_review=review,
                      synthetic_protocol_selected=True, contract=CONTRACT, assignment_review=assignment_review)
        kwargs.update(overrides)
        with patch('socket.create_connection', side_effect=AssertionError('NO_NETWORK')), \
             patch.object(bridge, 'identify_network_business_query', wraps=bridge.identify_network_business_query) as first, \
             patch.object(core, 'identify_network_business_query', side_effect=direct) as second:
            result = submit(bundle, raw, 'FIXED_POLICY', **kwargs)
        self.assertEqual(bundle, before_bundle)
        self.assertEqual(raw, before_raw)
        for field in ('production_admission', 'estimation_called', 'policy_called', 'estimation_handoff_allowed'):
            self.assertFalse(result.get(field, False), field)
        self.assertEqual(result.get('candidate_model_calls', 0), 0)
        return result, (first.call_count, second.call_count), direct_results

    def assert_blocked(self, result, counts):
        self.assertNotEqual(result['state'], 'CORE_POINT')
        self.assertEqual(counts, (0, 0))
        self.assertFalse(result.get('core_called'))
        self.assertFalse(any(v.get('certificate_replayed') for v in result.get('query_views', [])))

    def test_r1b_r2_actual_core_replay_and_independent_support(self):
        for route, wanted in (('r1b', 'R1B_FULL_ASSIGNMENT'), ('r2', 'R2_MEAN_SIGNATURE')):
            with self.subTest(route=route):
                bundle, raw, packet, context, review = self.fixture(route)
                assignment_review = approved_assignment(bundle, raw, packet, context)
                result, counts, outcomes = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
                self.assertEqual(result['state'], 'CORE_POINT')
                self.assertEqual(counts, (1, 1))
                self.assertEqual(result['query_views'][0]['route'], wanted)
                self.assertTrue(result['query_views'][0]['certificate_replayed'])
                self.assertEqual(context.core_port.last_real_results['q1']['verification_level'], 'CORE_REPLAY_VERIFIED')
                mathematical = outcomes[0].result
                vectors = [z for z in product((0, 1), repeat=5) if sum(z) == (2 if route == 'r1b' else 4)]
                mass = Fraction(1, len(vectors))
                if route == 'r1b':
                    self.assertEqual(Fraction(mathematical.assignment_probability), mass)
                    self.assertEqual(mass, Fraction(1, 10))
                    self.assertEqual(tuple(mathematical.target.policy_assignment), (1, 0, 0, 1, 0))
                    self.assertEqual(dict(zip(mathematical.weighted_nodes, map(Fraction, mathematical.node_weights))),
                                     {n: Fraction(1, 5) for n in 'ABCDE'})
                else:
                    nodes = bundle['node_order']
                    adjacency = [{1, 2, 3, 4}, {0}, {0}, {0}, {0}]
                    probabilities = {n: sum((mass for z in vectors if z[i] == 1 and
                        2*sum(z[j] for j in adjacency[i]) > len(adjacency[i])), Fraction())
                        for i, n in enumerate(nodes)}
                    self.assertEqual(probabilities, {'hub': Fraction(4, 5), **{n: Fraction(3, 5) for n in nodes[1:]}})
                    self.assertEqual({c[0]: Fraction(p) for c, p in zip(mathematical.policy_node_classes, mathematical.node_class_support)}, probabilities)
                    self.assertEqual({c[0]: Fraction(w) for c, w in zip(mathematical.policy_node_classes, mathematical.node_weights)},
                                     {n: Fraction(1, 5) for n in nodes})

    def test_zero_support_reaches_core_without_false_certificate(self):
        bundle, raw, packet, context, review = self.fixture('zero')
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review,
            approved_assignment(bundle, raw, packet, context))
        self.assertEqual(counts, (1, 1))
        self.assertEqual(result['state'], 'UNSUPPORTED')
        self.assertEqual(result['query_views'][0]['reason_code'], 'ZERO_POLICY_SIGNATURE_SUPPORT')
        self.assertFalse(result['query_views'][0]['certificate_replayed'])
        # Independently, quota four and a treated hub leave three treated
        # neighbors. The target hub has only two: strict-majority low is absent.
        original_vectors = [z for z in product((0, 1), repeat=5) if sum(z) == 4]
        target = tuple(raw['reading']['questions']['q1']['first'][n] for n in bundle['node_order'])
        target_hub = (target[0], int(2*sum(target[1:]) > 4))
        support = sum((Fraction(1, 5) for z in original_vectors
                       if (z[0], int(2*sum(z[1:]) > 4)) == target_hub), Fraction())
        self.assertEqual(target_hub, (1, 0))
        self.assertEqual(support, 0)

    def test_missing_assignment_facts_cannot_use_ready_target_to_bypass_gate(self):
        bundle, raw, packet, context, review = self.fixture()
        old_assignment_review = approved_assignment(bundle, raw, packet, context)
        lines = bundle['documents']['study.txt'].splitlines()
        lines[2] = '原试验如何选取启用小组、每轮人数是否固定，尚未记录。'
        bundle['documents']['study.txt'] = '\n'.join(lines)
        raw['reported_assignment'].update(mechanism='NOT_FULLY_SPECIFIED', fixed_count=None,
            uniform_subset_declared=None, source_ids=assignment_sources(bundle))
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, old_assignment_review)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertTrue(any(v['state'] == 'REVIEW_REQUIRED' for v in result['query_views']))
        self.assertEqual(raw['reading']['questions']['q1']['first'], dict(zip('ABCDE', (1, 0, 0, 1, 0))))
        self.assert_blocked(result, counts)

    def test_unknown_target_keeps_known_values_even_with_complete_assignment_facts(self):
        bundle, raw, packet, context, review = self.fixture()
        old_assignment_review = approved_assignment(bundle, raw, packet, context)
        goal = '问题1：A和D用工具，B和E不用，C是否使用未定；评价五组等权平均按时完成件数。'
        bundle['question_slots']['q1'] = goal
        bundle['documents']['goal.txt'] = goal
        raw['reading']['intents']['q1']['quote'] = goal
        raw['reading']['questions']['q1']['first']['C'] = None
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, old_assignment_review)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertEqual(result['intent_condition_review']['q1']['missing_conditions'], ['first.C'])
        self.assertEqual(raw['reading']['questions']['q1']['first'], {'A': 1, 'B': 0, 'C': None, 'D': 1, 'E': 0})
        self.assert_blocked(result, counts)

    def test_maximum_only_preserves_cap_and_never_becomes_fixed_count(self):
        bundle, raw, packet, context, review = self.fixture()
        old_assignment_review = approved_assignment(bundle, raw, packet, context)
        lines = bundle['documents']['study.txt'].splitlines()
        lines[2] = '原试验每轮最多选两组使用工具，可能一组也不选；人数与名单的具体概率尚未记录。'
        bundle['documents']['study.txt'] = '\n'.join(lines)
        raw['reported_assignment'].update(mechanism='NOT_FULLY_SPECIFIED', fixed_count=None,
            maximum_count=2, uniform_subset_declared=None, source_ids=assignment_sources(bundle))
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, old_assignment_review)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertEqual(result['assignment_review']['facts']['maximum_count'], 2)
        self.assertIsNone(result['assignment_review']['facts']['fixed_count'])
        self.assertTrue(result['assignment_review']['questions'])
        self.assert_blocked(result, counts)

    def test_complete_reading_requires_new_assignment_review(self):
        bundle, raw, packet, context, review = self.fixture()
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, None)
        self.assert_blocked(result, counts)
        self.assertEqual(context.core_port.calls, [])

    def test_new_assignment_review_does_not_replace_existing_review_or_science(self):
        for missing in ('packet', 'context', 'submission_review', 'synthetic_protocol_selected'):
            with self.subTest(missing=missing):
                bundle, raw, packet, context, review = self.fixture()
                assignment_review = approved_assignment(bundle, raw, packet, context)
                result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review,
                    **{missing: False if missing == 'synthetic_protocol_selected' else None})
                self.assert_blocked(result, counts)

    def test_worksheet_is_not_assignment_approval(self):
        bundle, raw, packet, context, review = self.fixture()
        sheet = assignment_worksheet(bundle, raw, packet, context)
        with self.assertRaises(ValueError):
            ReviewedAssignmentFacts.model_validate(sheet)
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, sheet)
        self.assert_blocked(result, counts)

    def test_stale_wrapper_study_source_and_review_hashes_block(self):
        mutations = ('fixed_count', 'uniform', 'conflict', 'target', 'population', 'study_text', 'source_id', 'packet_hash', 'review_hash')
        for change in mutations:
            with self.subTest(change=change):
                bundle, raw, packet, context, review = self.fixture()
                assignment_review = approved_assignment(bundle, raw, packet, context)
                if change == 'fixed_count': raw['reported_assignment']['fixed_count'] = 3
                elif change == 'uniform': raw['reported_assignment']['uniform_subset_declared'] = False
                elif change == 'conflict': raw['reported_assignment']['reported_conflict'] = True
                elif change == 'target': raw['reading']['questions']['q1']['first']['B'] = 1
                elif change == 'population': raw['reading']['questions']['q1']['population'] = ['B']
                elif change == 'study_text': bundle['documents']['study.txt'] += '\n新增未经审核的说明。'
                elif change == 'source_id': raw['reported_assignment']['source_ids'] = ['src_' + '0'*64]
                elif change == 'packet_hash': packet['queries']['q1']['study_sha256'] = '0'*64
                else:
                    hash_fields = [k for k in type(assignment_review).model_fields if k.endswith('_sha256')]
                    self.assertTrue(hash_fields)
                    assignment_review = assignment_review.model_copy(update={hash_fields[0]: '0'*64})
                result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
                self.assert_blocked(result, counts)

    def test_fresh_outer_review_does_not_approve_changed_independent_target(self):
        bundle, raw, packet, context, _ = self.fixture()
        raw['reading']['questions']['q1']['population'] = ['B']
        context = replace(context, approval=context.approval.model_copy(update={
            'model_draft_sha256': routes.canonical_hash(raw['reading'])}))
        review = ReviewedIntentSubmissionV057(**submission_worksheet(bundle, raw['reading'], 'FIXED_POLICY', packet, context),
            reviewer='Synthetic intent reviewer', evidence='Adversarial outer rebinding cannot change independent target',
            reviewed_intent_and_conditions=True, synthetic_fixture=True)
        try:
            assignment_review = approved_assignment(bundle, raw, packet, context)
        except ValueError:
            # Rejecting at review creation is also an acceptable boundary.
            self.assertEqual(context.core_port.calls, [])
            return
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
        self.assert_blocked(result, counts)

    def test_fresh_assignment_review_cannot_override_typed_quota(self):
        bundle, raw, packet, context, review = self.fixture()
        # Provenance and an outer review alone cannot change the independently
        # declared m=2 typed study to agree with the reported count 3.
        raw['reported_assignment']['fixed_count'] = 3
        assignment_review = approved_assignment(bundle, raw, packet, context)
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')
        self.assert_blocked(result, counts)

    def test_typed_study_change_invalidates_assignment_review(self):
        bundle, raw, packet, context, review = self.fixture()
        assignment_review = approved_assignment(bundle, raw, packet, context)
        binding = context.core_port.bindings['q1']
        study = binding.inquiry.study
        design = json.loads(study.assignment_design_json)
        design['m'] = 3
        changed_study = replace(study, assignment_design_json=json.dumps(design))
        context.core_port.bindings['q1'] = replace(binding,
            inquiry=replace(binding.inquiry, study=changed_study))
        result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')
        self.assert_blocked(result, counts)

    def test_a4_a5_omissions_cannot_be_granted_by_new_assignment_review(self):
        for field in ('a4_reference', 'a5_reference'):
            with self.subTest(field=field):
                bundle, raw, packet, context, _ = self.fixture()
                packet['queries']['q1'].pop(field)
                review = routes.reviewed_submission(bundle, raw['reading'], 'FIXED_POLICY', packet, context)
                try:
                    assignment_review = approved_assignment(bundle, raw, packet, context)
                except (ValueError, KeyError):
                    self.assertEqual(context.core_port.calls, [])
                    continue
                result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
                self.assert_blocked(result, counts)

    def test_invalid_wrapper_types_and_model_authored_approval_stop(self):
        for change in ('extra_approval', 'bool_count', 'unknown_field', 'duplicate_sources', 'bare_legacy_reading'):
            with self.subTest(change=change):
                bundle, raw, packet, context, review = self.fixture()
                assignment_review = approved_assignment(bundle, raw, packet, context)
                if change == 'extra_approval': raw['scientific_approval'] = True
                elif change == 'bool_count': raw['reported_assignment']['fixed_count'] = True
                elif change == 'unknown_field': raw['reported_assignment']['scientific_approval'] = True
                elif change == 'duplicate_sources': raw['reported_assignment']['source_ids'] *= 2
                else: raw = raw['reading']
                result, counts, _ = self.submit_observed(bundle, raw, packet, context, review, assignment_review)
                self.assert_blocked(result, counts)

    def test_prompt_is_public_and_entry_contract_is_explicit(self):
        bundle, raw, packet, context, review = self.fixture()
        bundle['research_reference'] = {'gold_status': 'PRIVATE_TEST_GOLD'}
        bundle['science_packet'] = 'PRIVATE_TEST_SCIENCE'
        request = business_entry.prepare_request(bundle, 'FIXED_POLICY', contract=CONTRACT)
        for sentinel in ('PRIVATE_TEST_GOLD', 'PRIVATE_TEST_SCIENCE', 'FIXED_ASSIGNMENT_TEST_A4', 'R1B_FULL_ASSIGNMENT'):
            self.assertNotIn(sentinel, request['user'])
        self.assertIn('reported_assignment', json.loads(request['user'])['output_schema']['properties'])
        for entry in ('D1_EFFECTS', 'D2_ARM', 'CLUSTER_ARM'):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                business_entry.prepare_request(bundle, entry, contract=CONTRACT)
        with self.assertRaises(ValueError):
            business_entry.prepare_request(bundle, 'FIXED_POLICY', envelope={}, contract=CONTRACT)

    def test_read_once_uses_one_provider_call_and_never_grants_science(self):
        bundle, raw, _, _, _ = self.fixture()

        class Recorded:
            calls = 0
            def generate_json(self, **kwargs):
                self.calls += 1
                return deepcopy(raw)

        provider = Recorded()
        with patch('socket.create_connection', side_effect=AssertionError('NO_NETWORK')), \
             patch.object(bridge, 'identify_network_business_query', side_effect=AssertionError('NO_CORE')), \
             patch.object(core, 'identify_network_business_query', side_effect=AssertionError('NO_CORE')):
            result = business_entry.read_once(bundle, provider, 'FIXED_POLICY', contract=CONTRACT)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['state'], 'REVIEW_REQUIRED')
        self.assertFalse(result['core_called'])

        class Broken:
            calls = 0
            def generate_json(self, **kwargs):
                self.calls += 1
                raise TimeoutError('SYNTHETIC_PROVIDER_FAILURE')

        provider = Broken()
        with self.assertRaises(TimeoutError):
            business_entry.read_once(bundle, provider, 'FIXED_POLICY', contract=CONTRACT)
        self.assertEqual(provider.calls, 1)


if __name__ == '__main__':
    unittest.main()
