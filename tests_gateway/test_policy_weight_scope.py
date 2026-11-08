"""Half weight and half treatment are separate business facts."""
import unittest
from cfm_id_llm.quality import _policy_subset_hint
from examples.mean_order_business_fixture import make_case,run

class PolicyWeightScopeTests(unittest.TestCase):
    def test_explicit_evaluation_weights_are_not_partial_treatment(self):
        for text in ('全体都使用。只计算两组，两组各占一半。',
                     '所有人开通，评价两个部门，权重各为一半。',
                     '全体使用。按平均完成率评价甲和乙，各占一半。',
                     '全体使用。两个组的评价权重是一半。'):
            with self.subTest(text=text):self.assertFalse(_policy_subset_hint(text))
    def test_true_half_treatment_and_all_existing_subset_cues_still_flag(self):
        for text in ('只给一半人员开通，比较平均完成率。','一半小组使用系统。','部分员工接受处理。',
                     '只处理两组；评价时各占一半。','only one employee is treated','some employees use it',
                     '全员参与评价，但只给少数人处理。'):
            with self.subTest(text=text):self.assertTrue(_policy_subset_hint(text))
    def test_quota_or_population_half_is_not_erased(self):
        for text in ('平均分配，两个组各占一半名额。','评价后各占一半的人员开通。','两组各占一半。'):
            with self.subTest(text=text):self.assertTrue(_policy_subset_hint(text))
    def test_weights_do_not_hide_independent_treatment_conflict(self):
        for text in ('评价两组，各占一半；只有一半人员使用。',
                     '只给一半员工开通，同时计算两部门结果，各占一半。'):
            with self.subTest(text=text):self.assertTrue(_policy_subset_hint(text))

if __name__=='__main__':unittest.main()

