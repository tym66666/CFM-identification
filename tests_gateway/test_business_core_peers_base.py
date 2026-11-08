from copy import deepcopy
from fractions import Fraction
from itertools import product
import unittest
from evaluation import business_core_peers_base as a
from evaluation.business_core_pilot_base import canonical_hash
from examples import nbib_core_peers_fixture as fixture


class CorePeersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.positive = fixture.load_case()
        cls.context = fixture.synthetic_context(cls.positive)

    def item(self):
        return deepcopy(self.positive)

    def test_real_two_certificates_preserve_third_goal(self):
        i = self.item()
        result = a.identify_submission(i['bundle'], i['raw'], i['packet'], context=self.context, synthetic_protocol_selected=True)
        self.assertEqual([x['state'] for x in result['query_views']], ['CORE_POINT', 'CORE_POINT', 'UNSUPPORTED'])
        self.assertEqual(result['identified_query_count'], 2)
        self.assertEqual(result['total_query_count'], 3)
        self.assertEqual(set(self.context.core_port.bindings), {'q1', 'q2'})
        self.assertFalse(result['query_views'][2]['core_called'])
        for field in ('candidate_model_calls', 'estimation_called', 'policy_called', 'production_admission', 'estimation_handoff_allowed'):
            self.assertFalse(result[field])

    def test_core_support_independent_small_subset_enumeration_all_1200_cells(self):
        b = self.positive['bundle']; peers = a.core_partner_table(b)
        rates = a.d1.probability_table(b)
        batch = self.context.core_port.bindings['q1'].inquiry.batch
        for n, group in peers.items():
            high = Fraction(0)
            for bits in product((0, 1), repeat=len(group)):
                weight = Fraction(1)
                for member, bit in zip(group, bits):
                    p = Fraction(rates[member]); weight *= p if bit else 1-p
                if sum(bits) > len(group)/2: high += weight
            for own in (0, 1):
                own_prob = Fraction(rates[n]) if own else 1-Fraction(rates[n])
                for exposure in (0, 1):
                    expected = own_prob * (high if exposure else 1-high)
                    self.assertEqual(Fraction(batch.cell(n, own, exposure)['joint_support']), expected)
        self.assertEqual(batch.shape, (300, 2, 2))

    def test_core_subset_is_not_full_neighborhood(self):
        b = self.positive['bundle']; peers = a.core_partner_table(b); n = 'unit_000'
        full = {x for e in b['structure']['edges'] if n in e for x in e if x != n}
        self.assertLess(len(peers[n]), len(full))
        assignment = set(peers[n][:len(peers[n])//2+1])
        self.assertTrue(len(assignment) > len(peers[n])/2)
        self.assertFalse(len(full & assignment) > len(full)/2)
        contract = self.context.core_port.bindings['q1'].inquiry.batch.template.identification_spec['randomized_network_arm_theorem_contract']
        self.assertEqual(contract['grouping'], a.E3)
        self.assertEqual(set(contract['core_collaborators'][n]), set(peers[n]))

    def test_no_automatic_science(self):
        i = self.item(); result = a.identify_submission(i['bundle'], i['raw'], i['packet'])
        self.assertEqual([x['state'] for x in result['query_views']], ['REVIEW_REQUIRED', 'REVIEW_REQUIRED', 'UNSUPPORTED'])
        self.assertFalse(result['core_called'])

    def test_scope_unknown_cannot_inherit_study_scope(self):
        i = fixture.load_case('scope_unknown'); result = a.preview_submission(i['bundle'], i['raw'])
        self.assertEqual([x['state'] for x in result['query_views']], ['NEEDS_INPUT', 'NEEDS_INPUT', 'UNSUPPORTED'])
        self.assertFalse(result['core_called'])

    def test_one_unknown_does_not_block_other_query(self):
        i = self.item(); i['raw']['questions']['q1']['peer_scope'] = '不明确'
        self.assertEqual([q['state'] for q in a.preview_submission(i['bundle'], i['raw'])['query_views']], ['NEEDS_INPUT', 'REVIEW_REQUIRED', 'UNSUPPORTED'])

    def test_full_neighbors_not_silently_treated_as_core(self):
        i = self.item(); i['raw']['questions']['q1']['peer_scope'] = '全部邻居'
        r = a.preview_submission(i['bundle'], i['raw'])
        self.assertEqual(r['query_views'][0]['reason_code'], 'TARGET_SCOPE_DIFFERS_FROM_STUDY')
        self.assertEqual(r['query_views'][1]['state'], 'REVIEW_REQUIRED')

    def test_missing_core_file_needs_input(self):
        i = self.item(); b = i['bundle']; b['tables'].pop(a.CORE_FILE); b['file_inventory'].pop(a.CORE_FILE); b['core_partner_binding'] = None
        i['raw']['study']['core_partner_source'] = None
        r = a.preview_submission(b, i['raw'])
        self.assertEqual(r['query_views'][0]['reason_code'], 'CORE_PARTNER_TABLE_REQUIRED')

    def test_core_table_edit_rejected_without_matching_binding(self):
        i = self.item(); i['bundle']['tables'][a.CORE_FILE]['rows'][0]['core_partner_node_id'] = 'unit_000'
        with self.assertRaisesRegex(ValueError, 'BINDING'): a.core_partner_table(i['bundle'])

    def test_non_neighbor_or_duplicate_or_incomplete_core_map_rejected(self):
        for action in ('self', 'duplicate', 'missing'):
            i = self.item(); b = i['bundle']; table = b['tables'][a.CORE_FILE]
            if action == 'self': table['rows'][0]['core_partner_node_id'] = table['rows'][0]['node_id']
            elif action == 'duplicate': table['rows'].append(deepcopy(table['rows'][0]))
            else: table['rows'] = [r for r in table['rows'] if r['node_id'] != 'unit_000']
            table['row_count'] = len(table['rows']); b['core_partner_binding']['table_sha256'] = canonical_hash(table)
            with self.assertRaises(ValueError): a.core_partner_table(b)

    def test_stale_model_draft_cannot_reuse_science_review(self):
        i = self.item(); i['raw']['study']['design_sources'].append('study_protocol.md:L5')
        r = a.identify_submission(i['bundle'], i['raw'], i['packet'], context=self.context, synthetic_protocol_selected=True)
        self.assertFalse(r['core_called']); self.assertIsNotNone(r['review_error'])

    def test_deleted_goal_rejected(self):
        i = self.item(); i['raw']['questions'].pop('q3')
        self.assertEqual(a.preview_submission(i['bundle'], i['raw'])['state'], 'DRAFT_INVALID')

    def test_optimization_cannot_invent_fixed_states(self):
        i = self.item(); i['raw']['questions']['q3']['first'] = deepcopy(i['raw']['questions']['q1']['first'])
        self.assertEqual(a.preview_submission(i['bundle'], i['raw'])['state'], 'DRAFT_INVALID')

    def test_undecided_remaining_not_hidden_by_valid_scope(self):
        i = self.item(); i['raw']['questions']['q1']['remaining'] = dict(rule='未确定', source=None, quote=None)
        r = a.preview_submission(i['bundle'], i['raw'])
        self.assertEqual(r['query_views'][0]['reason_code'], 'REMAINING_ALLOCATION_UNRESOLVED')

    def test_request_has_no_private_science_or_reference_answers(self):
        i = self.item(); s, u = a.make_request(i['bundle'])
        self.assertNotIn(i['packet']['science']['population_information'], s+u)
        self.assertNotIn(i['packet']['science']['causal_licenses'], s+u)
        self.assertNotIn('expected_targets', u)

    def test_reading_does_not_mutate_candidate_or_bundle(self):
        i = self.item(); before = deepcopy(i); a.preview_submission(i['bundle'], i['raw'])
        self.assertEqual(i, before)


if __name__ == '__main__': unittest.main()
