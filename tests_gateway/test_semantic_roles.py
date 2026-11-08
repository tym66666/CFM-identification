import unittest
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.semantic_roles import build_role_result,ScopedRoleFormulator

class LevelScopeTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='LEVEL-SCOPE',business_question='一家医院采用新流程且两家邻院恰有一家采用时，第三个月等候时间如何？希望评价全部医院，每家等权取平均。')
        self.cat=build_catalog(self.case)
        def f(q):return {'ref':next(s['ref'] for s in self.cat if q in s['quote']),'quote':q}
        self.f=f;self.raw={'goals':[{'form':'level','quantity':'mean','question':f('一家医院采用新流程且两家邻院恰有一家采用时，第三个月等候时间如何'),
            'population':{'role':'target_scope','evidence':f('一家医院采用新流程且两家邻院恰有一家采用时')},
            'evaluation_time':f('第三个月'),'situation':{'own_action':f('一家医院采用新流程'),'peers':f('两家邻院恰有一家采用')},
            'aggregation':{'operation':'mean','operation_evidence':f('取平均'),'weights':f('每家等权')}}]}
    def test_level_scenario_does_not_silently_fill_population(self):
        r=build_role_result(self.case,self.raw,'mock');g=r['business_draft']['goals'][0]
        self.assertIsNone(g['who']);self.assertEqual(g['situation']['own_action']['text'],'一家医院采用新流程')
        self.assertIn('每家等权',g['summarize']['text']);self.assertEqual(g['when']['text'],'第三个月')
        self.assertEqual(r['confirmation_card']['status'],'SOURCE_RECHECK_REQUIRED')
        self.assertFalse(r['proposed_clarifications']) # Recheck existing source; do not pretend user omitted scope.
    def test_separate_scope_stays_usable_and_original_overlap_proposal_is_retained(self):
        r=build_role_result(self.case,self.raw,'mock')
        self.assertEqual(r['model_role_draft']['goals'][0]['population']['role'],'target_scope')
        self.raw['goals'][0]['population']['evidence']=self.f('希望评价全部医院')
        r=build_role_result(self.case,self.raw,'mock');self.assertFalse(r['role_scope_holds'])
        self.assertEqual(r['business_draft']['goals'][0]['who']['text'],'希望评价全部医院')
    def test_local_gate_adds_no_model_call_or_approval(self):
        class Counting:
            name='mock'
            def __init__(self,raw):self.raw=raw;self.calls=0
            def generate_json(self,**kwargs):self.calls+=1;return self.raw
        p=Counting(self.raw);r=ScopedRoleFormulator(p).formulate(self.case)
        self.assertEqual(p.calls,1);self.assertFalse(r['identification_ready']);self.assertFalse(r['role_entailment_verified'])
    def test_mixed_level_and_comparison_preserves_both_holds(self):
        comparison={'form':'comparison','focus':'own','question':self.f('一家医院采用新流程'),
            'population':{'role':'target_scope','evidence':self.f('一家医院采用新流程')},
            'situation_a':{'own_action':self.f('采用新流程')}}
        self.raw['goals'].append(comparison)
        r=build_role_result(self.case,self.raw,'mock')
        self.assertEqual(len(r['role_scope_holds']),2)
        self.assertTrue(all(g['who'] is None for g in r['business_draft']['goals']))
        self.assertEqual(r['model_role_draft']['goals'][1]['population']['role'],'target_scope')

if __name__=='__main__':unittest.main()
