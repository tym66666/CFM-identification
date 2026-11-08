"""Demo data must be derived from formal results; static HTML must remain safe."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from examples.run_observational_effects import main


class R3ShowcaseTests(unittest.TestCase):
    def test_demo_11_cards_and_success_rejection_counts(self):
        with TemporaryDirectory() as tmp:
            result=main(Path(tmp))
            self.assertEqual(len(result['cards']),11)
            self.assertEqual(result['counts'],{'POINT':7,'NEEDS_INPUT':3,'UNSUPPORTED':1})
            self.assertEqual(len({c['id'] for c in result['cards']}),11)
            self.assertEqual(len({c['route'] for c in result['cards'] if c['status']=='POINT'}),2)
            self.assertTrue(all(c['proof_targets'] for c in result['cards'][:6]))
            self.assertTrue(all(not c['proof_targets'] for c in result['cards'][7:]))

    def test_demo_bytes_are_deterministic(self):
        with TemporaryDirectory() as a,TemporaryDirectory() as b:
            main(Path(a));main(Path(b))
            for name in ('CFM_ID_v2_6_Observational_Effects_and_Taxonomy.json',
                         'CFM_ID_v2_6_Observational_Effects_and_Taxonomy.html'):
                self.assertEqual((Path(a)/name).read_bytes(),(Path(b)/name).read_bytes())

    def test_html_data_embedding_and_classification_count(self):
        with TemporaryDirectory() as tmp:
            main(Path(tmp))
            page=(Path(tmp)/'CFM_ID_v2_6_Observational_Effects_and_Taxonomy.html').read_text()
            data=json.loads((Path(tmp)/'CFM_ID_v2_6_Observational_Effects_and_Taxonomy.json').read_text())
            self.assertEqual(len(data['classification_audit']),5)
            self.assertIn('data-filter="POINT"',page)
            self.assertIn('R3_OBSERVATIONAL_P_STANDARDIZED_ARM_CONTRAST_FIXED_W_POINT_V1',page)
            self.assertEqual(page.count('type="application/json"'),1)
            self.assertNotIn('sample causal truth values',page)

    def test_rejects_are_not_labeled_nonidentification_proofs(self):
        with TemporaryDirectory() as tmp:
            data=main(Path(tmp))
            self.assertTrue(all('不能把此拒绝当作非识别证明' in c['explanation']
                                for c in data['cards'] if c['status']!='POINT'))


if __name__=='__main__':unittest.main()
