"""Offline six common-setting benchmark: actual Core outputs + independent replay.

No online LLM, no real business science authorization, no outcome estimates.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from examples.run_common_business_benchmark import (
    BUSINESSES,VARIANTS,generate,run,render_html,
    _digest,_build_inquiry,
)
from research_partial.star7_bounded_r2_policy_demo import (
    NODES,bound_for_leaves,generate as partial_generate,support_table,witness_checks,
    world_outcome,run as partial_run,
)

class BusinessFormalBenchmarkV293(unittest.TestCase):
    def test_all_six_common_scenarios_are_distinct(self):
        self.assertEqual(len(BUSINESSES),6)
        self.assertEqual({x[3] for x in BUSINESSES},{'D1','D2','D4','D5','D6','OBS'})
        self.assertEqual(len(set(x[0] for x in BUSINESSES)),6)
        self.assertEqual(len(VARIANTS),18)

    def test_all_cases_true_core_and_verified_positive_replay(self):
        b=generate()
        self.assertEqual(b['case_count'],18)
        self.assertEqual(b['pass_count'],18)
        self.assertEqual(b['status_counts'],{'POINT':7,'NEEDS_INPUT':7,'UNSUPPORTED':4})
        self.assertTrue(all(x['passed'] for x in b['cases']))
        self.assertTrue(all(x['has_verified_core_result'] for x in b['cases'] if x['actual_status']=='POINT'))
        self.assertTrue(all(not x['has_verified_core_result'] for x in b['cases'] if x['actual_status']!='POINT'))
        self.assertTrue(all(x['numeric_effect_estimate'] is None for x in b['cases']))

    def test_zero_support_is_not_labeled_proved_nonidentification(self):
        b=generate()
        zeros=[x for x in b['cases'] if x['variant']=='zero_support']
        self.assertEqual(len(zeros),4)
        self.assertTrue(all(x['reason']=='ZERO_ARM_SUPPORT' for x in zeros))
        self.assertTrue(all(x['actual_status']=='UNSUPPORTED' for x in zeros))
        self.assertFalse('NON_IDENTIFIED' in {x['actual_status'] for x in zeros})

    def test_missing_a4_and_a5_are_safe_refusals(self):
        b=generate()
        missing=[x for x in b['cases'] if x['variant'] in ('a4_missing','a4_sample_only','a5_missing')]
        self.assertEqual(len(missing),7)
        self.assertTrue(all(x['actual_status']=='NEEDS_INPUT' for x in missing))
        self.assertTrue(all(x['route'] is None for x in missing))

    def test_business_contract_digest_tamper_sensitive(self):
        a={'business_scenario':'S2','intent':'全员开放AI','target_kind':'fixed_policy',
           'assignment':(1,1,1)}
        b={**a,'assignment':(1,0,0)}
        self.assertNotEqual(_digest(a),_digest(b))

    def test_identification_routes_not_silently_replaced_by_llm(self):
        b=generate()
        self.assertEqual({x['route'] for x in b['cases'] if x['actual_status']=='POINT'},
            {'R1A_RANDOMIZED_ARM','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'})
        self.assertEqual(b['raw_language_evaluation'],'NOT_PERFORMED')
        self.assertEqual(b['approvals'],'HYPOTHETICAL_FIXED_FIXTURES_NOT_REAL_INDEPENDENT_REVIEW')

    def test_deterministic_json_and_offline_html(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            p=run(Path(a));q=run(Path(b))
            self.assertEqual(len(p),2)
            for left,right in zip(p,q): self.assertEqual(left.read_bytes(),right.read_bytes())
            page=p[1].read_text(encoding='utf8')
            self.assertIn('六类常用网络干扰业务',page)
            self.assertIn('Core + 独立 Replay',page) if 'Core + 独立 Replay' in page else self.assertIn('数学 Core + 独立 Replay',page)
            self.assertNotIn('https://cdn.',page)
            self.assertNotIn('点识别比例代表实际业务',page)

class PartialResearchOnlyStar7(unittest.TestCase):
    def test_support_by_existing_engine_and_independent_35_assignments(self):
        s=support_table()
        self.assertEqual(s['hub'],'0')
        self.assertEqual({v for k,v in s.items() if k!='hub'},{'1/7'})

    def test_symbolic_sharp_bounds_and_witness_pair(self):
        means={leaf:Fraction(1,2) for leaf in NODES[1:]}
        self.assertEqual(bound_for_leaves(means),(Fraction(3,7),Fraction(4,7)))
        self.assertEqual(witness_checks(),['3/7','4/7'])
        for m in (Fraction(0),Fraction(1)):
            self.assertEqual(world_outcome('hub',NODES,m),m)

    def test_invalid_bounded_outcome_mean_cannot_enter(self):
        with self.assertRaises(ValueError):
            bound_for_leaves({leaf:Fraction(3,2) for leaf in NODES[1:]})
        with self.assertRaises(ValueError):
            bound_for_leaves({'leaf1':Fraction(1,2)})
        with self.assertRaises(ValueError):
            world_outcome('hub',NODES,Fraction(2))

    def test_research_flag_and_reproducible_json(self):
        b=partial_generate()
        self.assertEqual(b['status'],'RESEARCH_ONLY')
        self.assertFalse(b['formally_certified_partial'])
        self.assertIsNone(b['production_route'])
        self.assertEqual(b['sharp_width'],'1/7')
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as c:
            self.assertEqual(partial_run(Path(a)).read_bytes(),partial_run(Path(c)).read_bytes())

if __name__=='__main__':unittest.main()

class SupervisorCombinedAtlasV293(unittest.TestCase):
    def test_metadata_formal_cases_and_partial_labels_are_separated(self):
        from examples.build_supervisor_business_atlas import data
        x=data()
        self.assertEqual(x['metadata']['counts']['routes'],10)
        self.assertEqual(x['formal_business']['case_count'],18)
        self.assertTrue(x['not_real_business_coverage'])
        self.assertFalse(x['numeric_estimation_performed'])
        self.assertFalse(x['isolated_partial_research']['formally_certified_partial'])

    def test_offline_supervisor_html_is_deterministic(self):
        from examples.build_supervisor_business_atlas import run
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            p=run(Path(a));q=run(Path(b))
            for f,g in zip(p,q):self.assertEqual(f.read_bytes(),g.read_bytes())
            txt=p[1].read_text(encoding='utf8')
            for s in ('PARTIAL 研究示例','真实 Core + 独立 replay', '固定 7 人星型协作网络', 'v2.9.2'):
                self.assertIn(s,txt)
            self.assertNotIn('__DATA__',txt)
            self.assertNotIn('__JS__',txt)
