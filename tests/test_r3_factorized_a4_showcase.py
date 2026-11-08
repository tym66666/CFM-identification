"""Deterministic presentation checks; scenarios run through the official API."""
from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from examples.run_r3_factorized_a4 import write

class FactorizedShowcaseTest(unittest.TestCase):
    def test_live_api_statuses_and_bytewise_regeneration(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            aj,ah,d1=write(Path(a))
            bj,bh,d2=write(Path(b))
            self.assertEqual(aj.read_bytes(),bj.read_bytes())
            self.assertEqual(ah.read_bytes(),bh.read_bytes())
            self.assertEqual(d1['case_counts'],{'POINT':3,'NEEDS_INPUT':3,'UNSUPPORTED':1})
            self.assertIsNone(d1['estimated_effects'])
            self.assertTrue(all(c['full_summary']['identification'] is not None for c in d1['cases']
                                if c['status']=='POINT'))
            self.assertNotIn('finite_sample_estimate',ah.read_text())

if __name__=='__main__':unittest.main()
