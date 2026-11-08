from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.literal_grounding import grounding_slots,TwoResponseMock
from cfm_id_llm.compact_grounding import make_compact_grounding_request,build_compact_grounding_result,CompactQuoteReviewedIntake
from cfm_id_llm.compact_review_cli import main


class CompactGroundingTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='COMPACT-GROUND',business_question='员工获得AI助手是否改善自己的满意度？对照、汇总和时间尚未确定。')
        self.ref=build_catalog(self.case)[0]['ref']
        c=lambda text:dict(text=text,refs=[self.ref],reading='explicit')
        self.initial={'facts':{'action':c('AI助手'),'outcome':c('满意度')},'goals':[dict(form='comparison',focus='own',question=c('助手对本人的影响'),situation_a=dict(own_action=c('获得AI助手')))]}
        _,self.slots,_=grounding_slots(self.case,self.initial)
        self.review={'answers':{x['slot_id']:None for x in self.slots}}

    def slot(self,path):return next(x['slot_id'] for x in self.slots if x['path']==path)
    def result(self):return build_compact_grounding_result(self.case,self.initial,self.review,'mock')

    def test_compact_quote_null_ambiguity_keep_same_trust_boundary(self):
        self.review['answers'][self.slot(['facts','outcome'])]={'ref':self.ref,'quote':'满意度'}
        self.review['answers'][self.slot(['goals',0,'who'])]='AMBIGUOUS'
        r=self.result();self.assertTrue(r['review_coverage_complete']);self.assertEqual(r['quality']['draft']['shared_draft']['units_variables']['outcome']['value'],'满意度')
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])
        self.assertFalse(r['semantic_correctness_verified']);self.assertFalse(r['identification_ready'])

    def test_bad_quote_and_missing_slot_cannot_pass_compact_wrapper(self):
        self.review['answers'][self.slot(['facts','outcome'])]={'ref':self.ref,'quote':'收入提高'}
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'GROUNDING_QUOTE_NOT_FOUND')
        self.review['answers'].pop(self.slot(['facts','outcome']))
        with self.assertRaises(A0QualityValidationError) as e:self.result()
        self.assertEqual(e.exception.code,'GROUNDING_COVERAGE_REJECTED')

    def test_free_explanations_and_other_empty_strings_are_rejected(self):
        for value in ('UNKNOWN',{'ref':self.ref,'quote':'满意度','reason':'自由补充'}):
            self.review['answers'][self.slot(['facts','outcome'])]=value
            with self.subTest(value=value),self.assertRaises(A0QualityValidationError) as e:self.result()
            self.assertEqual(e.exception.code,'COMPACT_GROUNDING_SCHEMA_REJECTED')

    def test_schema_requires_every_bound_key(self):
        _,user,_=make_compact_grounding_request(self.case,self.initial)
        schema=json.loads(user.split('\n输出Schema：\n')[1]);answer=schema['properties']['answers']
        self.assertEqual(set(answer['required']),set(self.review['answers']));self.assertFalse(answer['additionalProperties'])

    def test_two_model_calls_and_plain_language_cli(self):
        fixture={'extraction':self.initial,'review':self.review};p=TwoResponseMock(fixture)
        r=CompactQuoteReviewedIntake(p).formulate(self.case);self.assertEqual(p.calls,2);self.assertFalse(r['core_called'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f=root/'responses.json';f.write_text(json.dumps(fixture),encoding='utf8')
            self.assertEqual(main(['--question',self.case.business_question,'--case-id',self.case.case_id,'--mock-response',str(f),'--output-dir',str(root/'out')]),0)
            self.assertTrue((root/'out'/'business_confirmation.html').exists())


if __name__=='__main__':unittest.main()
