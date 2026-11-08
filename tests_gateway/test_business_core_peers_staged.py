import unittest
from copy import deepcopy
from examples.nbib_core_peers_fixture import load_case
from evaluation import business_core_peers_staged_base as old, business_core_peers_staged as new


class TargetEvidenceTests(unittest.TestCase):
    def test_materials_schema_and_parent_unchanged(self):
        i=load_case();e=new.bind_study(i['bundle'],{'study':i['raw']['study']})
        self.assertEqual(old.target_request(i['bundle'],e)[1],new.target_request(i['bundle'],e)[1])

    def test_bad_historical_quote_remains_invalid_not_repaired(self):
        i=deepcopy(load_case());e=new.bind_study(i['bundle'],{'study':i['raw']['study']});q={'questions':i['raw']['questions']}
        q['questions']['q1']['remaining']=dict(rule='原抽签条件平均',source='target_clarification.txt:L1',quote='独立抽签')
        class Mock:
            def generate_json(self,**kwargs):return q
        r=new.normalize_targets(i['bundle'],e,Mock());self.assertEqual(r['state'],'DRAFT_INVALID');self.assertFalse(r['core_called']);self.assertEqual(r['target_candidate'],q)


if __name__=='__main__':unittest.main()
