from copy import deepcopy
from pathlib import Path
import json
import unittest
from evaluation import business_d1_staged as new
from evaluation import business_d1_aggregation as prior
from evaluation.business_d1_submission import identify_submission
from examples.nbib_d1_fixture import synthetic_context


class RemainingDecisionTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((Path(__file__).resolve().parents[1] / 'assets/d1_condition_fixtures/materials_cases.json').read_text(encoding='utf8'))

    def example(self, name='DEV49-missing-remaining', cite=True):
        item = deepcopy(self.cases[name])
        raw = dict(questions=deepcopy(item['raw']['questions']))
        for q in raw['questions'].values():
            source, quote = q.pop('remaining_source'), q.pop('remaining_evidence_span')
            rule = '原抽签条件平均' if source else '未确定'
            if not source and cite:
                source = 'target_clarification.txt:L4'
                quote = item['bundle']['documents']['target_clarification.txt'].splitlines()[3]
            q['remaining'] = dict(rule=rule, source=source, quote=quote)
        return item, raw

    def compose(self, item, raw):
        return new.compose_reading(item['bundle'], dict(study=item['raw']['study']), raw)

    def test_unknown_can_have_real_evidence_without_becoming_confirmation(self):
        i, raw = self.example(); r = self.compose(i, raw)
        self.assertEqual(r['state'], 'NEEDS_INPUT')
        self.assertTrue(all(x['remaining_source'] is None for x in r['draft']['questions'].values()))
        self.assertEqual(r['remaining_decisions']['q1'], raw['questions']['q1']['remaining'])
        self.assertEqual({x['field'] for x in r['clarification_questions']}, {'remaining'})
        self.assertFalse(r['core_called'])

    def test_unknown_without_evidence_is_allowed(self):
        i, raw = self.example(cite=False)
        self.assertEqual(self.compose(i, raw)['state'], 'NEEDS_INPUT')

    def test_no_raw_mutation(self):
        i, raw = self.example(); before = deepcopy(raw); r = self.compose(i, raw)
        self.assertEqual(before, raw); self.assertEqual(r['target_candidate'], raw)

    def test_projection_retains_all_other_coordinates(self):
        i, raw = self.example(); projected, _ = new.project_target_candidate(i['bundle'], raw)
        self.assertEqual(projected, dict(questions=i['raw']['questions']))

    def test_uncertain_quote_cannot_confirm_original_rule(self):
        i, raw = self.example(); raw['questions']['q1']['remaining']['rule'] = '原抽签条件平均'
        r = self.compose(i, raw)
        self.assertEqual(r['state'], 'DRAFT_INVALID'); self.assertFalse(r['core_called'])
        self.assertEqual(r['reason_code'], 'DECLARED_REMAINING_CONTRADICTS_QUOTED_EVIDENCE')

    def test_fabricated_quote_is_rejected(self):
        i, raw = self.example(); raw['questions']['q1']['remaining']['quote'] = '已经决定沿用抽签。'
        self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_non_target_source_is_rejected(self):
        i, raw = self.example(); raw['questions']['q1']['remaining']['source'] = 'study_protocol.md:L3'
        self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_incomplete_citation_pair_is_rejected(self):
        for field in ('source', 'quote'):
            i, raw = self.example(); raw['questions']['q1']['remaining'][field] = None
            self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_positive_requires_citation(self):
        i, raw = self.example(cite=False); raw['questions']['q1']['remaining']['rule'] = '原抽签条件平均'
        self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_old_and_new_fields_cannot_be_mixed(self):
        i, raw = self.example(); raw['questions']['q1']['remaining_source'] = None
        self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_malformed_or_incomplete_questions_fail_closed(self):
        i, raw = self.example()
        for value in ({'questions': []}, {'questions': {'q1': None}}, {'questions': {'q1': {}}}, {'questions': {'q1': raw['questions']['q1']}}):
            self.assertEqual(self.compose(i, value)['state'], 'DRAFT_INVALID')

    def test_unknown_rule_enum_rejected(self):
        i, raw = self.example(); raw['questions']['q1']['remaining']['rule'] = '差不多按原规则'
        self.assertEqual(self.compose(i, raw)['state'], 'DRAFT_INVALID')

    def test_other_arrangement_not_admitted_as_original(self):
        i, raw = self.example(); line = '其他经理全部关闭权限。'
        lines = i['bundle']['documents']['target_clarification.txt'].splitlines(); lines[3] = line
        i['bundle']['documents']['target_clarification.txt'] = '\n'.join(lines)
        for q in raw['questions'].values():
            q['remaining'].update(rule='其他安排', quote=line)
        r = self.compose(i, raw)
        self.assertEqual(r['state'], 'UNSUPPORTED'); self.assertFalse(r['core_called'])
        self.assertEqual(r['candidate_model_calls'], 0); self.assertFalse(r['production_admission'])

    def test_missing_design_does_not_read_targets(self):
        i, raw = self.example(); i['raw']['study'].update(exposure=None, exposure_source=None)
        r = self.compose(i, raw); self.assertEqual(r['state'], 'NEEDS_INPUT')
        self.assertFalse(r['target_normalization_performed']); self.assertIsNone(r['draft'])

    def test_known_weights_preserved_with_unknown_population(self):
        i, raw = self.example('DEV49-missing-population'); r = self.compose(i, raw)
        self.assertEqual(r['state'], 'NEEDS_INPUT'); self.assertEqual({x['field'] for x in r['clarification_questions']}, {'population'})

    def test_request_only_changes_contract_not_business_documents(self):
        i, raw = self.example(); study = dict(study=i['raw']['study'])
        _, old = prior.target_request(i['bundle'], study); system, new_user = new.target_request(i['bundle'], study)
        old, new_user = json.loads(old), json.loads(new_user); old.pop('output_schema'); schema = new_user.pop('output_schema')
        self.assertEqual(old, new_user); self.assertNotIn('remaining_source', system)
        q = schema['$defs']['Question']; self.assertIn('remaining', q['required']); self.assertNotIn('remaining_source', q['properties'])

    def test_positive_projection_matches_previous_reading(self):
        i, raw = self.example('NBIB-001-two-effects-v047'); r = self.compose(i, raw)
        self.assertEqual(r['draft'], i['raw']); self.assertEqual(r['state'], 'REVIEW_REQUIRED')
        self.assertFalse(r['core_called']); self.assertFalse(r['evidence_is_semantic_proof'])

    def test_reviewed_positive_has_two_real_certificates(self):
        i, raw = self.example('NBIB-001-two-effects-v047'); r = self.compose(i, raw); i['raw'] = r['draft']
        result = identify_submission(i['bundle'], i['raw'], i['packet'], context=synthetic_context(i), synthetic_protocol_selected=True)
        self.assertEqual(result['state'], 'CORE_POINT'); self.assertEqual(len(result['query_views']), 2)
        self.assertTrue(all(x['certificate_replayed'] for x in result['query_views']))


if __name__ == '__main__':
    unittest.main()
