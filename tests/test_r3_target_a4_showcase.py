"""Synthetic R3 cross-source audit showcase records, reproducibility and no estimates."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.run_r3_target_a4_audit import generate,write

class R3TargetA4ShowcaseTests(unittest.TestCase):
    def test_all_rows_are_derived_and_no_numerical_adapter(self):
        data=generate()
        self.assertEqual(data['result_count'],4)
        cases=data['cases']
        self.assertEqual(sum(c['can_merge_as_one_symbolic_target'] for c in cases),2)
        self.assertEqual([c['relationship'] for c in cases],
            ['SAME_TARGET','CONFLICTING_OR_UNRESOLVED_A4_SOURCE',
             'DISTINCT_DECLARED_TARGET','SAME_TARGET'])
        self.assertEqual(data['one_target_handoff']['estimation']['status'],'NO_ADAPTER')
        self.assertFalse(data['one_target_handoff']['conditional_mean_values_reconciled'])
        self.assertEqual(data['data_kind'],'SYNTHETIC_SYMBOLIC_POPULATION')

    def test_regeneration_is_byte_deterministic_and_complete(self):
        with TemporaryDirectory() as a,TemporaryDirectory() as b:
            first=write(Path(a));second=write(Path(b))
            self.assertEqual([p.name for p in first],[p.name for p in second])
            for p,q in zip(first,second):
                self.assertEqual(p.read_bytes(),q.read_bytes())
            self.assertIn('can be proved by this dashboard',first[0].read_text())

if __name__=='__main__':unittest.main()
