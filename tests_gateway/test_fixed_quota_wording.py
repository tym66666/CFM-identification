"""Public audit acceptance: synonyms and adversarial source context, offline."""
from copy import deepcopy
import unittest

from cfm_id_llm.audit import audit_draft, DraftEvidenceError
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec
from tests_gateway.support import case_and_draft

POSITIVE = [
    '原试点每轮从六家门店均匀随机选四家使用工具。',
    '原试点每轮从六家门店均匀随机抽取四家使用工具。',
    '原试点每轮从六家门店均匀抽出四家使用工具。',
    '每轮随机选定四个窗口启用，其余窗口不开通。',
    '每轮从六家门店随机选择4家启用。',
    '每轮从六家门店随机挑选四家启用。',
    '每轮从六家门店随机抽四家启用。',
    '每次恰好随机抽取四人使用工具。',
    '每次正好随机抽取四人使用工具。',
    '每轮均匀随机抽出恰好4个站点。',
    '每次从三十名员工中均匀抽取十四人。',
    '每次从300名员工中随机抽取150人。',
    '每轮从六家门店随机选４家启用。',
    '原实验采用固定名额随机分配。',
    '原实验采用完全随机化设计。',
    '全部四店名单机会相同，每轮抽一份实施。',
    '每轮均匀抽四家；工具效果可能不同。',
    '每轮均匀抽四家，结果可能不同。',
    '原试验不是逐人独立抽签，而是每轮均匀随机抽四家。',
    'Each trial randomly selects four stores from six.',
    'The experiment uses complete randomization.',
    'The trial uses a fixed quota and random assignment.',
    'All four-store subsets are equally likely.',
    '原试点采取抽签方式，每轮选出四家启用。',
    '规定处理人数为四人，使用随机抽签决定具体名单。',
    '已确定下周的实验协议：每轮均匀随机选四家。',
    '每轮不放回随机抽四家。',
    'Exactly 150 of the 300 salespeople were selected uniformly without replacement.',
    '处理前固定合作网络。完全随机化实验每次恰好从四名员工中随机选两人分配 AI，其余两人不分配。一致性 Yobs=Y(T)；不接受任何 exposure sufficiency 或 mean-signature sufficiency。',
    '每轮从六家门店中随机抽取四家，其余两家不使用工具。',
    '每轮随机选取四人，剩余人员未被分配干预。',
]

NEGATIVE = [
    '原试点随机给一半人使用。',
    '每轮最多随机抽取四家使用。',
    '每轮随机抽取最多四家使用。',
    '每轮至多恰好四人中签。',
    '每轮随机抽取至少四家使用。',
    '每轮随机抽取不超过四家使用。',
    '每轮随机抽取不少于四家使用。',
    '每轮随机抽取大约四家使用。',
    '每轮随机抽取约四家使用。',
    '每轮随机抽取四家左右。',
    '每轮随机抽取四至五家。',
    '每轮随机抽取四家或者五家。',
    '每轮随机抽取三四家。',
    '每轮随机抽取3.5家。',
    '平均每轮随机抽取四家使用。',
    '每轮可能随机抽取四家。',
    '拟考虑采用固定名额随机分配，尚未决定。',
    '没有说明是否固定名额随机分配。',
    '原实验不是固定名额随机分配。',
    '原实验并非完全随机化。',
    '每人独立抛硬币，本次观察到恰好四人中签。',
    '本次记录显示随机抽中了恰好四家。',
    '随机启用人数的均值是四家。',
    '如果以后每轮随机选四家，效果如何？',
    '下周是否每轮随机选四家？',
    '未来固定四家启用能怎样？',
    '预算只够四家，按需给企业开通。',
    '每个片区分别随机抽四家。',
    '各组均匀随机抽取四家。',
    '从六家中有放回随机抽取四次。',
    '从六家中有放回随机抽取四家。',
    '每轮按规模权重随机抽四家，不同四家名单概率不同。',
    '每轮随机抽四家，但处理总人数不固定。',
    '每轮随机抽四家，但也可能选五家。',
    'Four stores happened to be selected by independent coin flips.',
    'We may randomly select four stores.',
    'We randomly select at most four stores.',
    'The experiment is not complete randomization.',
    'We randomly select four stores with replacement.',
    'We randomly select four stores within each group.',
    '本实验不采用每轮随机抽取四家的办法。',
    '试点并不要求每轮随机抽取四家。',
    '不是每轮随机选四家，而是由店长自愿报名。',
    'We do not randomly select four stores.',
    'We never randomly select four stores.',
    '我想知道下周随机选四家使用时的收益。',
    '现在想评估将来均匀随机选四家的政策收益。',
    '文档中的示例方案是每轮随机选四家，当前试验另有安排。',
    '每轮随机选四家，按门店规模加权确定名单。',
    '本实验没有采用每轮随机抽取四家的规则。',
    '本实验未采用每轮随机抽取四家的规则。',
    '原试点不随机选取四家。',
    '每轮随机选四家为上限。',
    'Exactly four stores were not selected uniformly.',
    'Not exactly four stores were selected uniformly.',
    '其余两人不分配。',
    '原试点没有随机选取四人，其余人不分配。',
    '每轮最多随机选取四人，其余人不分配。',
    '每轮随机选取四人，其余人不分配，但名单按规模加权选择。',
    '每轮随机选取四人，其余人不分配，也不执行随机抽取。',
    '每轮随机选四家，其余门店不按随机规则分配。',
]


