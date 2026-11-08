"""Offline evidence selection/binding regressions. No live credentials or HTTP."""
from copy import deepcopy
import json,unittest
from cfm_id_llm.evidence_refs import build_catalog,make_ref_request,bind_ref_draft,EvidenceRefFormulator
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.schemas import BusinessCase,SourceDocument

class EvidenceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='TEST',business_question='一家企业有三名员工。关心全员使用助手的整体业绩。',
            sources=[SourceDocument(source_id='doc',text='指标为 `metric_after`，单位为分。\n时间未指定。')])
        self.catalog=build_catalog(self.case)
        self.ref=next(s['ref'] for s in self.catalog if '关心' in s['quote'])
        self.claim={'value':'全员使用助手的整体业绩','basis':'EXPLICIT_TEXT','evidence':[{'ref':self.ref}]}
        target={'kind':'FIXED_POLICY_VALUE','description':deepcopy(self.claim)}
        self.raw={'shared_draft':{'target':deepcopy(target)},'primary_query_id':'q1',
           'queries':[{'query_id':'q1','business_goal':deepcopy(self.claim),'target':deepcopy(target)}]}
    def test_catalog_offsets_exact_with_markdown_unicode(self):
        sources=self.case.source_map()
        for span in self.catalog:
            self.assertEqual(span['quote'],sources[span['source_id']][span['start']:span['end']])
        self.assertTrue(any('`metric_after`' in s['quote'] for s in self.catalog))
    def test_long_span_does_not_drop_final_character(self):
        case=BusinessCase(case_id='long',business_question='文'*1001)
        spans=build_catalog(case)
        self.assertEqual(''.join(s['quote'] for s in spans),'文'*1001)
    def test_full_source_still_present_even_if_uncitable_short_fragment(self):
        case=BusinessCase(case_id='short',business_question='业务问题',sources=[SourceDocument(source_id='x',text='A')])
        _,user,_=make_ref_request(case)
        self.assertIn('"text":"A"',user)
    def test_binding_changes_only_evidence_and_does_not_mutate_wire(self):
        original=deepcopy(self.raw)
        bound=bind_ref_draft(self.case,self.raw)
        self.assertEqual(self.raw,original)
        self.assertEqual(bound['queries'][0]['business_goal']['value'],self.claim['value'])
        evidence=bound['queries'][0]['business_goal']['evidence'][0]
        self.assertEqual(evidence['source_id'],'business_question')
        self.assertIn(evidence['quote'],self.case.business_question)
    def test_unknown_reference_is_rejected_without_echo(self):
        self.raw['queries'][0]['business_goal']['evidence']=[{'ref':'PRIVATE_SENTINEL'}]
        with self.assertRaises(A0QualityValidationError) as c:bind_ref_draft(self.case,self.raw)
        self.assertEqual(c.exception.code,'A0_REFERENCE_NOT_FOUND')
        self.assertNotIn('PRIVATE_SENTINEL',str(c.exception))
    def test_other_case_reference_rejected(self):
        changed=self.case.model_copy(update={'business_question':self.case.business_question+'另一个问题。'})
        with self.assertRaises(A0QualityValidationError):bind_ref_draft(changed,self.raw)
    def test_inline_quote_and_extra_keys_and_string_refs_rejected(self):
        for evidence in [[{'source_id':'business_question','quote':'全员'}],
                         [{'ref':self.ref,'quote':'全员'}],[self.ref],None]:
            with self.subTest(evidence=evidence):
                raw=deepcopy(self.raw);raw['queries'][0]['business_goal']['evidence']=evidence
                with self.assertRaises(A0QualityValidationError):bind_ref_draft(self.case,raw)
    def test_unknown_claim_string_remains_rejected(self):
        self.raw['queries'][0]['semantics']={'comparator':{'value':'UNRESOLVED','basis':'UNRESOLVED','evidence':[]}}
        with self.assertRaises(A0QualityValidationError) as c:EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(c.exception.code,'A0_SCHEMA_REJECTED')
    def test_unknown_claim_cannot_hide_evidence(self):
        self.raw['queries'][0]['semantics']={'comparator':{'value':None,'basis':'UNRESOLVED','evidence':[{'ref':self.ref}]}}
        with self.assertRaises(A0QualityValidationError):EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)
    def test_primary_target_mismatch_still_rejected(self):
        self.raw['shared_draft']['target']['kind']='POLICY_OPTIMIZATION'
        with self.assertRaises(A0QualityValidationError) as c:EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(c.exception.diagnostics['issues'][0]['code'],'PRIMARY_TARGET_MISMATCH')
    def test_reference_cannot_bypass_extra_field_rejection(self):
        self.raw['unexpected']={'ref':self.ref}
        with self.assertRaises(A0QualityValidationError):EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)
    def test_one_model_call_no_retries_even_for_bad_reference(self):
        self.raw['queries'][0]['business_goal']['evidence']=[{'ref':'unknown'}]
        provider=MockProvider(self.raw)
        with self.assertRaises(A0QualityValidationError):EvidenceRefFormulator(provider).formulate(self.case)
        self.assertEqual(provider.calls,1)
    def test_real_reference_does_not_certify_false_claim_or_math(self):
        # A real quote is not an entailment checker. Preserve the model's claim
        # visibly for review, without approving it or correcting its meaning.
        bad='所有员工的业绩必然翻倍'
        self.raw['queries'][0]['target']['description']['value']=bad
        self.raw['shared_draft']['target']['description']['value']=bad
        report=EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(report.draft.queries[0].target.description.value,bad)
        self.assertFalse(report.core_called)
        self.assertFalse(report.estimation_handoff_allowed)
        self.assertTrue(report.scientific_review_required)
    def test_request_contains_only_current_case_catalog_and_wire_schema(self):
        before=self.case.model_dump_json()
        _,user,catalog=make_ref_request(self.case)
        schema=json.loads(user.split('输出 Schema（evidence 使用 ref 编号；未知 SemanticClaim 可为 null）：\n')[1])
        self.assertEqual(schema['$defs']['EvidenceQuote']['properties']['ref']['enum'],[s['ref'] for s in catalog])
        self.assertNotIn('gold/references',user)
        self.assertNotIn('candidate_math_route',user)
        self.assertEqual(before,self.case.model_dump_json())
    def test_catalog_limit_rejects_before_model_call(self):
        case=BusinessCase(case_id='large',business_question='甲乙。'*513)
        provider=MockProvider(self.raw)
        with self.assertRaises(A0QualityValidationError) as c:EvidenceRefFormulator(provider).formulate(case)
        self.assertEqual(c.exception.code,'A0_REFERENCE_CATALOG_LIMIT')
        self.assertEqual(provider.calls,0)

    def test_declared_wire_null_maps_only_claims_to_unknown(self):
        self.raw['queries'][0]['semantics']={'comparator':None,'time_horizon':None}
        before=deepcopy(self.raw)
        bound=bind_ref_draft(self.case,self.raw)
        self.assertEqual(bound['queries'][0]['semantics']['comparator'],{'value':None,'basis':'UNRESOLVED','evidence':[]})
        self.assertEqual(self.raw,before)
        self.assertFalse(EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case).estimation_handoff_allowed)

    def test_null_nonclaim_objects_and_lists_still_rejected(self):
        for field in ['target','units_variables','assumptions']:
            raw=deepcopy(self.raw);raw['shared_draft'][field]=None
            with self.subTest(field=field),self.assertRaises(A0QualityValidationError):
                EvidenceRefFormulator(MockProvider(raw)).formulate(self.case)

    def test_null_claim_cannot_support_declared_design(self):
        self.raw['shared_draft']['information_design']={'assignment_family':'COMPLETE_RANDOMIZATION','assignment_law':None}
        with self.assertRaises(A0QualityValidationError):EvidenceRefFormulator(MockProvider(self.raw)).formulate(self.case)

if __name__=='__main__':unittest.main()

