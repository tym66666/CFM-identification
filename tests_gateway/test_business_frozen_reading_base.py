import unittest,json
from copy import deepcopy
from unittest.mock import patch
from examples.nbib_core_peers_fixture import load_case
from evaluation import business_frozen_reading_base as f
from evaluation.business_core_peers_staged_base import bind_study

class ScopeContractTests(unittest.TestCase):
    def test_local_unknown_is_not_inapplicable(self):
        i=load_case();r=deepcopy(i['raw']);r['questions']['q1']['peer_scope']='不适用'
        with patch.object(f.entries,'identify',side_effect=AssertionError('must not dispatch')):
            result=f.identify(i['bundle'],r,'STAGED_CORE_PEERS')
        self.assertFalse(result['core_called']);self.assertEqual(result['reading_candidate'],r)
        self.assertEqual(result['state'],'READING_REVIEW_REQUIRED')
    def test_optimization_and_known_scope_unchanged(self):
        i=load_case();self.assertEqual(f.cross_field_issues(i['raw']),[])
    def test_unknown_kept_not_completed(self):
        i=load_case();r=deepcopy(i['raw']);r['questions']['q1']['peer_scope']='不明确';before=deepcopy(r)
        self.assertEqual(f.cross_field_issues(r),[]);self.assertEqual(r,before)
    def test_schema_constraint_same_for_all_local_queries(self):
        i=load_case();e=bind_study(i['bundle'],{'study':i['raw']['study']})
        s,u=f.make_request(i['bundle'],'STAGED_CORE_PEERS',e)
        rule=json.loads(u)['output_schema']['$defs']['Question']['allOf'][-1]
        self.assertEqual(rule['then']['properties']['operation'],{'const':'选最优'})

if __name__=='__main__':unittest.main()