def audit_wording(text, quote=None, *, extra_quotes=()):
    case, raw = case_and_draft('fixed_quota_policy')
    case['sources'].append(dict(source_id='quota_rule',text=text,kind='STUDY_PROTOCOL'))
    raw['information_design']['assignment_law']=dict(
        value='待审核的固定人数随机分配声明',basis='INTERPRETATION',
        evidence=[dict(source_id='quota_rule',quote=quote or text)] +
                 [dict(source_id='quota_rule',quote=q) for q in extra_quotes])
    original=deepcopy(raw)
    report=audit_draft(BusinessCase.model_validate(case),DraftProblemSpec.model_validate(raw),provider='offline-wording-acceptance')
    assert raw==original
    return report


class FixedQuotaWordingTests(unittest.TestCase):
    def assertQuota(self,text,accepted,quote=None,**kwargs):
        report=audit_wording(text,quote,**kwargs)
        self.assertEqual('A4_UNGROUNDED_FIXED_QUOTA' not in [i.code for i in report.issues],accepted,text)
        self.assertEqual(report.draft.information_design.assignment_family.value,'COMPLETE_RANDOMIZATION')
        self.assertEqual(report.mathematical_verification,'NOT_PERFORMED')
        self.assertFalse(report.estimation_handoff_allowed)
        self.assertIn('A4_POPULATION_INFORMATION_OPEN',[i.code for i in report.issues])
        self.assertTrue(all(a.status!='CERTIFIED' for a in report.draft.assumptions))

    def test_natural_synonyms(self):
        for text in POSITIVE:
            with self.subTest(text=text):self.assertQuota(text,True)

    def test_not_a_fixed_size_assignment_declaration(self):
        for text in NEGATIVE:
            with self.subTest(text=text):self.assertQuota(text,False)

    def test_cropped_negation_cannot_be_laundered(self):
        self.assertQuota('原试验不是固定名额随机分配。',False,'固定名额随机分配')

    def test_cropped_realized_count_cannot_be_laundered(self):
        self.assertQuota('每人独立抛硬币，本次观察到随机抽中了恰好四家。',False,'随机抽中了恰好四家')

    def test_cropped_hypothetical_cannot_be_laundered(self):
        self.assertQuota('如果下次每轮随机选四家，效果怎样？',False,'每轮随机选四家')

    def test_cropped_named_design_keeps_negation(self):
        self.assertQuota('本实验不是完全随机化。',False,'完全随机化')

    def test_repeated_quote_with_conflicting_context_stays_open(self):
        self.assertQuota('旧例每轮随机选四家。当前未决定是否每轮随机选四家。',False,'每轮随机选四家')

    def test_only_cited_design_context_is_used(self):
        text='原试点是逐人独立抽签。未来如果每轮随机选四家，效果怎样？'
        self.assertQuota(text,False,'每轮随机选四家')

    def test_unrelated_true_sentence_cannot_rescue_bad_evidence(self):
        self.assertQuota('另一个实验采用完全随机化。当前方案尚未决定。',False,'当前方案尚未决定')

    def test_citation_ending_at_period_does_not_absorb_next_goal(self):
        text='原试点每轮随机选四家。未来如果改为全体使用会怎样？'
        self.assertQuota(text,True,'原试点每轮随机选四家。')

    def test_claim_value_cannot_replace_missing_evidence(self):
        self.assertQuota('每人中签概率相同，联合分配机制未说明。',False)

    def test_separate_quotes_cannot_build_a_new_design_sentence(self):
        self.assertQuota('每轮随机选择。记录含四家门店的销售额。',False,'每轮随机选择',extra_quotes=('四家门店',))

    def test_multi_sentence_quote_cannot_build_a_new_design(self):
        self.assertQuota('每轮随机选择。记录含四家门店的销售额。',False)

    def test_cropped_selection_keeps_negated_verb(self):
        self.assertQuota('本实验不采用每轮随机抽取四家的办法。',False,'随机抽取四家')

    def test_source_provenance_still_checked(self):
        with self.assertRaises(DraftEvidenceError):
            audit_wording('原试点每轮随机选四家。','每轮随机选八家')


if __name__=='__main__':unittest.main()

