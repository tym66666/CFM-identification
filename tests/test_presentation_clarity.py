"""Business-first supervisor display invariants, not a new identification theorem."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest

from cfm_id.business_presentation import (
    CONDITION_NAMES, STATE_LABEL, enhance_payload, explain_formal_case,
    load_original_nbib_benchmark,
)
from examples.build_supervisor import build_payload, render


class SupervisorReadabilityContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_payload()
        cls.by_id = {c['case_id']: c for c in cls.data['core_cases']}
        cls.view = cls.data['presentation']['cases']

    def test_27_real_formal_results_not_overwritten(self):
        self.assertEqual(len(self.by_id), 27)
        self.assertEqual(self.data['summary'], {'POINT': 9, 'NEEDS_INPUT': 10, 'UNSUPPORTED': 8})
        self.assertEqual(len(self.view), 27)
        self.assertTrue(all(c['proof']['replay_verified'] for c in self.by_id.values()
                            if c['identification']['status'] == 'POINT'))

    def test_21_business_language_benchmark_is_separate_and_not_certified(self):
        records = load_original_nbib_benchmark()
        self.assertEqual(len(records), 21)
        self.assertEqual({b['id'] for b in records}, {'NBIB-%03d' % i for i in range(1,22)})
        self.assertTrue(all(b['mathematical_status'] == 'NOT_FORMALLY_CHECKED' for b in records))
        self.assertTrue(all(b['questions'] and b['original_description'] for b in records))
        self.assertTrue(all(next(x for x in b['display_conditions'] if x['label']=='所需总体研究信息')['state']=='missing' for b in records))
        self.assertIn('销售', records[0]['original_description'])

    def test_canonical_chinese_conditions_for_every_case(self):
        keys = tuple(c[0] for c in CONDITION_NAMES)
        labels = tuple(c[1] for c in CONDITION_NAMES)
        for c in self.view.values():
            self.assertEqual(tuple(a['id'] for a in c['conditions']), keys)
            self.assertEqual(tuple(a['label'] for a in c['conditions']), labels)
            self.assertTrue(all(x['state'] in STATE_LABEL for x in c['conditions']))
            self.assertTrue(c['question'] and c['business_context'])
            self.assertTrue(all(a['case_specific_explanation'] for a in c['conditions']))

    def test_formal_point_checkmarks_require_replay(self):
        for cid, raw in self.by_id.items():
            v = self.view[cid]
            if raw['identification']['status'] == 'POINT':
                self.assertTrue(raw['proof']['replay_verified'])
                self.assertTrue(all(x['state'] == 'confirmed' for x in v['conditions']))

    def test_cannot_promote_unverified_point_to_checkmarks(self):
        wrong = json.loads(json.dumps(self.by_id['S1-point']))
        wrong['proof']['replay_verified'] = False
        with self.assertRaises(AssertionError): explain_formal_case(wrong)

    def test_missing_source_and_missing_science_are_distinguished(self):
        a4 = {x['id']: x['state'] for x in self.view['S6-a4_sample_only']['conditions']}
        a5 = {x['id']: x['state'] for x in self.view['S6-a5_missing']['conditions']}
        self.assertEqual(a4['information'], 'missing')
        self.assertEqual(a5['assumptions'], 'missing')
        self.assertEqual(a4['support'], 'unchecked')
        self.assertEqual(a5['support'], 'unchecked')
        d6 = self.view['S5-a5_missing']
        science = next(x for x in d6['conditions'] if x['id'] == 'assumptions')
        self.assertIn('名额方案公告', science['case_specific_explanation'])

    def test_zero_support_is_not_theorem_nonidentification(self):
        for cid in ('S2-zero_support','S3-zero_support','S4-zero_support','S5-zero_support',
                    'GOLDEN-zero_quota','GOLDEN-add_network_edge'):
            raw = self.by_id[cid]
            self.assertEqual(raw['identification']['status'], 'UNSUPPORTED')
            v = self.view[cid]
            self.assertEqual(next(x for x in v['conditions'] if x['id']=='support')['state'],'failed')
            self.assertIn('不能据此断言',v['next_step_plain'])

    def test_zero_support_business_question_matches_actual_target_changed(self):
        self.assertIn('另外三名', self.view['S2-zero_support']['question'])
        self.assertIn('所有关联同事都没使用', self.view['S3-zero_support']['question'])
        self.assertIn('两名', self.view['S4-zero_support']['question'])
        self.assertIn('恰好两位', self.view['S5-zero_support']['question'])
        self.assertIn('恰好一位', self.view['S1-point_e4']['question'])
        self.assertIn('使用比例分档', self.view['GOLDEN-different_exposure']['question'])
        self.assertIn('本人已经使用 AI', self.view['S6-point']['question'])
        self.assertTrue(all(arm['own_treatment'] == 1 for arm in self.by_id['S6-point']['identification']['support'][0]))

    def test_rejected_assumption_distinguished_from_missing(self):
        missing = self.view['GOLDEN-a5_unresolved']['conditions']
        rejected = self.view['GOLDEN-a5_rejected']['conditions']
        self.assertEqual(next(x for x in missing if x['id']=='assumptions')['state'],'missing')
        self.assertEqual(next(x for x in rejected if x['id']=='assumptions')['state'],'failed')

    def test_research_partial_cannot_acquire_formal_certificate(self):
        r = self.data['research_partial']
        self.assertFalse(r['proof']['replay_verified'])
        self.assertEqual(r['category'],'PARTIAL_RESEARCH_ONLY')
        self.assertNotIn(r['case_id'],self.view)

    def test_page_contains_benchmark_and_condition_legend(self):
        with tempfile.TemporaryDirectory() as tmp:
            pages = render(Path(tmp))
            text = pages[1].read_text(encoding='utf8')
            self.assertIn('NBIB', text)
            self.assertIn('所需总体研究信息', text)
            self.assertIn('严格零支持',text)
            self.assertIn('只表示这份合成输入',text)
            self.assertIn('业务理解题 · 尚未认证',text)
            self.assertNotIn('https://cdn.',text)

    def test_pages_are_deterministic_and_coverage_kept(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            x,y = render(Path(a)),render(Path(b))
            self.assertEqual([p.read_bytes() for p in x],[p.read_bytes() for p in y])
        d=self.data['coverage']
        self.assertEqual((len(d['designs']),len(d['exposures']),len(d['topologies']),len(d['scenarios'])),(6,5,9,16))


if __name__=='__main__':unittest.main()
