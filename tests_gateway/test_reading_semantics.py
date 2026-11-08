import unittest
from copy import deepcopy
from evaluation.reading_semantics import semantic_payload


class ReadingSemanticsTests(unittest.TestCase):
    def test_full_roster_alias_is_equal_without_rewriting_answer(self):
        full={'population':{'selection':'全体','ids':[]},'aggregation':'等权平均'}
        listed={'population':{'selection':'指定','ids':['b','a']},'aggregation':'等权平均'}
        original=deepcopy(listed)
        self.assertEqual(semantic_payload(full,['a','b']),semantic_payload(listed,['a','b']))
        self.assertEqual(listed,original)

    def test_subset_duplicate_or_other_roster_never_collapses(self):
        full={'population':{'selection':'全体','ids':[]}}
        for ids in (['a'],['a','a'],['a','c']):
            self.assertNotEqual(semantic_payload(full,['a','b']),semantic_payload({'population':{'selection':'指定','ids':ids}},['a','b']))

    def test_changed_aggregation_and_declared_fact_remain_different(self):
        a={'population':{'selection':'全体','ids':[]},'aggregation':'等权平均','study':{'declared_independent':True}}
        for key,value in [('aggregation','单个'),('study',{'declared_independent':None})]:
            b=deepcopy(a);b[key]=value
            self.assertNotEqual(semantic_payload(a,['a','b']),semantic_payload(b,['a','b']))


if __name__=='__main__':unittest.main()
