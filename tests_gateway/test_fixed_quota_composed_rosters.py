"""Composed equal-size rosters retain the original non-authorizing safeguards."""
import unittest
from tests_gateway.test_fixed_quota_wording import audit_wording
class ComposedRosterTests(unittest.TestCase):
    def check(self,text,accepted,quote=None):
        r=audit_wording(text,quote)
        self.assertEqual('A4_UNGROUNDED_FIXED_QUOTA' not in [x.code for x in r.issues],accepted,text)
        self.assertEqual(r.mathematical_verification,'NOT_PERFORMED')
        self.assertFalse(r.estimation_handoff_allowed)
        self.assertTrue(all(a.status!='CERTIFIED' for a in r.draft.assumptions))
    def test_composed_equal_size_rosters(self):
        for text in [
            '试点每次从这4个组里抽出恰好1组使用系统，其余停用；所有1组组成的名单抽中的机会相同。',
            '每轮先在全部由2组组成的名单中等概率抽一份，再让名单上的组启用，其余组不用。',
            '所有由三家构成的名单机会相同，每轮抽一份。',
            '所有十四人组成的名单等概率，每次抽一份实施。',
            '每次在全部由12个站点组成的组合里等概率选一组。',
        ]:
            with self.subTest(text=text):self.check(text,True)
    def test_qualifiers_and_other_designs_not_accepted(self):
        for text in [
            '每轮最多由两组组成的名单等概率。',
            '每轮由大约两组组成的名单等概率。',
            '由三四组组成的名单等概率。',
            '由三四组组成的名单机会相同。',
            '由2.5组组成的名单等概率。',
            '如果由两组组成的名单等概率抽取，将来效果如何？',
            '考虑从由两组组成的名单中等概率抽一份，尚未决定。',
            '原试点并不采用从由两组组成的名单中等概率抽一份的规则。',
            '记录显示，由两组组成的名单等概率被抽中。',
            '各片区分别从由两组组成的名单中等概率抽一份。',
            '由两组组成的名单并非等概率，实际按规模加权选择。',
            '从由两组组成的名单中等概率抽一份，但也可能用三个组。',
            '示例中由两组组成的名单机会相同，当前试点另有安排。',
        ]:
            with self.subTest(text=text):self.check(text,False)
    def test_crop_cannot_hide_qualifiers(self):
        self.check('如果从所有由两组组成的名单中等概率抽一份，效果怎样？',False,'由两组组成的名单中等概率')
        self.check('原实验不采用从由两组组成的名单中等概率抽一份。',False,'由两组组成的名单中等概率')
    def test_separate_sentences_cannot_supply_size(self):
        self.check('本轮名册由两组组成。每轮等概率抽取名单。',False)
    def test_unreported_uniformity_is_not_inferred(self):
        self.check('名册上的两组组成了一个工作组。',False)
if __name__=='__main__':unittest.main()

