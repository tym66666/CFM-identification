"""Fail-closed Identification-only output and real-Core supervisor cases."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from identification_only import from_verified_core, import_unverified_candidate, research_partial_card
from examples.build_identification_only_demo import build_data, run, STEM
from examples.run_common_business_benchmark import _build_inquiry
from pfn_pipeline import identify_network_business_query
from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21
from research_partial.star7_bounded_r2_policy_demo import generate as partial_generate


class IdentificationOnlyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.point = identify_network_business_query(_build_inquiry('S1','point'))
        cls.blocked = identify_network_business_query(_build_inquiry('S2','zero_support'))

    def report(self, outcome=None, business='合成试验：用户 a 开启功能'):
        return from_verified_core(outcome or self.point, case_id='checked',
            business_question=business, setting='合成', design='D1', exposure='E5',
            information_description='研究者合成声明的 typed A4',
            assumptions_description='明确的随机化、consistency')

    def test_point_replays_actual_core_and_no_estimated_value(self):
        x=self.report()
        self.assertEqual(x['identification']['status'],'POINT')
        self.assertEqual(x['proof']['level'],'CORE_REPLAY_VERIFIED')
        self.assertTrue(x['proof']['replay_verified'])
        self.assertEqual(x['identification']['theorem_route'],'R1A_RANDOMIZED_ARM')
        self.assertEqual(x['identification']['support'],'3/8')
        self.assertIn('mu_i',x['identification']['formula'])
        self.assertIsNone(x['numeric_effect_estimate'])
        self.assertFalse(x['is_real_business_evidence'])
        self.assertFalse(x['business_semantics_independently_certified'])
        with self.assertRaises(ValueError):
            from_verified_core(self.point, case_id='real_claim', business_question='全员处理',
                setting='real', assumptions_description='approved?',
                information_description='A4?', input_provenance='REAL_BUSINESS')

    def test_wrong_route_cannot_publish_a_point_report(self):
        forged=replace(self.point,route='R1B_FULL_ASSIGNMENT')
        with self.assertRaises(ValueError):self.report(forged)

    def test_false_point_without_proof_is_rejected(self):
        forged=VerifiedBusinessOutcomeV21(query_type='ARM',status='POINT',
                   route='R1A_RANDOMIZED_ARM',reason_code=None,result=None)
        with self.assertRaises(ValueError):self.report(forged)

    def test_tampered_certificate_cannot_publish_point(self):
        result=copy.deepcopy(self.point.result)
        result.result['certificate']['joint_arm_support_probability']='1/999'
        forged=replace(self.point,result=result)
        with self.assertRaises((ValueError,AssertionError)):
            self.report(forged)

    def test_unsupported_is_not_noner_identified_or_point(self):
        r=self.report(self.blocked)
        self.assertEqual(r['category'],'UNSUPPORTED')
        self.assertFalse(r['nonidentification_proven'])
        self.assertFalse(r['proof']['replay_verified'])
        self.assertIsNone(r['identification']['formula'])
        self.assertIsNone(r['identification']['theorem_route'])

    def test_unreviewed_llm_cannot_claim_mathematical_status(self):
        r=import_unverified_candidate(business_question='全员使用AI',candidate='LLM 推测可能不可识别')
        self.assertEqual(r['category'],'UNVERIFIED_LLM_CANDIDATE')
        self.assertEqual(r['identification']['status'],'NOT_EVALUATED')
        self.assertIsNone(r['identification']['formula'])
        self.assertFalse(r['nonidentification_proven'])
        self.assertFalse(r['proof']['replay_verified'])
        with self.assertRaises(ValueError):import_unverified_candidate(business_question=' ',candidate='x')

    def test_partial_remains_research_and_no_production_certificate(self):
        part=research_partial_card(partial_generate())
        self.assertEqual(part['category'],'PARTIAL_RESEARCH_ONLY')
        self.assertFalse(part['proof']['replay_verified'])
        self.assertEqual(part['identification']['sharp_width'],'1/7')
        self.assertEqual(part['identification']['illustrative_interval'],['3/7','4/7'])
        x=partial_generate();x['formally_certified_partial']=True
        with self.assertRaises(ValueError):research_partial_card(x)

    def test_cases_still_match_all_eighteen_core_reference_results(self):
        d=build_data()
        self.assertEqual(d['formal_case_count'],27)
        self.assertEqual(d['core_status_counts'],{'POINT':9,'NEEDS_INPUT':10,'UNSUPPORTED':8})
        self.assertEqual(len(set(d['formal_case_ids'])),27)
        self.assertEqual(sum(x['proof']['replay_verified'] for x in d['cases']),9)
        self.assertTrue(all(x['identification']['status']==x['original_expected_status']
                            for x in d['cases'] if 'original_expected_status' in x))
        self.assertFalse(d['production_partial_certified'])

    def test_offline_html_and_json_deterministic(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            a=run(Path(one));b=run(Path(two))
            self.assertEqual([p.read_bytes() for p in a],[p.read_bytes() for p in b])
            html=a[1].read_text(encoding='utf-8')
            self.assertIn('type="file"',html)
            self.assertIn('待审核业务输入 JSON',html)
            self.assertIn('未在浏览器执行 Core / replay',html)
            self.assertNotIn('https://cdn.',html)
            self.assertIn('textContent',html)
            payload=json.loads(a[0].read_text(encoding='utf-8'))
            self.assertEqual(payload['formal_case_count'],27)

    def test_business_text_is_escaped_when_embedded(self):
        from examples.build_identification_only_demo import run as run_gallery
        with tempfile.TemporaryDirectory() as d:
            path=run_gallery(Path(d))[1]
            self.assertNotIn('</script><script>alert',path.read_text(encoding='utf-8'))

    def test_new_identification_modules_never_import_estimation(self):
        root=Path(__file__).resolve().parents[1]
        for file in (root/'identification_only/report.py',
                     root/'examples/build_identification_only_demo.py'):
            body=file.read_text(encoding='utf-8')
            self.assertNotIn('import torch',body)
            self.assertNotIn('pfn_pipeline._internal.estimation',body)


if __name__=='__main__':unittest.main()
