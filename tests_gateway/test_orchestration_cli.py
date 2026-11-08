from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests_gateway.support import ROOT


class RoutingCliV02Tests(unittest.TestCase):
    def cli(self, *argv):
        return subprocess.run([sys.executable, '-m', 'cfm_id_llm.orchestration_cli',
                               '--input', 'examples/complete_formulation_demo.json',
                               '--mock-response', 'examples/complete_formulation_demo_mock_response.json',
                               *argv], cwd=ROOT, capture_output=True, text=True, timeout=20)

    def test_without_review_does_not_call_core(self):
        r=self.cli('--mock-core','examples/mock_core_point_scenario.json','--format','json')
        self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads(r.stdout)
        self.assertEqual(data['routing']['status'],'AWAITING_HUMAN_REVIEW')
        self.assertIsNone(data['routing']['core_status'])

    def test_demo_review_with_point_is_mock_only(self):
        r=self.cli('--review','examples/TEST_ONLY_review_for_complete_case.json',
                   '--mock-core','examples/mock_core_point_scenario.json','--format','json')
        self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads(r.stdout)
        self.assertEqual(data['routing']['verification_level'],'MOCK_ONLY')
        self.assertEqual(data['routing']['core_status'],'POINT')
        self.assertFalse(data['routing']['estimation_handoff_allowed'])
        self.assertEqual(data['routing']['core_certificate']['kind'],'MOCK_TEST_ONLY')

    def test_unsupported_is_software_limit_not_math_non_identified(self):
        r=self.cli('--review','examples/TEST_ONLY_review_for_complete_case.json',
                   '--mock-core','examples/mock_core_unsupported_scenario.json','--format','text')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('真实库未接入', r.stdout)
        self.assertNotIn('非识别证明已完成',r.stdout)

    def test_replay_failure_not_rewritten_as_candidate(self):
        r=self.cli('--review','examples/TEST_ONLY_review_for_complete_case.json',
                   '--mock-core','examples/mock_core_replay_rejected_scenario.json','--format','json')
        self.assertEqual(r.returncode,0,r.stderr)
        obj=json.loads(r.stdout)['routing']
        self.assertEqual(obj['status'],'CORE_VERIFICATION_FAILED')
        self.assertEqual(obj['fallback'],'BLOCKED_SAFETY_FAILURE')

    def test_pending_review_template_is_not_confirmation(self):
        r=self.cli('--review','examples/review_template_demo_pending.json','--format','text')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('ValidationError',r.stderr)

    def test_cli_can_generate_pending_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'review.json'
            r=self.cli('--review-template',str(path),'--format','json')
            self.assertEqual(r.returncode,0,r.stderr)
            template=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(template['decision'],'PENDING_CHANGE_TO_CONFIRMED_AFTER_REAL_REVIEW')
            self.assertEqual(len(template['draft_sha256']),64)
            self.assertEqual(json.loads(r.stdout)['routing']['status'],'AWAITING_HUMAN_REVIEW')

    def test_missing_review_file_does_not_get_autoapproved(self):
        r=self.cli('--review','examples/not_real_file.json')
        self.assertNotEqual(r.returncode,0)

    def test_mock_routing_benchmark(self):
        from evaluation.run_mock_routing_benchmark import run
        result=run()
        self.assertEqual(result["passed"], result["fixture_cases"])
        self.assertEqual(result["fixture_cases"], 8)
        self.assertIn("NOT real", result["scope"])

    def test_ambiguous_business_case_blocks_even_with_mock_core(self):
        r=subprocess.run([sys.executable,'-m','cfm_id_llm.orchestration_cli',
            '--input','examples/sales_ambiguous.json',
            '--mock-response','examples/sales_ambiguous_mock_response.json',
            '--mock-core','examples/mock_core_point_scenario.json','--format','json'],
            cwd=ROOT, capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['routing']['status'],'NEEDS_CLARIFICATION')


if __name__ == '__main__': unittest.main()
