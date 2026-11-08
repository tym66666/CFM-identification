"""Formal-backed is a deterministic *synthetic* identification benchmark.

The legacy 21 raw-business golds intentionally have no scientific population
A4 permissions and must not be relabeled as mathematics-certified cases.
"""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from examples.run_formal_benchmark import main


class FormalBackedSnapshotV291(unittest.TestCase):
    def test_all_nine_routes_and_snapshot_reproducibility(self):
        release = Path(__file__).resolve().parents[1]/'assets/formal_benchmark_assets'/'formal_backed_results.json'
        baseline = json.loads(release.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp)/'rerun.json'
            self.assertEqual(main(['--output',str(generated)]),0)
            self.assertEqual(json.loads(generated.read_text(encoding='utf-8')),baseline)
        self.assertEqual(baseline['count'],36)
        self.assertEqual((baseline['route_count'],baseline['pass_count'],baseline['fail_count']),(9,36,0))
        self.assertFalse(baseline['numeric_estimation_performed'])
        self.assertEqual(baseline['track'],'FORMAL_BACKED_TRACK')
        self.assertEqual(baseline['scenario_counts'],{
            'ADMITTED_FORMAL_TARGET':9,'A4_SOURCE_MISMATCH':9,
            'A5_LICENSE_MISMATCH':9,'ROUTE_APPROVAL_MISMATCH':9})
        self.assertTrue(all(c['expected']==c['actual'] for c in baseline['cases']))
