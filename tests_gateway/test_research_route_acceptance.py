"""Reference runner boundaries and failure accounting, entirely offline."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.research_route_acceptance import evaluate_references,main


class ResearchAcceptanceTests(unittest.TestCase):
    def test_reference_states_and_review_records(self):
        report=evaluate_references()
        self.assertEqual(report['cases'],92)
        self.assertEqual(set(report['routes']),{'DAG_CLASSICAL_BACKDOOR','DAG_ADJUSTMENT','MEAN_ORDER_D2_E1','DAG_CLASSICAL_FRONTDOOR'})
        self.assertEqual(set(report['states']),{'POINT','PARTIAL','INCOMPATIBLE','NEEDS_INPUT','REVIEW_REQUIRED','UNSUPPORTED','CHECK_BLOCKED'})
        self.assertEqual(report['http_calls'],0)
        for row in report['rows']:
            self.assertIn('review',row)
            self.assertEqual(row['expected_state'],row['result']['state'])

    def test_bad_result_is_rejected_before_pass_report(self):
        with patch('evaluation.research_route_acceptance.run_registered_route',return_value={'state':'UNSUPPORTED'}):
            with self.assertRaisesRegex(ValueError,'REFERENCE_ACCEPTANCE_FAILED'):
                evaluate_references()

    def test_cli_requires_explicit_fixture_selection_and_preserves_old_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'evidence.json'
            with patch('evaluation.research_route_acceptance.evaluate_references',side_effect=AssertionError('unexpected evaluation')):
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    main(['--output',str(path)])
                self.assertFalse(path.exists())
                path.write_text('existing evidence',encoding='utf8')
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    main(['--allow-synthetic-reviews','--output',str(path)])
                self.assertEqual(path.read_text(encoding='utf8'),'existing evidence')


if __name__=='__main__':unittest.main()
