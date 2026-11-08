"""Review lifecycle and native proof boundaries. No model calls or credentials."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from cfm_id import research_session as w, review_items as items, session_routes as routes
from cfm_id.research_session_cli import main as cli
from cfm_id_bridge.scientific_binding import sha
from examples.research_session_reference import network, mean_order, dag, approve
from examples.research_item_review_reference import FACTORIES, approve_items, decide, finalize


class ItemReviewTests(unittest.TestCase):
    def opened(self, factory=dag):
        lane, bundle, candidate, native = factory()
        s = w.receive_candidate(w.start(lane, bundle), candidate)
        return w.begin_item_review(s, native_submission=native), native

    def assert_stop(self, result, state='REVIEW_REQUIRED'):
        self.assertEqual(result['state'], state)
        self.assertIsNone(result['mathematical_claim'])
        self.assertIsNone(result['certificate'])
        self.assertFalse(result['independent_replay'])
        self.assertFalse(result['backend_called'])

    def test_all_five_native_routes_replay_after_restore(self):
        for factory in FACTORIES:
            with self.subTest(lane=factory.__name__), TemporaryDirectory() as d:
                s, native = self.opened(factory)
                self.assertEqual(set(items.decisions(s.item_review).values()), {'PENDING'})
                self.assertFalse(w.item_review_worksheet(s)['is_approval'])
                original = w.execute(approve(s.model_copy(update={'item_review': None}), native),
                                     native_submission=native, research_protocol_selected=True)
                s = approve_items(s)
                w.save(s, Path(d) / 'reviewed.json')
                restored = w.restore(Path(d) / 'reviewed.json')
                self.assert_stop(w.execute(restored, research_protocol_selected=True))
                result = w.execute(restored, native_submission=native, research_protocol_selected=True)
                self.assertEqual(result['state'], original['state'])
                self.assertEqual(result['mathematical_claim'], original['mathematical_claim'])
                self.assertEqual(result['certificate'], original['certificate'])
                self.assertTrue(result['independent_replay'])
                self.assertFalse(result['production_admission'])

    def test_no_native_approval_is_copied_into_outer_items(self):
        s, native = self.opened()
        self.assertTrue(all(v == 'ACCEPTED' for v in native['science_review'].decisions.values()))
        self.assertTrue(all(v == 'PENDING' for v in items.decisions(s.item_review).values()))
        with self.assertRaisesRegex(ValueError, 'ALL_REVIEW_ITEMS'):
            finalize(s)
        with patch.object(routes, 'submit', side_effect=AssertionError('must stop')):
            self.assert_stop(w.execute(s, native_submission=native, research_protocol_selected=True))

    def test_old_three_checkbox_review_cannot_bypass_active_book(self):
        s, native = self.opened()
        with self.assertRaisesRegex(ValueError, 'CURRENT_ITEM_REVIEW_BINDING'):
            approve(s, native)
        # Even knowing the current digest cannot make pending items acceptable.
        review = dict(binding_sha256=w.binding(s), native_submission_sha256=sha(s.item_review.native_snapshot),
            item_review_sha256=sha(s.item_review), reviewer='Reviewer', evidence='Independent exact declaration review.',
            decisions={k: 'ACCEPTED' for k in w.DECISIONS})
        with self.assertRaisesRegex(ValueError, 'ALL_REVIEW_ITEMS'):
            w.record_review(s, review)

    def test_edit_withdraw_pending_reject_clear_approval_before_backend(self):
        for factory in (network, mean_order, dag):
            s, native = self.opened(factory)
            s = approve_items(s)
            row = next(r for r in s.item_review.items if r.category == 'A5')
            for decision, state in [('WITHDRAWN', 'REVIEW_REQUIRED'), ('PENDING', 'REVIEW_REQUIRED'),
                                    ('REJECTED', 'CHECK_BLOCKED'), ('ACCEPTED', 'REVIEW_REQUIRED')]:
                with self.subTest(factory=factory.__name__, decision=decision):
                    changed = decide(s, row.item_id, decision)
                    self.assertIsNone(changed.review)
                    self.assertEqual(len(changed.item_review.events), len(s.item_review.events) + 1)
                    with patch.object(routes, 'submit', side_effect=AssertionError('must stop')):
                        self.assert_stop(w.execute(changed, native_submission=native,
                                                   research_protocol_selected=True), state)
                    self.assertEqual(changed.history[-1]['prior_review_sha256'], sha(s.review))

    def test_reaccepting_requires_explicit_finalization(self):
        s, native = self.opened()
        s = approve_items(s)
        row = s.item_review.items[0]
        changed = decide(decide(s, row.item_id, 'WITHDRAWN'), row.item_id, 'ACCEPTED')
        self.assert_stop(w.execute(changed, native_submission=native, research_protocol_selected=True))
        with self.assertRaisesRegex(ValueError, 'CURRENT_ITEM_REVIEW_BINDING'):
            w.record_review(changed, s.review)
        result = w.execute(finalize(changed), native_submission=native, research_protocol_selected=True)
        self.assertEqual(result['state'], 'POINT')

    def test_stale_concurrent_edits_and_finalize_are_rejected(self):
        s, _ = self.opened()
        old_digest = sha(s.item_review)
        row = s.item_review.items[0]
        updated = decide(s, row.item_id, 'ACCEPTED')
        with self.assertRaisesRegex(ValueError, 'STALE_ITEM_REVIEW_EDIT'):
            w.decide_item(updated, dict(expected_review_sha256=old_digest, item_id=row.item_id,
                decision='REJECTED', reviewer='Reviewer', evidence='Another reviewer on the old copy.'))
        with self.assertRaisesRegex(ValueError, 'STALE_ITEM_REVIEW_FINALIZATION'):
            w.finalize_item_review(updated, expected_review_sha256=old_digest,
                                  reviewer='Reviewer', evidence='Old worksheet is not current approval.')

    def test_unknown_items_blank_reasons_and_foreign_binding_rejected(self):
        s, _ = self.opened()
        for field, value in [('item_id', 'unknown'), ('reviewer', '   '), ('evidence', ' ' * 20)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                change = dict(expected_review_sha256=sha(s.item_review), item_id=s.item_review.items[0].item_id,
                              decision='ACCEPTED', reviewer='Reviewer', evidence='Independent review of exact materials.')
                change[field] = value
                w.decide_item(s, change)
        other, _ = self.opened()
        with self.assertRaisesRegex(ValueError, 'STALE_ITEM_REVIEW'):
            w.inspect(other.model_copy(update={'item_review': s.item_review}))

    def test_deleted_changed_and_reclassified_items_rejected_even_after_rehash(self):
        s, _ = self.opened()
        for mutation in ('delete', 'title', 'category', 'bool_to_int'):
            with self.subTest(mutation=mutation), TemporaryDirectory() as d:
                value = s.model_dump()
                rows = value['item_review']['items']
                if mutation == 'delete': rows.pop()
                elif mutation == 'title': rows[0]['title'] = 'All scientific assumptions approved'
                elif mutation == 'category': rows[0]['category'] = 'A5'
                else:
                    row = next(r for r in rows if r['item_id'].startswith('positivity:'))
                    row['declaration']['strictly_positive_joint'] = 1
                p = Path(d) / 'changed.json'
                w.write_json(p, dict(kind='RESEARCH_SESSION_CHECKPOINT', payload=value, sha256=sha(value)))
                with self.assertRaisesRegex(ValueError, 'CHECKLIST_CHANGED'):
                    w.restore(p)

    def test_broken_event_chain_and_prior_decisions_rejected(self):
        s, _ = self.opened()
        s = decide(s, s.item_review.items[0].item_id, 'ACCEPTED')
        for field, value in [('sequence', 2), ('previous_sha256', '0' * 64),
                             ('previous_decision', 'REJECTED'), ('item_id', 'unknown')]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'JOURNAL_INVALID'):
                raw = s.model_dump()
                raw['item_review']['events'][0][field] = value
                w.inspect(w.ResearchSession.model_validate(raw))

    def test_source_and_candidate_changes_reset_book(self):
        s, _ = self.opened()
        s = approve_items(s)
        bundle = deepcopy(s.bundle)
        bundle['documents']['new_context'] = 'Study period has been changed.'
        for changed in (w.receive_candidate(s, s.candidate), w.revise_materials(s, bundle, reason='Changed context')):
            self.assertIsNone(changed.item_review)
            self.assertIsNone(changed.review)
            self.assertEqual(changed.history[-1]['prior_item_review_sha256'], sha(s.item_review))

    def test_changed_native_submission_requires_fresh_pending_book(self):
        s, native = self.opened()
        s = approve_items(s)
        native['science_review'] = native['science_review'].model_copy(update={'evidence': 'Changed scientific review evidence.'})
        with patch.object(routes, 'submit', side_effect=AssertionError('must stop')):
            self.assert_stop(w.execute(s, native_submission=native, research_protocol_selected=True), 'CHECK_BLOCKED')
        new = w.begin_item_review(s, native_submission=native)
        self.assertIsNone(new.review)
        self.assertEqual(set(items.decisions(new.item_review).values()), {'PENDING'})
        self.assertNotEqual(sha(new.item_review.native_snapshot), sha(s.item_review.native_snapshot))

    def test_native_scientific_rejection_cannot_be_overridden(self):
        for decision in ('PENDING', 'REJECTED'):
            with self.subTest(decision=decision):
                lane, bundle, candidate, native = dag()
                r = native['science_review']
                decisions = dict(r.decisions)
                decisions['recursive_scm_and_perfect_intervention'] = decision
                native['science_review'] = r.model_copy(update={'decisions': decisions})
                s = approve_items(w.begin_item_review(w.receive_candidate(w.start(lane, bundle), candidate),
                                                     native_submission=native))
                self.assert_stop(w.execute(s, native_submission=native, research_protocol_selected=True),
                                 'REVIEW_REQUIRED' if decision == 'PENDING' else 'CHECK_BLOCKED')

    def test_network_and_partial_native_permission_remains_required(self):
        for factory, key, field in ((network, 'submission_review', 'reviewed_intent_and_conditions'),
                                   (mean_order, 'review', 'reviewed_base_assumptions_and_all_arrangement_scope')):
            with self.subTest(factory=factory.__name__):
                lane, bundle, candidate, native = factory()
                native[key] = native[key].model_copy(update={field: False})
                s = approve_items(w.begin_item_review(w.receive_candidate(w.start(lane, bundle), candidate),
                                                     native_submission=native))
                self.assert_stop(w.execute(s, native_submission=native, research_protocol_selected=True), 'CHECK_BLOCKED')

    def test_absent_mean_order_axes_are_explicit_not_assumptions(self):
        # Reuse independently specified scientific fixture with mixed node modes.
        from examples.mean_order_business_fixture import make_case
        modes = {'A': 'NONE', 'B': 'OWN', 'C': 'PEERS', 'D': 'BOTH'}
        with patch('examples.mean_order_business_fixture.make_case', side_effect=lambda: make_case(mode=modes)):
            s, _ = self.opened(mean_order)
        orders = [r.declaration for r in s.item_review.items if r.item_id.startswith('order/')]
        self.assertEqual(len(orders), 8)
        for row in orders:
            mode = modes[row['order']['node']]
            self.assertEqual(row['restriction_present'], mode in (row['axis'], 'BOTH'))
        self.assertEqual(sum(row['restriction_present'] for row in orders), 4)

    def test_new_items_never_change_original_model_request(self):
        for factory in (network, mean_order, dag):
            with self.subTest(factory=factory.__name__):
                s, _ = self.opened(factory)
                request = routes.request(s.lane, s.bundle)
                self.assertEqual(w.prepare_request(approve_items(s)), request)
                self.assertNotIn('Independent synthetic item reviewer', json.dumps(request))

    def test_missing_conditions_cannot_create_review_items(self):
        lane, bundle, candidate, _ = network('convenience_stores')
        _, _, _, native = network()
        s = w.receive_candidate(w.start(lane, bundle), candidate)
        with self.assertRaisesRegex(ValueError, 'NOT_READY'):
            w.begin_item_review(s, native_submission=native)

    def test_route_specific_semantics_are_not_collapsed(self):
        s, _ = self.opened(network)
        licenses = [row.declaration['name'] for row in s.item_review.items if '/license/' in row.item_id]
        self.assertEqual(set(licenses), {'consistency', 'finite_conditional_first_moments',
            'fixed_pretreatment_network', 'full_vector_randomization', 'known_assignment_law'})
        s, _ = self.opened(mean_order)
        bounds = [row for row in s.item_review.items if row.item_id.startswith('bounds/')]
        self.assertEqual(len(bounds), 4)
        self.assertTrue(all(row.declaration['bounds_kind'] == 'CONDITIONAL_MEAN' for row in bounds))
        orders = [row for row in s.item_review.items if row.item_id.startswith('order/')]
        self.assertEqual(len(orders), 8)
        self.assertEqual({r.declaration['axis'] for r in orders}, {'OWN', 'PEERS'})
        self.assertTrue(all(r.declaration['restriction_present'] for r in orders))
        self.assertTrue(any(r.item_id.startswith('mean_sufficiency_claim:') for r in s.item_review.items))
        s, _ = self.opened()
        self.assertEqual(len([r for r in s.item_review.items if r.category == 'A5']), 5)
        self.assertFalse(any('FD1' in r.title or 'FD2' in r.title or 'FD3' in r.title for r in s.item_review.items))

    def test_withdrawing_bound_is_not_a_relaxed_mathematical_model(self):
        s, native = self.opened(mean_order)
        s = approve_items(s)
        bound = next(r for r in s.item_review.items if r.item_id.startswith('bounds/'))
        changed = decide(s, bound.item_id, 'WITHDRAWN')
        self.assertEqual(changed.item_review.native_snapshot, s.item_review.native_snapshot)
        self.assert_stop(w.execute(changed, native_submission=native, research_protocol_selected=True))

    def test_legacy_checkpoints_remain_readable_without_granting_items(self):
        s, native = self.opened()
        legacy = approve(s.model_copy(update={'item_review': None}), native).model_dump()
        legacy.pop('item_review')
        legacy['review'].pop('item_review_sha256')
        with TemporaryDirectory() as d:
            p = Path(d) / 'old.json'
            w.write_json(p, dict(kind='PUBLIC_RESEARCH_SESSION_CHECKPOINT', payload=legacy, sha256=sha(legacy)))
            restored = w.restore(p)
            self.assertIsNone(restored.item_review)
            self.assertEqual(w.execute(restored, native_submission=native, research_protocol_selected=True)['state'], 'POINT')

    def test_cli_dag_open_decide_finalize_and_submit(self):
        s, native = self.opened()
        with TemporaryDirectory() as d:
            d = Path(d)
            raw = s.model_copy(update={'item_review': None})
            w.save(raw, d / 'raw.json')
            for key, review in native.items(): w.write_json(d / (key + '.json'), review.model_dump())
            files = ['--reading-review', str(d / 'reading_review.json'), '--science-review', str(d / 'science_review.json')]
            self.assertEqual(cli(['review-open-dag', '--session', str(d / 'raw.json'), *files,
                                  '--output', str(d / 'pending.json')]), 0)
            s = w.restore(d / 'pending.json')
            self.assertEqual(cli(['review-items', '--session', str(d / 'pending.json'), '--output', str(d / 'items.json')]), 0)
            current = d / 'pending.json'
            for index, row in enumerate(s.item_review.items):
                s = w.restore(current)
                change = dict(expected_review_sha256=sha(s.item_review), item_id=row.item_id,
                    decision='ACCEPTED', reviewer='Synthetic CLI reviewer', evidence='Explicit independent synthetic protocol review.')
                w.write_json(d / f'decision{index}.json', change)
                dest = d / f'edited{index}.json'
                self.assertEqual(cli(['review-decide', '--session', str(current), '--review', str(d / f'decision{index}.json'),
                                      '--output', str(dest)]), 0)
                current = dest
            s = w.restore(current)
            w.write_json(d / 'finalize.json', dict(expected_review_sha256=sha(s.item_review),
                reviewer='Synthetic CLI reviewer', evidence='Final independent synthetic review of current items.'))
            self.assertEqual(cli(['review-finalize', '--session', str(current), '--review', str(d / 'finalize.json'),
                                  '--output', str(d / 'reviewed.json')]), 0)
            args = ['submit-dag', '--session', str(d / 'reviewed.json'), *files, '--select-research-protocol',
                    '--output', str(d / 'result.json')]
            self.assertEqual(cli(args), 0)
            self.assertEqual(w.read_json(d / 'result.json')['state'], 'POINT')
            self.assertEqual(cli(args), 2)  # exclusive outputs

    def test_cli_can_edit_network_and_partial_books_without_executable_context(self):
        for factory in (network, mean_order):
            with self.subTest(factory=factory.__name__), TemporaryDirectory() as d:
                s, _ = self.opened(factory)
                d = Path(d)
                w.save(s, d / 'session.json')
                change = dict(expected_review_sha256=sha(s.item_review), item_id=s.item_review.items[0].item_id,
                    decision='WITHDRAWN', reviewer='Synthetic CLI reviewer', evidence='This declaration needs additional independent review.')
                w.write_json(d / 'change.json', change)
                self.assertEqual(cli(['review-decide', '--session', str(d / 'session.json'), '--review', str(d / 'change.json'),
                                      '--output', str(d / 'changed.json')]), 0)
                self.assertEqual(w.restore(d / 'changed.json').item_review.events[-1].decision, 'WITHDRAWN')


if __name__ == '__main__':
    unittest.main()
