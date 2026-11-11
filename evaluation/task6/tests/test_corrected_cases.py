import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]/'corrected_cases'


def case(scenario,variant):
    return json.loads((ROOT/'materials'/f'T6v2-{scenario}-{variant}.json').read_text(encoding='utf8'))


class CorrectedCasesTests(unittest.TestCase):
    def test_missing_versions_remove_conflicting_explicit_claims(self):
        n03=case('N03','missing')
        self.assertNotIn('甲和丙都不启用',n03['business_question'])
        self.assertNotIn('乙的同伴状态固定',n03['sources'][0]['text'])
        self.assertNotIn('保持乙自己不启用',case('N04','missing')['business_question'])
        self.assertNotIn('历史试点为分层固定名额',case('N08','missing')['sources'][0]['text'])
        self.assertNotIn('促销X→接触M',case('D12','missing')['sources'][0]['text'])

    def test_conflicts_preserve_original_text_and_references_are_separate(self):
        for name in ('N03','N04','N08','D12'):
            c=case(name,'conflict')
            original=json.loads((ROOT.parents[0]/'materials'/f'T6-{name}-changed.json').read_text(encoding='utf8'))
            self.assertEqual(c['business_question'],original['business_question'])
            self.assertEqual(c['sources'],original['sources'])
            for variant in ('missing','conflict'):
                ref=json.loads((ROOT/'references'/f'T6v2-{name}-{variant}.json').read_text(encoding='utf8'))
                self.assertTrue(ref['clarification_answer_prepared'])
                self.assertNotIn('clarification_answer_prepared',case(name,variant))


if __name__=='__main__':unittest.main()
