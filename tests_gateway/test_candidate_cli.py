from __future__ import annotations
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path

from cfm_id_llm.candidate_cli import main
from evaluation.run_mock_candidate_benchmark import benchmark
from tests_gateway.support import ROOT


class CandidateCLIV03Tests(unittest.TestCase):
    def args(self, *extra):
        return [
            '--input',str(ROOT/'examples/weighted_exposure_demo.json'),
            '--mock-formulation',str(ROOT/'examples/weighted_exposure_demo_mock_response.json'),
            '--review',str(ROOT/'examples/TEST_ONLY_review_for_weighted_exposure.json'),
            '--mock-core',str(ROOT/'examples/mock_core_unsupported_scenario.json'),
            '--candidate-provider','mock',
            '--mock-candidate',str(ROOT/'examples/weighted_exposure_demo_mock_candidate.json'),
            '--format','json',*extra,
        ]

    def test_without_preview_does_not_generate(self):
        with io.StringIO() as s,redirect_stdout(s):
            status=main(self.args())
            data=json.loads(s.getvalue())
        self.assertEqual(status,0)
        self.assertEqual(data['routing']['status'],'MOCK_CORE_RESULT')
        self.assertIsNone(data['candidate'])

    def test_preview_explicit_returns_unverified(self):
        with io.StringIO() as s,redirect_stdout(s):
            status=main(self.args('--allow-mock-preview'))
            data=json.loads(s.getvalue())
        self.assertEqual(status,0)
        self.assertEqual(data['candidate']['status'],'UNVERIFIED_CANDIDATE')
        self.assertEqual(data['candidate']['execution_mode'],'MOCK_PREVIEW')
        self.assertFalse(data['candidate']['estimation_handoff_allowed'])
        self.assertIsNone(data['candidate']['mathematical_certificate'])

    def test_text_explains_what_candidate_is(self):
        args=self.args('--allow-mock-preview')
        args[args.index('--format')+1]='text'
        with io.StringIO() as s,redirect_stdout(s):
            status=main(args)
            body=s.getvalue()
        self.assertEqual(status,0)
        self.assertIn('LLM_UNVERIFIED',body)
        self.assertIn('MOCK_PREVIEW',body)
        self.assertIn('Estimation Handoff：禁止',body)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'candidate.json'
            with redirect_stdout(io.StringIO()):
                status=main(self.args('--allow-mock-preview','--output',str(dest)))
            self.assertEqual(status,0)
            data=json.loads(dest.read_text(encoding='utf-8'))
            self.assertEqual(data['candidate']['verification_level'],'LLM_UNVERIFIED')

    def test_missing_review_never_creates_candidate(self):
        args=self.args('--allow-mock-preview')
        idx=args.index('--review');del args[idx:idx+2]
        with io.StringIO() as s,redirect_stdout(s):
            status=main(args)
            data=json.loads(s.getvalue())
        self.assertEqual(status,0)
        self.assertEqual(data['routing']['status'],'AWAITING_HUMAN_REVIEW')
        self.assertIsNone(data['candidate'])

    def test_missing_fixture_fails_safely(self):
        args=self.args('--allow-mock-preview')
        ix=args.index('--mock-candidate')
        del args[ix:ix+2]
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args),2)

    def test_mock_benchmark_has_no_unexpected_status(self):
        result=benchmark()
        self.assertEqual(result['cases'],result['passed'])
        self.assertGreaterEqual(result['cases'],10)
        self.assertEqual(result['real_llm_accuracy'],'NOT_MEASURED')
        self.assertTrue(all(x['verification_level']=='LLM_UNVERIFIED' for x in result['results']))
        self.assertTrue(all(not x['handoff_allowed'] for x in result['results']))

if __name__=='__main__':unittest.main()
