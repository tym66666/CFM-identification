from copy import deepcopy
import json
import unittest
from examples import nbib_d2_fixture as d2_fixture
from examples import nbib_arm_fixture as cluster_fixture
from evaluation import business_remaining_transfer as adapter


def new_reading(old):
    raw = deepcopy(old)
    for q in raw['questions'].values():
        source, quote = q.pop('remaining_source'), q.pop('remaining_evidence_span')
        q['remaining'] = dict(rule='原抽签条件平均' if source else '未确定', source=source, quote=quote)
    return raw


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.items = [(adapter.ENTRY_D2, d2_fixture.load_case(), d2_fixture),
                      (adapter.ENTRY_CLUSTER, cluster_fixture.load_case(), cluster_fixture)]

    def negative(self, item):
        item = deepcopy(item); raw = new_reading(item['raw'])
        quote = '其他对象怎样安排，业务部门还没有决定。'
        lines = item['bundle']['documents']['target_clarification.txt'].splitlines(); lines[2] = quote
        item['bundle']['documents']['target_clarification.txt'] = '\n'.join(lines)
        raw['questions']['q1']['remaining'].update(rule='未确定', quote=quote)
        return item, raw

    def test_positive_needs_explicit_review_in_both_designs(self):
        for entry, item, _ in self.items:
            r = adapter.identify_reading(item['bundle'], new_reading(item['raw']), entry)
            self.assertEqual(r['state'], 'REVIEW_REQUIRED'); self.assertFalse(r['core_called'])

    def test_both_real_core_certificates_after_review(self):
        for entry, item, fixture in self.items:
            r = adapter.identify_reading(item['bundle'], new_reading(item['raw']), entry, item['packet'],
                context=fixture.synthetic_context(item), synthetic_protocol_selected=True)
            self.assertEqual(r['state'], 'CORE_POINT'); self.assertTrue(r['core_called'])
            cert = r['query_views'][0]['certificate_replayed'] if 'query_views' in r else r['view']['core']['certificate_replayed']
            self.assertTrue(cert)

    def test_unknown_with_evidence_blocks_both_designs(self):
        for entry, item, _ in self.items:
            item, raw = self.negative(item); r = adapter.identify_reading(item['bundle'], raw, entry)
            self.assertEqual(r['state'], 'NEEDS_INPUT'); self.assertFalse(r['core_called'])
            self.assertEqual(r['remaining_decisions']['q1'], raw['questions']['q1']['remaining'])
            self.assertEqual(r['clarification_questions'][0]['field'], 'remaining')

    def test_known_coordinates_retained(self):
        for entry, item, _ in self.items:
            item, raw = self.negative(item); r = adapter.identify_reading(item['bundle'], raw, entry)
            for k, v in raw['questions']['q1'].items():
                if k != 'remaining': self.assertEqual(r['draft']['questions']['q1'][k], v)
            self.assertEqual(r['draft']['study'], raw['study'])

    def test_raw_unchanged(self):
        for entry, item, _ in self.items:
            raw = new_reading(item['raw']); before = deepcopy(raw); r = adapter.identify_reading(item['bundle'], raw, entry)
            self.assertEqual(raw, before); self.assertEqual(r['reading_candidate'], before)

    def test_false_positive_rule_contradicted_by_quote_rejected(self):
        for entry, item, _ in self.items:
            item, raw = self.negative(item); raw['questions']['q1']['remaining']['rule'] = '原抽签条件平均'
            self.assertEqual(adapter.identify_reading(item['bundle'], raw, entry)['state'], 'DRAFT_INVALID')

    def test_malformed_or_mixed_contract_rejected(self):
        for entry, item, _ in self.items:
            raw = new_reading(item['raw']); raw['questions']['q1']['remaining_source'] = None
            self.assertEqual(adapter.identify_reading(item['bundle'], raw, entry)['state'], 'DRAFT_INVALID')
            self.assertEqual(adapter.identify_reading(item['bundle'], {'questions': {}}, entry)['state'], 'DRAFT_INVALID')

    def test_fake_source_rejected(self):
        for entry, item, _ in self.items:
            raw = new_reading(item['raw']); raw['questions']['q1']['remaining']['source'] = 'fake:L3'
            self.assertEqual(adapter.identify_reading(item['bundle'], raw, entry)['state'], 'DRAFT_INVALID')

    def test_other_rule_not_changed_to_original(self):
        for entry, item, _ in self.items:
            item, raw = self.negative(item); raw['questions']['q1']['remaining']['rule'] = '其他安排'
            r = adapter.identify_reading(item['bundle'], raw, entry)
            self.assertEqual(r['state'], 'UNSUPPORTED'); self.assertFalse(r['core_called'])
            self.assertEqual(r['candidate_model_calls'], 0)

    def test_request_preserves_public_evidence(self):
        for entry, item, _ in self.items:
            build, _, _ = adapter._entry(entry)
            _, old = adapter.annotate_outcome_contract(*build(item['bundle']))
            system, user = adapter.make_request(item['bundle'], entry)
            old, user = json.loads(old), json.loads(user); old.pop('output_schema'); user.pop('output_schema')
            self.assertEqual(old, user); self.assertNotIn('remaining_source', system)

    def test_design_fields_not_replaced(self):
        for entry, item, _ in self.items:
            build, _, _ = adapter._entry(entry)
            _, old = adapter.annotate_outcome_contract(*build(item['bundle']))
            _, user = adapter.make_request(item['bundle'], entry)
            self.assertEqual(json.loads(old)['output_schema']['properties']['study'], json.loads(user)['output_schema']['properties']['study'])

    def test_no_estimation_policy_or_candidate_approval(self):
        for entry, item, _ in self.items:
            r = adapter.identify_reading(item['bundle'], new_reading(item['raw']), entry)
            self.assertFalse(any(r[k] for k in ('production_admission','estimation_called','policy_called','estimation_handoff_allowed','candidate_model_calls')))

    def test_wrong_entry_not_auto_repaired(self):
        _, item, _ = self.items[0]
        self.assertEqual(adapter.identify_reading(item['bundle'], new_reading(item['raw']), adapter.ENTRY_CLUSTER)['state'], 'DRAFT_INVALID')

    def test_unknown_entry_is_explicit_error(self):
        with self.assertRaises(ValueError): adapter.make_request(self.items[0][1]['bundle'], 'AUTO')


if __name__ == '__main__': unittest.main()
