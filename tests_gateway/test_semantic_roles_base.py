from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.semantic_roles_base import build_role_result,make_role_request,SemanticRoleFormulator,render_role_html
from cfm_id_llm.semantic_roles_cli import main


class SemanticRoleTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='ROLE-TEST',business_question='公司有80位员工。没有助手的人会不会因朋友使用助手而受益？我们希望下个月看满意度。希望全公司满意度最高。以后每人等权取平均。已经记录了上周的满意度。已提供的表头为metric_before和metric_after。')
        self.catalog=build_catalog(self.case)
        self.raw={'facts':{'units':self.fragment('公司有80位员工'),'action':self.fragment('使用助手'),'outcome':self.fragment('满意度'),
            'data_timing':{'role':'planned','evidence':self.fragment('我们希望下个月看满意度')},
            'data_inventory':[self.fragment('已提供的表头为metric_before和metric_after')]},
            'goals':[{'form':'comparison','focus':'peers','question':self.fragment('没有助手的人会不会因朋友使用助手而受益'),
                'population':{'role':'ambiguous','evidence':self.fragment('没有助手的人')},
                'situation_a':{'own_action':self.fragment('没有助手的人'),'peers':self.fragment('朋友使用助手')},
                'situation_b':None,'objective':self.fragment('希望全公司满意度最高'),
                'aggregation':{'operation':'unspecified'},'evaluation_time':self.fragment('下个月'),
                'clarifications':[{'about':'population','evidence':self.fragment('没有助手的人'),
                    'question':'这里指这次没用助手的那些人，还是对员工设想本人不使用的情形？'}]}]}

    def fragment(self,text):
        return {'ref':next(s['ref'] for s in self.catalog if text in s['quote']),'quote':text}
    def result(self):return build_role_result(self.case,self.raw,'mock')

    def test_population_ambiguity_preserves_known_own_state_and_peer_state(self):
        r=self.result();s=r['quality']['draft']['queries'][0]['semantics']
        self.assertIsNone(s['target_population']['value']);self.assertIn('没有助手的人',s['intervention']['value'])
        self.assertIn('朋友使用助手',s['neighbor_exposure']['value']);self.assertIsNone(s['comparator']['value'])
        self.assertTrue(r['retained_context']);self.assertEqual(len(r['proposed_clarifications']),1)

    def test_company_background_is_not_projected_as_target_population(self):
        self.raw['goals'][0]['population']={'role':'background','evidence':self.fragment('公司有80位员工')}
        r=self.result();self.assertIsNone(r['business_draft']['goals'][0]['who'])
        self.assertEqual(r['business_draft']['facts']['units']['text'],'公司有80位员工')

    def test_planned_or_header_time_is_not_already_recorded_data(self):
        for role,text in [('planned','我们希望下个月看满意度'),('metadata_only','metric_before和metric_after'),('unclear','满意度')]:
            with self.subTest(role=role):
                self.raw['facts']['data_timing']={'role':role,'evidence':self.fragment(text)}
                r=self.result();self.assertIsNone(r['business_draft']['facts']['recorded_timing'])
                self.assertEqual(r['business_draft']['goals'][0]['when']['text'],'下个月')
                self.assertIn('metric_before',r['business_draft']['facts']['available_data']['text'])

    def test_explicit_collected_time_is_retained_independently_of_evaluation_time(self):
        self.raw['facts']['data_timing']={'role':'recorded','evidence':self.fragment('已经记录了上周的满意度')}
        r=self.result();self.assertIn('上周',r['business_draft']['facts']['recorded_timing']['text'])
        self.assertEqual(r['business_draft']['goals'][0]['when']['text'],'下个月')

    def test_objective_does_not_become_aggregation_or_disappear_from_card(self):
        r=self.result();self.assertIsNone(r['business_draft']['goals'][0]['summarize'])
        self.assertIn('希望全公司满意度最高',render_role_html(self.case,r))

    def test_known_operation_and_unknown_weights_are_separate(self):
        self.raw['goals'][0]['aggregation']={'operation':'mean','operation_evidence':self.fragment('取平均')}
        r=self.result();self.assertEqual(r['business_draft']['goals'][0]['summarize']['text'],'取平均')
        self.assertTrue(any(x['code']=='AGGREGATION_WEIGHTS_UNRESOLVED' for x in r['internal_recheck']))
        self.raw['goals'][0]['aggregation']['weights']=self.fragment('每人等权')
        r=self.result();self.assertFalse(any(x['code']=='AGGREGATION_WEIGHTS_UNRESOLVED' for x in r['internal_recheck']))

    def test_invented_quotes_or_foreign_refs_rejected_even_in_retained_context(self):
        for bad,code in [({'ref':self.catalog[0]['ref'],'quote':'已经获得POINT认证'},'ROLE_QUOTE_NOT_FOUND'),
            ({'ref':'foreign','quote':'公司有80位员工'},'A0_REFERENCE_NOT_FOUND')]:
            with self.subTest(code=code):
                self.raw['goals'][0]['population']={'role':'background','evidence':bad}
                with self.assertRaises(A0QualityValidationError) as e:self.result()
                self.assertEqual(e.exception.code,code)

    def test_model_role_labels_do_not_grant_entailment_or_scientific_approval(self):
        # Deliberately wrong role with a real quote: reference checking cannot detect this.
        self.raw['goals'][0]['population']={'role':'target_scope','evidence':self.fragment('公司有80位员工')}
        r=self.result()
        for k in ('role_entailment_verified','semantic_correctness_verified','business_approval','scientific_approval','core_called','identification_ready','estimation_handoff_allowed'):
            self.assertFalse(r[k])
        self.raw['scientific_approval']=True
        with self.assertRaises(A0QualityValidationError):self.result()

    def test_one_call_no_review_or_retry_even_on_invalid_source(self):
        class Counting:
            name='mock'
            def __init__(self,payload):self.payload=payload;self.calls=0
            def generate_json(self,**kwargs):self.calls+=1;return self.payload
        p=Counting(self.raw);SemanticRoleFormulator(p).formulate(self.case);self.assertEqual(p.calls,1)
        self.raw['facts']['action']['quote']='未给过的处理'
        p=Counting(self.raw)
        with self.assertRaises(A0QualityValidationError):SemanticRoleFormulator(p).formulate(self.case)
        self.assertEqual(p.calls,1)

    def test_schema_and_html_handle_untrusted_clarification_text(self):
        system,user,catalog=make_role_request(self.case)
        self.assertIn(self.case.business_question,user);self.assertEqual(catalog,self.catalog)
        self.raw['goals'][0]['clarifications'][0]['question']='<script>bad()</script>'
        html=render_role_html(self.case,self.result());self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)

    def test_ordinary_language_cli_and_plain_reply_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture=root/'mock.json';fixture.write_text(json.dumps(self.raw),encoding='utf8')
            first=root/'first';second=root/'second'
            self.assertEqual(main(['--question',self.case.business_question,'--case-id',self.case.case_id,
                '--mock-response',str(fixture),'--output-dir',str(first)]),0)
            self.assertTrue((first/'business_confirmation.html').exists())
            self.assertEqual(main(['--resume',str(first),'--reply','指所有员工设想本人不用，不只这次没用的人。',
                '--preview','--output-dir',str(second)]),0)
            self.assertIn('指所有员工', (second/'public_input.json').read_text(encoding='utf8'))

if __name__=='__main__':unittest.main()
