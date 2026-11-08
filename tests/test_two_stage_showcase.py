"""Published v2.7 visualization is deterministic and produced by verified APIs."""
from __future__ import annotations
from tempfile import TemporaryDirectory
from pathlib import Path
import hashlib
import json
import unittest
from examples.run_two_stage import run


class TestTwoStageShowcase(unittest.TestCase):
    def test_actual_theorem_statuses_and_reproducible_files(self):
        with TemporaryDirectory() as left, TemporaryDirectory() as right:
            data=run(Path(left)); second=run(Path(right))
            self.assertEqual(data,second)
            self.assertEqual(data['case_count'],11)
            self.assertEqual(data['counts'],{'POINT':8,'NEEDS_INPUT':2,'UNSUPPORTED':1})
            self.assertEqual({c['route'] for c in data['cases'] if c['status']=='POINT'},
                             {'R1A_RANDOMIZED_ARM','R1B_FULL_ASSIGNMENT','R2_MEAN_SIGNATURE'})
            for case in data['cases']:
                if case['status']=='POINT':
                    self.assertTrue(case['theorem_verified'])
                else:
                    self.assertIsNone(case['route'])
                    self.assertTrue(case['reason'])
            r2=next(c for c in data['cases'] if c['route']=='R2_MEAN_SIGNATURE')
            self.assertIn('q(z)=0;',r2['exact_support'])
            self.assertIn('min signature support=',r2['exact_support'])
            self.assertEqual(sum(c['size']==300 for c in data['cases']),3)
            for name in ('CFM_ID_v2_7_Two_Stage_Identification.json',
                         'CFM_ID_v2_7_Two_Stage_Identification.html'):
                self.assertEqual(hashlib.sha256((Path(left)/name).read_bytes()).digest(),
                                 hashlib.sha256((Path(right)/name).read_bytes()).digest())
            self.assertEqual(json.loads((Path(left)/'CFM_ID_v2_7_Two_Stage_Identification.json').read_text()),data)

if __name__=='__main__':unittest.main()
