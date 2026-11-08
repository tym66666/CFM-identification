"""v2.8 P1 synthetic showcase replay and capabilities-count regression."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.run_r3_correlated_mixture import generate as gen_demo,write as write_demo
from examples.run_identification_capability_snapshot import (
    generate as gen_snapshot,write as write_snapshot)


class CorrelatedR3ShowcaseV28P1(unittest.TestCase):
    def test_all_demo_results_are_api_derived(self):
        d=gen_demo()
        self.assertEqual(d['node_count'],300)
        self.assertEqual(d['record_count'],9)
        self.assertEqual(d['counts'],{'POINT':4,'NEEDS_INPUT':4,'UNSUPPORTED':1})
        for row in d['cases']:
            self.assertTrue(row['no_numeric_estimate'])
            self.assertEqual(row['replay'],row['status']=='POINT')
            if row['status']=='POINT':
                self.assertEqual(row['route'],'R3_P_STANDARDIZED_EFFECTS')
        self.assertEqual(d['estimator_adapter'],'NO_ADAPTER')
        self.assertFalse(d['scientific_assumptions_verified_in_real_world'])

    def test_byte_identical_reproduction(self):
        with TemporaryDirectory() as a,TemporaryDirectory() as b:
            aa=write_demo(Path(a));bb=write_demo(Path(b))
            for left,right in zip(aa,bb):
                self.assertEqual(left.name,right.name)
                self.assertEqual(left.read_bytes(),right.read_bytes())
            self.assertIn('NO_ADAPTER',aa[0].read_text())

    def test_catalog_4_10_11_and_design_6_exposure_5_are_separate(self):
        d=gen_snapshot()
        self.assertEqual(d['identification_mechanism_count'],4)
        self.assertEqual(d['route_count'],10)
        self.assertEqual(d['documented_premise_name_count'],11)
        self.assertEqual(d['A4_design_premise_name_count'],1)
        self.assertEqual(d['experimental_assignment_count'],6)
        self.assertEqual(d['exposure_mapping_count'],5)
        self.assertEqual(d['conditional_DxE_combination_count'],30)
        self.assertEqual(len(d['observational_population_A4_source_kinds']),5)
        self.assertEqual(d['automated_numerical_estimator_for_new_R3'],'NO_ADAPTER')

    def test_catalog_file_is_deterministic(self):
        with TemporaryDirectory() as a,TemporaryDirectory() as b:
            self.assertEqual(write_snapshot(Path(a)).read_bytes(),
                             write_snapshot(Path(b)).read_bytes())

if __name__=='__main__':unittest.main()
