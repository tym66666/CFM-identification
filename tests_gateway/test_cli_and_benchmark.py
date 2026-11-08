from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from evaluation.run_mock_benchmark import run
from tests_gateway.support import ROOT


class CliBenchmarkTests(unittest.TestCase):
    def run_cli(self, *argv):
        return subprocess.run([sys.executable,'-m','cfm_id_llm',*argv],cwd=ROOT,
                              text=True,capture_output=True,timeout=20)

    def test_json_cli_and_invariants(self):
        p=self.run_cli('--input','examples/sales_ambiguous.json','--mock-response',
                       'examples/sales_ambiguous_mock_response.json','--format','json')
        self.assertEqual(p.returncode,0,p.stderr)
        obj=json.loads(p.stdout)
        self.assertEqual(obj['mathematical_verification'],'NOT_PERFORMED')
        self.assertFalse(obj['estimation_handoff_allowed'])

    def test_text_cli(self):
        p=self.run_cli('--input','examples/sales_ambiguous.json','--mock-response',
                       'examples/sales_ambiguous_mock_response.json','--format','text')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('未运行识别定理',p.stdout)
        self.assertIn('UNRESOLVED',p.stdout)

    def test_output_file_written(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'result.json'
            p=self.run_cli('--input','examples/fixed_quota_policy.json','--mock-response',
                           'examples/fixed_quota_policy_mock_response.json','--format','json','--output',str(file))
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertTrue(file.is_file())
            self.assertEqual(json.loads(file.read_text(encoding='utf8'))['review_status'],'NEEDS_CLARIFICATION')

    def test_real_provider_requires_model(self):
        p=self.run_cli('--input','examples/sales_ambiguous.json','--provider','openai-chat')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('--model',p.stderr)

    def test_no_fixture_argument_is_error(self):
        p=self.run_cli('--input','examples/sales_ambiguous.json')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('--mock-response',p.stderr)

    def test_benchmark(self):
        r=run()
        self.assertEqual(r['fixture_cases'],7)
        self.assertEqual(r['passed'],7)
        self.assertIn('NOT measured',r['scope'])


if __name__ == '__main__': unittest.main()
