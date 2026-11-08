"""Fail-safe presentation checks: this HTML is a viewer, not an ID proof."""
import copy
import json
import unittest

from pfn_pipeline.identification_coverage import run_business_coverage_v22
from examples.run_network_topology_matrix import run_topology_matrix
from examples.run_business_coverage_showcase import _html


class CoverageShowcaseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards=run_business_coverage_v22()
        cls.topo=run_topology_matrix()
        cls.html=_html(cls.cards,cls.topo)

    def test_html_embeds_same_actual_evidence(self):
        self.assertIn('id="results" type="application/json"',self.html)
        start='<script id="results" type="application/json">'
        payload=self.html.split(start,1)[1].split('</script>',1)[0]
        decoded=json.loads(payload)
        self.assertEqual(decoded['coverage'],self.cards)
        self.assertEqual(decoded['topology'],self.topo)

    def test_no_numeric_effect_values_or_claimed_estimators(self):
        self.assertEqual(len(self.cards['cards']),32)
        self.assertTrue(self.cards['point_no_numeric_estimate'])
        self.assertNotIn('estimated_treatment_effect_value',self.html)

    def test_untrusted_card_cannot_end_embedded_json_script(self):
        tainted=copy.deepcopy(self.cards)
        tainted['cards'][0]['business_question']='x</script><script>alert(1)</script>'
        out=_html(tainted,self.topo)
        self.assertEqual(out.count('</script>'),2) # the JSON script end and ordinary JS end
        self.assertIn('x<\\/script><script>alert(1)<\\/script>',out)
        self.assertIn('td.textContent=v',out) # no dynamic innerHTML from data

    def test_demo_discloses_critical_scope_limits(self):
        for value in ('32 张', '81', 'symbolic','POINT','不展示虚构的政策收益'):
            with self.subTest(value=value):
                self.assertIn(value,self.html)


if __name__=='__main__':unittest.main()
