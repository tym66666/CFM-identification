"""Offline mathematical acceptance must fail on disagreement and preserve evidence."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.dag_frontdoor_acceptance import graph_audit, arithmetic_audit, main


class FrontdoorAcceptanceTests(unittest.TestCase):
    def test_all_four_node_graphs_and_larger_samples_agree(self):
        result, _ = graph_audit()
        self.assertEqual(result['exhaustive_four_node_dags'], 543)
        self.assertEqual(result['sampled_larger_graphs'], 256)
        self.assertEqual(set(result['condition_patterns']), {'000','001','010','011','100','101','110','111'})
        self.assertGreater(result['certified_candidates_replayed'], 0)

    def test_checker_disagreement_cannot_pass(self):
        with patch('evaluation.dag_frontdoor_acceptance.check_candidate',
                   return_value=({'FD1':False,'FD2':False,'FD3':False}, {})):
            with self.assertRaisesRegex(ValueError, 'graph checker disagreement'):
                graph_audit()

    def test_exact_formula_and_condition_failure_witnesses(self):
        result = arithmetic_audit([])
        self.assertEqual(result['positive_models'], 128)
        self.assertEqual(result['exact_equalities'], 512)
        self.assertEqual(len(result['expression_error_witnesses']), 2)
        for row in result['negative_examples']:
            self.assertGreater(row['mismatching_models'], 0)
            self.assertFalse(row['general_nonidentification_proved'])

    def test_cli_requires_selection_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'evaluation.dag_frontdoor_acceptance.evaluate', side_effect=AssertionError('unexpected evaluation')):
            path = Path(folder) / 'report.json'
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--output', str(path)])
            self.assertFalse(path.exists())
            path.write_text('preserved', encoding='utf8')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--allow-synthetic-reviews','--output',str(path)])
            self.assertEqual(path.read_text(encoding='utf8'), 'preserved')


if __name__ == '__main__':
    unittest.main()

