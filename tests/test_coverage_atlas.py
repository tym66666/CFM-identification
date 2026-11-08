"""Coverage atlas is a metadata review, never a theorem / real business-rate oracle."""
import json
from pathlib import Path
import tempfile
import unittest
from examples.build_supervisor_dashboard import snapshot,generate

class SupervisorCoverageAtlasTests(unittest.TestCase):
    def test_metadata_counts_from_implemented_types_not_paper_labels(self):
        x=snapshot()
        self.assertEqual(x['counts'],dict(mechanisms=4,routes=10,design=6,exposure=5,topology_shapes=9,
                            design_exposure_cells=30,premise_names=11))
        self.assertEqual(len(x['scenarios']),16)
        self.assertEqual(len(x['topologies']),9)
        self.assertIn('NOT empirical business coverage',x['caveat'])

    def test_distinguishes_component_coverage_and_supported_point(self):
        x=snapshot()
        self.assertTrue(any('未实现' in c['status'] for c in x['scenarios']))
        self.assertTrue(any('假设' in c['status'] for c in x['scenarios']))
        self.assertIn('target','Target'.lower())
        self.assertNotIn('majority_coverage_percentage',x)

    def test_html_json_are_deterministically_regenerated(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            pa=generate(a);pb=generate(b)
            for p,q in zip(pa,pb): self.assertEqual(p.read_bytes(),q.read_bytes())
            payload=json.loads(pa[0].read_text(encoding='utf-8'))
            html=pa[1].read_text(encoding='utf-8')
            self.assertEqual(payload['counts']['routes'],10)
            for text in ('Design × Exposure','逐实例验证','处理前','NOT empirical business coverage'):
                self.assertIn(text,html)
            self.assertNotIn('__DATA__',html)

    def test_no_live_business_point_or_real_value_claims(self):
        x=snapshot()
        self.assertTrue(all('confidence' in r for r in x['mechanisms']))
        self.assertFalse(any('actual_sales_estimate' in c for c in x['scenarios']))

if __name__=='__main__':unittest.main()
