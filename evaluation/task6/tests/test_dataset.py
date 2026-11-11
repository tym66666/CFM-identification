import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DatasetContract(unittest.TestCase):
    def test_24_cases_and_splits(self):
        data=[json.loads(p.read_text(encoding='utf8')) for p in (ROOT/'materials').glob('*.json')]
        self.assertEqual(len(data),24)
        self.assertEqual(len({x['case_id'] for x in data}),24)
        self.assertEqual(len({x['case_id'].split('-')[1] for x in data}),12)
        self.assertTrue(all(x['business_question'] and x['sources'] for x in data))
        self.assertTrue(all('gold' not in x and 'expected' not in x for x in data))
        self.assertEqual(sum(x['case_id'].startswith('T6-D') for x in data),4)
    def test_reference_no_implicit_approval(self):
        for p in (ROOT/'references').glob('*.gold.json'):
            x=json.loads(p.read_text(encoding='utf8'))
            self.assertEqual(x['reference_review_status'],'AUTHOR_DRAFT_PENDING_INDEPENDENT_REVIEW')
            self.assertTrue(x['must_not_claim_point_from_a0'])
    def test_no_access_token_in_cases(self):
        for path in (ROOT/'materials').glob('*.json'):
            text=path.read_text(encoding='utf8')
            self.assertNotIn('api_key',text)
            self.assertNotIn('Bearer ',text)

if __name__=='__main__':unittest.main()
