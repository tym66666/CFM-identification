from __future__ import annotations
import unittest

from evaluation.demo_clarification import execute
from evaluation.self_probe import run
from cfm_id_llm.schemas import PopulationInformationLevel


class TestSelfProbeV06(unittest.TestCase):
    def test_eight_self_authored_examples_pass_schema_and_quote_audit(self):
        summary = run()
        self.assertEqual(summary['cases'], 8)
        self.assertEqual(summary['schema_and_quote_passed'], 8)
        self.assertTrue(summary['result_not_independent_accuracy_metric'])
        self.assertFalse(summary['live_llm_api_called'])
        self.assertFalse(summary['mathematical_identification_performed'])
        self.assertTrue(all(x['not_a_verified_identification'] for x in summary['results']))

    def test_observational_case_not_converted_to_randomized(self):
        summary = run()
        row = next(x for x in summary['results'] if x['id'] == 'B24')
        self.assertEqual(row['my_selected_target'], 'ATE')
        self.assertEqual(row['review_status'], 'NEEDS_CLARIFICATION')
        self.assertTrue(row['population_info_not_auto_certified'])

    def test_fixed_policy_query_kept_distinct_from_arm(self):
        summary = run()
        row = next(x for x in summary['results'] if x['id'] == 'B08')
        self.assertEqual(row['my_selected_target'], 'FIXED_POLICY_VALUE')
        self.assertTrue(row['population_info_not_auto_certified'])

    def test_html_demo_escapes_user_supplied_text(self):
        from evaluation.render_normalization_demo import render
        bad=execute()
        bad['user_answer']='<script>alert(1)</script>'
        page=render(bad, run())
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)

    def test_html_demo_explicitly_not_online_accurate(self):
        from evaluation.render_normalization_demo import render
        page=render(execute(),run())
        self.assertIn('不是在线 LLM 准确率',page)
        self.assertIn('尚未科学认证',page)

    def test_followup_updates_reported_design_but_not_A4(self):
        r=execute()
        self.assertEqual(r['initial_assignment'], 'UNRESOLVED')
        self.assertEqual(r['revised_assignment'], 'COMPLETE_RANDOMIZATION')
        self.assertEqual(r['population_information_level'], 'UNRESOLVED')
        self.assertFalse(r['core_formal_spec_generated'])
        self.assertFalse(r['estimation_handoff_allowed'])
        self.assertEqual(r['math_verification'], 'NOT_PERFORMED')
        self.assertEqual(len(r['pending_business_questions']), 1)


if __name__ == '__main__':
    unittest.main()
