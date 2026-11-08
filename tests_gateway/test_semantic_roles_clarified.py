from copy import deepcopy
import json,unittest
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.semantic_roles_clarified import make_role_request,build_role_result
from cfm_id_llm.quality_formulator import A0QualityValidationError

class ScopeOverlapTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='OVERLAP',business_question='没有软件的人会因朋友使用软件而受益吗？我们想评价全体员工。')
        self.cat=build_catalog(self.case)
        def f(q):return {'ref':next(s['ref'] for s in self.cat if q in s['quote']),'quote':q}
        self.f=f
        self.raw={'goals':[{'form':'comparison','focus':'peers','question':f('没有软件的人会因朋友使用软件而受益吗'),
            'population':{'role':'target_scope','evidence':f('没有软件的人')},'situation_a':{'own_action':f('没有软件'),'peers':f('朋友使用软件')}}]}
    def test_overlap_holds_population_not_own_state_and_preserves_raw_proposal(self):
        original=deepcopy(self.raw);r=build_role_result(self.case,self.raw,'mock')
        self.assertEqual(self.raw,original);self.assertIsNone(r['business_draft']['goals'][0]['who'])
        self.assertEqual(r['business_draft']['goals'][0]['situation_a']['own_action']['text'],'没有软件')
        self.assertEqual(r['model_role_draft']['goals'][0]['population']['role'],'target_scope')
        self.assertEqual(len(r['role_scope_holds']),1);self.assertFalse(r['role_entailment_verified'])
    def test_separate_explicit_population_is_not_held(self):
        self.raw['goals'][0]['population']['evidence']=self.f('我们想评价全体员工')
        r=build_role_result(self.case,self.raw,'mock');self.assertFalse(r['role_scope_holds'])
        self.assertEqual(r['business_draft']['goals'][0]['who']['text'],'我们想评价全体员工')
    def test_bad_quote_cannot_hide_behind_overlap_hold(self):
        self.raw['goals'][0]['population']['evidence']['quote']='不存在的没有软件的人'
        with self.assertRaises(A0QualityValidationError):build_role_result(self.case,self.raw,'mock')
    def test_descriptions_distinguish_design_set_measure_and_target_distribution(self):
        _,user,_=make_role_request(self.case);schema=json.loads(user.split('\n输出Schema：\n')[1])
        facts=schema['$defs']['SharedFacts']['properties']
        self.assertIn('全体中统一固定名额',facts['assignment_family']['description'])
        self.assertIn('不是谁算伙伴',facts['peer_measure']['description'])
        self.assertIn('按原抽签方式',schema['$defs']['Level']['properties']['remaining_assignments']['description'])

if __name__=='__main__':unittest.main()
