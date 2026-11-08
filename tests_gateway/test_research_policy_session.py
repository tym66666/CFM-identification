"""Fixed-policy and contrast session integration, actual replay and negative gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from cfm_id import research_session as work, session_routes as routes, session_policy_routes as policy_routes
from cfm_id import business_entry
from cfm_id_bridge.scientific_binding import sha
from examples.research_item_review_reference import approve_items, decide
from examples.research_policy_session_reference import policy, comparison, contrast

FACTORIES = (policy, comparison, lambda: policy('star7', bounded=True), contrast)


class PolicySessionTests(unittest.TestCase):
    def opened(self, factory):
        lane, bundle, candidate, native = factory()
        session = work.receive_candidate(work.start(lane, bundle), candidate)
        return work.begin_item_review(session, native_submission=native), native

    def execute(self, session, native):
        return work.execute(session, native_submission=native, research_protocol_selected=True)

    def assert_stop(self, result, *, before_backend=True):
        self.assertIsNone(result['mathematical_claim'])
        self.assertIsNone(result['certificate'])
        self.assertFalse(result['independent_replay'])
        if before_backend:
            self.assertFalse(result['backend_called'])

    def test_four_lanes_save_restore_and_native_results_unchanged(self):
        for factory in FACTORIES:
            s, native = self.opened(factory)
            with self.subTest(lane=s.lane), TemporaryDirectory() as directory:
                direct = routes.submit(s.lane, s.bundle, s.candidate, native)
                s = approve_items(s)
                p = Path(directory) / 'reviewed.json'
                work.save(s, p)
                restored = work.restore(p)
                self.assert_stop(work.execute(restored, research_protocol_selected=True))
                result = self.execute(restored, native)
                self.assertEqual(result['state'], 'POINT' if direct['state'] == 'CORE_POINT' else direct['state'])
                self.assertTrue(result['independent_replay'])
                if s.lane in policy_routes.BOUNDED:
                    self.assertEqual(result['certificate'], direct['bounded_result'])
                else:
                    self.assertEqual(result['native_result']['identification'], direct['identification'])
                self.assertFalse(result['production_admission'])
                self.assertFalse(result['estimation_handoff_allowed'])

    def test_requests_are_original_and_exclude_review_records(self):
        for factory in FACTORIES:
            s, native = self.opened(factory)
            with self.subTest(lane=s.lane):
                original = business_entry.prepare_request(s.bundle,
                    'FIXED_COMPARISON' if s.lane in policy_routes.PAIRED else 'FIXED_POLICY',
                    contract='fixed-assignment-id')
                self.assertEqual(work.prepare_request(approve_items(s)), original)
                self.assertNotIn('review', original)

    def test_public_formula_fields_match_existing_network_contract(self):
        for factory in (policy, comparison):
            s, native = self.opened(factory)
            claim = self.execute(approve_items(s), native)['mathematical_claim']
            self.assertEqual(claim['representation'], 'PER_QUERY_OBSERVED_FUNCTIONALS')
            for query in claim['queries']:
                self.assertEqual(len(query['functionals']), 1)
                self.assertEqual(set(query['functionals'][0]), {'target_fingerprint', 'expression'})
                self.assertEqual(len(query['functionals'][0]['target_fingerprint']), 64)
                self.assertTrue(query['functionals'][0]['expression'])
                self.assertIsInstance(query['target_coordinates'], dict)

    def test_r1b_policy_preserves_full_assignment_formula_without_mean_sufficiency(self):
        from tests_gateway.test_fixed_assignment_submission import quota_full_fixture
        from tests_gateway.test_question_bound_assignment import bind_fixture, review_for
        b, raw, packet, context, review = quota_full_fixture()
        raw = bind_fixture(b, raw)
        native = dict(packet=packet, context=context, submission_review=review,
                      assignment_review=review_for(b, raw, packet, context))
        s = work.receive_candidate(work.start(policy_routes.POLICY, b), raw)
        s = work.begin_item_review(s, native_submission=native)
        self.assertFalse(any('mean_sufficiency' in i.item_id for i in s.item_review.items))
        result = self.execute(approve_items(s), native)
        self.assertEqual(result['state'], 'POINT')
        self.assertEqual(result['mathematical_claim']['queries'][0]['route'], 'R1B_FULL_ASSIGNMENT')
        self.assertTrue(result['independent_replay'])

    def test_policy_target_population_all_subset_single(self):
        for population, expected in [(None, ['3/7','4/7']), (['H'], ['0','1']), (['L1'], ['1/2','1/2'])]:
            with self.subTest(population=population):
                s, native = self.opened(lambda: policy('star7', bounded=True, population=population))
                result = self.execute(approve_items(s), native)
                self.assertEqual(result['mathematical_claim']['interval'], expected)
                self.assertTrue(result['independent_replay'])

    def test_same_unknown_policy_cancels_in_joint_model(self):
        s, native = self.opened(lambda: contrast(second=[1]*4))
        result = self.execute(approve_items(s), native)
        self.assertEqual(result['state'], 'POINT')
        self.assertEqual(result['mathematical_claim']['interval'], ['0','0'])
        self.assertTrue(result['mathematical_claim']['sharp'])
        self.assertTrue(all(row['status'] != 'POINT' for row in result['native_result']['point_assessment'].values()))

    def test_different_policies_can_cancel_shared_unknown_cells(self):
        from examples.bounded_contrast_fixture import make_case
        from examples.partial_contrast_reference import set_common_information, vertex_reference
        p = make_case(list('ABCD'), [('A','B')], 1, [1,1,1,0], [1,1,0,0], ['A','C'], serial=126)
        set_common_information(p, values={('C',1,0):'3/5', ('C',0,0):'1/5'})
        expected = [str(v) for v in vertex_reference(p)]
        s, native = self.opened(lambda: contrast(payload=p))
        result = self.execute(approve_items(s), native)
        self.assertEqual(expected, ['1/5','1/5'])
        self.assertEqual(result['mathematical_claim']['interval'], expected)

    def test_partial_contrast_matches_independent_vertex_reference(self):
        from examples.bounded_contrast_fixture import make_case
        from examples.partial_contrast_reference import vertex_reference
        for first, second in [([1]*4, [0]*4), ([0]*4, [1]*4), ([1,1,0,0], [0,0,1,1])]:
            with self.subTest(first=first):
                p = make_case(list('ABCD'), [('A','B'), ('B','C'), ('C','D')], 2, first, second, list('ABCD'), serial=128)
                s, native = self.opened(lambda: contrast(payload=p))
                result = self.execute(approve_items(s), native)
                self.assertEqual(result['mathematical_claim']['interval'], [str(v) for v in vertex_reference(p)])

    def test_point_lane_never_falls_back_to_bounds(self):
        s, native = self.opened(lambda: policy('star7'))
        with patch('cfm_id.bounded_policy.submit', side_effect=AssertionError('no implicit fallback')):
            result = self.execute(approve_items(s), native)
        self.assertEqual(result['state'], 'UNSUPPORTED')
        self.assert_stop(result, before_backend=False)

    def test_pending_withdrawn_and_rejected_items_stop_before_submission(self):
        for factory in FACTORIES:
            s, native = self.opened(factory)
            s = approve_items(s)
            item = next(i for i in s.item_review.items if i.category == 'A5')
            for decision in ('PENDING', 'WITHDRAWN', 'REJECTED'):
                with self.subTest(lane=s.lane, decision=decision), patch.object(routes, 'submit', side_effect=AssertionError('must stop')):
                    changed = decide(s, item.item_id, decision)
                    self.assert_stop(self.execute(changed, native))

    def test_missing_native_reviews_cannot_be_replaced_by_all_outer_acceptances(self):
        for factory, key in [(policy, 'assignment_review'), (comparison, 'submission_review'),
                             (lambda: policy('star7', bounded=True), 'bounded_review'), (contrast, 'joint_review')]:
            lane, b, c, native = factory()
            with self.subTest(lane=lane):
                native[key] = None
                s = work.receive_candidate(work.start(lane, b), c)
                s = approve_items(work.begin_item_review(s, native_submission=native))
                result = self.execute(s, native)
                self.assertEqual(result['state'], 'REVIEW_REQUIRED')
                self.assert_stop(result)

    def test_missing_second_endpoint_science_remains_blocked(self):
        from dataclasses import replace
        for factory in (comparison, contrast):
            lane, b, c, native = factory()
            with self.subTest(lane=lane):
                context = native['context']['second']
                qid = next(iter(context.core_port.bindings))
                binding = context.core_port.bindings[qid]
                context.core_port.bindings[qid] = replace(binding, admission=binding.admission.model_copy(
                    update={'approved_scientific_binding': None}))
                s = work.receive_candidate(work.start(lane, b), c)
                s = approve_items(work.begin_item_review(s, native_submission=native))
                self.assertEqual(self.execute(s, native)['state'], 'CHECK_BLOCKED')
                self.assert_stop(self.execute(s, native))

    def test_direction_swap_and_changed_common_information_do_not_reuse_review(self):
        for mutation in ('direction', 'information'):
            s, native = self.opened(contrast)
            s = approve_items(s)
            if mutation == 'direction':
                native['context'] = {'first': native['context']['second'], 'second': native['context']['first']}
            else:
                info = native['information']['second']
                values = list(info.values)
                values[0] = values[0].model_copy(update={'value': '0'})
                native['information']['second'] = info.model_copy(update={'values': values})
            with self.subTest(mutation=mutation), patch.object(routes, 'submit', side_effect=AssertionError('must stop')):
                self.assert_stop(self.execute(s, native))
            reopened = approve_items(work.begin_item_review(s, native_submission=native))
            self.assert_stop(self.execute(reopened, native))

    def test_missing_target_conditions_generate_bound_followup(self):
        for factory in (policy, comparison):
            lane, b, c, native = factory()
            qid = next(iter(c['reading']['questions']))
            c['reading']['questions'][qid]['population'] = None
            s = work.receive_candidate(work.start(lane, b), c)
            self.assert_stop(self.execute(s, native))
            plan = work.clarification_plan(s)
            self.assertTrue(plan['questions'])
            changed = work.append_reply(s, plan, plan['questions'][0]['clarification_id'], '评价对象尚未决定。')
            self.assertIsNone(changed.candidate)
            self.assertIsNone(changed.review)

    def test_missing_original_quota_cannot_be_approved(self):
        lane, b, c, native = policy()
        c['reported_assignment']['fixed_count'] = None
        s = work.receive_candidate(work.start(lane, b), c)
        self.assert_stop(self.execute(s, native))
        with self.assertRaises(ValueError):
            work.begin_item_review(s, native_submission=native)

    def test_material_changes_invalidate_question_ids_and_item_review(self):
        s, native = self.opened(contrast)
        s = approve_items(s)
        b = deepcopy(s.bundle)
        b['documents']['study.txt'] += '\n补充一个不同研究时期。'
        changed = work.revise_materials(s, b, reason='Changed study context')
        self.assertIsNone(changed.item_review)
        changed = work.receive_candidate(changed, s.candidate)
        self.assertEqual(work.inspect(changed)['state'], 'CHECK_BLOCKED')
        self.assert_stop(self.execute(changed, native))

    def test_unknown_query_extra_flags_and_wrong_lane_submission_are_rejected(self):
        s, native = self.opened(lambda: policy('star7', bounded=True))
        for field, value in [('query_id', 'invented'), ('synthetic_protocol_selected', True)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                work.begin_item_review(s, native_submission=dict(native, **{field: value}))
        with self.assertRaises(ValueError):
            routes.submission_snapshot(policy_routes.COMPARISON, native)

    def test_bounded_lanes_do_not_silently_select_one_of_many_questions(self):
        from examples.fixed_comparison_fixture import public_bundle, reference
        b = public_bundle(only=['q1', 'q2'])
        s = work.receive_candidate(work.start(policy_routes.BOUNDED_COMPARISON, b), reference(b))
        self.assertEqual(work.inspect(s)['state'], 'UNSUPPORTED')
        self.assert_stop(work.execute(s, research_protocol_selected=True))

    def test_public_materials_reject_private_science(self):
        lane, b, _, native = policy()
        for key in ('science', 'information', 'reference', 'native_submission'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                work.start(lane, dict(b, **{key: {'admission': True}}))

    def test_forged_policy_formula_is_rejected_despite_success_flags(self):
        s, native = self.opened(policy)
        s = approve_items(s)
        real = routes.submit
        def tampered(*args):
            result = real(*args)
            result['identification']['results'][0]['core']['identification']['identified_functional'] = '0'
            return result
        with patch.object(routes, 'submit', side_effect=tampered):
            result = self.execute(s, native)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')
        self.assert_stop(result, before_backend=False)

    def test_rehashed_wrong_comparison_sign_is_rejected(self):
        s, native = self.opened(comparison)
        s = approve_items(s)
        real = routes.submit
        def tampered(*args):
            result = real(*args)
            row = result['query_views'][0]
            receipt = row['composition']
            receipt['terms'][0]['coefficient'] = '0'
            receipt.pop('receipt_sha256')
            receipt['receipt_sha256'] = sha(receipt)
            result['identification']['results'][0] = deepcopy(row)
            return result
        with patch.object(routes, 'submit', side_effect=tampered):
            result = self.execute(s, native)
        self.assert_stop(result, before_backend=False)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')

    def test_rehashed_wrong_bounds_and_valid_certificate_wrong_display_are_rejected(self):
        for factory in (lambda: policy('star7', bounded=True), contrast):
            for mutation in ('certificate', 'display', 'query_set', 'sharp'):
                s, native = self.opened(factory)
                s = approve_items(s)
                real = routes.submit
                def tampered(*args):
                    result = real(*args)
                    if mutation == 'certificate':
                        cert = result['bounded_result']
                        cert['upper'] = '7'
                        cert.pop('certificate_sha256')
                        cert['certificate_sha256'] = sha(cert)
                    elif mutation == 'display':
                        result['query_views'][0]['identified_interval'] = ['0','0']
                    elif mutation == 'query_set':
                        result['query_views'].append(deepcopy(result['query_views'][0]))
                    else:
                        result['query_views'][0]['sharp'] = 1
                    return result
                with self.subTest(lane=s.lane, mutation=mutation), patch.object(routes, 'submit', side_effect=tampered):
                    result = self.execute(s, native)
                    self.assertEqual(result['state'], 'CHECK_BLOCKED')
                    self.assert_stop(result, before_backend=False)

    def test_incompatible_data_is_diagnostic_not_a_certified_infeasibility_result(self):
        from cfm_id.bounded_policy import worksheet
        lane, b, c, native = policy('star7', bounded=True)
        info = native['information']
        values = list(info.values)
        values[0] = values[0].model_copy(update={'value': '2'})
        native['information'] = info.model_copy(update={'values': values})
        binding = worksheet(b, c, **{k: native[k] for k in ('query_id','packet','context','information')})
        native['bounded_review'] = native['bounded_review'].model_copy(update=binding)
        s = approve_items(work.begin_item_review(work.receive_candidate(work.start(lane, b), c), native_submission=native))
        result = self.execute(s, native)
        self.assertEqual(result['state'], 'INCOMPATIBLE')
        self.assert_stop(result, before_backend=False)

    def test_policy_snapshots_bind_actual_scientific_inputs_not_only_metadata(self):
        for factory in FACTORIES:
            s, native = self.opened(factory)
            snap = s.item_review.native_snapshot['native_submission']['context']
            contexts = snap.values() if s.lane in policy_routes.PAIRED else [snap]
            for context in contexts:
                self.assertEqual(set(context['inquiries']), set(context['bindings']))
                for inquiry in context['inquiries'].values():
                    self.assertIn('assumptions', inquiry)
                    self.assertIn('study', inquiry)
                    self.assertIn('r1b_sources', inquiry)
                    self.assertIn('r2_sources', inquiry)


if __name__ == '__main__':
    unittest.main()
