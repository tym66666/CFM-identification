"""Offline contract, refusal and applicability checks; no HTTP or credentials."""
from copy import deepcopy
import json,subprocess,sys,unittest
from cfm_id_llm.compact_formulator import (
    CompactFormulator, CompactDraft, make_compact_request, assemble_compact)
from cfm_id_llm.evidence_refs import build_catalog, make_ref_request
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.quality_formulator import A0QualityValidationError


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='COMPACT-TEST',business_question='公司有48个站点。目标是本人使用系统且一个邻居使用时，八周后全部站点等权平均延误。')
        self.ref=build_catalog(self.case)[1]['ref']
        c=lambda value:{'state':'STATED','value':value,'refs':[self.ref]}
        self.claim=c
        self.raw={'common':{'analysis_unit':c('站点'),'treatment':c('使用系统'),'outcome':c('延误'),
            'unit_network':c('站点邻接网络')},'queries':[{'goal':c('本人使用且一个邻居使用时的平均延误'),
            'kind':'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN','semantics':{
            'target_population':c('全部48个站点'),'intervention':c('本人使用系统'),
            'comparator':{'state':'NOT_APPLICABLE'},'neighbor_exposure':c('恰有一个邻居使用'),
            'aggregation':c('全部站点等权平均'),'time_horizon':c('八周后'),
            'policy_assignment':{'state':'NOT_APPLICABLE'}}}]}

    def run_draft(self, raw=None):
        p=MockProvider(self.raw if raw is None else raw);f=CompactFormulator(p)
        report=f.formulate(self.case)
        self.assertEqual(p.calls,1)
        return report,f

    def test_single_goal_assembled_identically_and_wire_unchanged(self):
        before=deepcopy(self.raw);report,f=self.run_draft()
        self.assertEqual(before,self.raw)
        self.assertEqual(report.draft.shared_draft.target,report.draft.queries[0].target)
        self.assertEqual(report.draft.primary_query_id,'q1')
        self.assertFalse(report.core_called)
        self.assertFalse(f.last_gate['identification_ready'])
        self.assertEqual(f.last_gate['status'],'DRAFT_FOR_EXTERNAL_REVIEW')

    def test_not_applicable_retained_in_sidecar_not_as_fact(self):
        report,f=self.run_draft()
        self.assertEqual(f.last_gate['slot_states']['q1']['comparator'],'NOT_APPLICABLE')
        self.assertIsNone(report.draft.queries[0].semantics.comparator.value)
        self.assertFalse(any(x['field']=='comparator' for x in f.last_gate['proposed_business_questions']))

    def test_unexpected_comparator_is_visible_and_blocked(self):
        self.raw['queries'][0]['semantics']['comparator']=self.claim('本人不使用系统')
        report,f=self.run_draft()
        self.assertEqual(report.draft.queries[0].semantics.comparator.value,'本人不使用系统')
        self.assertIn('UNEXPECTED_COMPARATOR',[x['code'] for x in f.last_gate['issues']])
        self.assertEqual(f.last_gate['status'],'FORMULATION_RECHECK_REQUIRED')

    def test_direct_effect_cannot_ignore_neighbors(self):
        q=self.raw['queries'][0];q['kind']='DIRECT_EFFECT'
        q['semantics']['comparator']=self.claim('本人未使用')
        q['semantics']['neighbor_exposure']=self.claim('不考虑邻居暴露')
        _,f=self.run_draft()
        self.assertIn('DIRECT_EFFECT_IGNORES_PEERS',[x['code'] for x in f.last_gate['issues']])

    def test_effect_comparator_not_applicable_is_rechecked(self):
        self.raw['queries'][0]['kind']='SPILLOVER_EFFECT'
        _,f=self.run_draft()
        self.assertIn('INVALID_NOT_APPLICABLE',[x['code'] for x in f.last_gate['issues']])

    def test_missing_coordinates_yield_questions_without_guessing(self):
        q=self.raw['queries'][0];q['kind']='DIRECT_EFFECT';q['semantics']={}
        report,f=self.run_draft()
        fields={x['field'] for x in f.last_gate['proposed_business_questions']}
        self.assertTrue({'comparator','neighbor_exposure','time_horizon','aggregation'}.issubset(fields))
        self.assertEqual(f.last_gate['status'],'BUSINESS_CLARIFICATION_REQUIRED')
        self.assertIsNone(report.draft.queries[0].semantics.comparator.value)
        self.assertTrue(all(x['status']=='VERIFY_MISSING_IN_SOURCE_BEFORE_ASKING' for x in f.last_gate['proposed_business_questions']))

    def test_interpretation_does_not_become_approval(self):
        self.raw['queries'][0]['semantics']['aggregation']['state']='INTERPRETED'
        report,f=self.run_draft()
        self.assertEqual(report.draft.queries[0].semantics.aggregation.basis,'INTERPRETATION')
        self.assertIn('INTERPRETATION_REQUIRES_REVIEW',[x['code'] for x in f.last_gate['issues']])
        self.assertFalse(f.last_gate['business_approval'])

    def test_optimization_requires_policy_not_solution(self):
        q=self.raw['queries'][0];q['kind']='POLICY_OPTIMIZATION'
        q['semantics']['policy_assignment']={'state':'UNKNOWN'}
        _,f=self.run_draft()
        self.assertIn('policy_assignment',[x['field'] for x in f.last_gate['proposed_business_questions']])

    def test_unknown_claim_cannot_hide_a_value(self):
        self.raw['queries'][0]['semantics']['comparator']={'state':'UNKNOWN','value':'none'}
        with self.assertRaises(A0QualityValidationError) as c:self.run_draft()
        self.assertEqual(c.exception.code,'COMPACT_SCHEMA_REJECTED')

    def test_null_is_not_a_claim_or_enum(self):
        for field in ['outcome','assignment_family']:
            raw=deepcopy(self.raw);raw['common'][field]=None
            with self.subTest(field=field),self.assertRaises(A0QualityValidationError):self.run_draft(raw)

    def test_extra_proof_ids_or_science_cannot_enter_wire(self):
        for key in ['shared_draft','mathematical_certificate','assumptions','query_id']:
            raw=deepcopy(self.raw);raw[key]='SECRET_MARKER'
            with self.subTest(key=key),self.assertRaises(A0QualityValidationError) as c:self.run_draft(raw)
            self.assertNotIn('SECRET_MARKER',str(c.exception))
            self.assertNotIn(key,str(c.exception.diagnostics))

    def test_unknown_and_cross_case_references_rejected(self):
        other=self.case.model_copy(update={'case_id':'OTHER'})
        for ref in ['unknown',build_catalog(other)[1]['ref']]:
            raw=deepcopy(self.raw);raw['queries'][0]['goal']['refs']=[ref]
            with self.subTest(ref=ref),self.assertRaises(A0QualityValidationError) as c:self.run_draft(raw)
            self.assertEqual(c.exception.code,'A0_REFERENCE_NOT_FOUND')

    def test_known_claim_needs_evidence(self):
        self.raw['queries'][0]['goal']['refs']=[]
        with self.assertRaises(A0QualityValidationError):self.run_draft()

    def test_known_assignment_requires_own_support(self):
        self.raw['common']['assignment_family']='COMPLETE_RANDOMIZATION'
        with self.assertRaises(A0QualityValidationError) as c:self.run_draft()
        self.assertEqual(c.exception.code,'A0_SCHEMA_REJECTED')

    def test_ordered_multiple_goals_not_deduplicated_or_rewritten(self):
        q=deepcopy(self.raw['queries'][0]);q['kind']='SPILLOVER_EFFECT';q['goal']=self.claim('对未使用者的同伴影响')
        q['semantics']['comparator']={'state':'UNKNOWN'};self.raw['queries'].append(q)
        report,_=self.run_draft()
        self.assertEqual([q.query_id for q in report.draft.queries],['q1','q2'])
        self.assertEqual(report.draft.queries[1].target.description.value,'对未使用者的同伴影响')

    def test_false_claim_with_real_quote_remains_unverified(self):
        self.raw['queries'][0]['semantics']['time_horizon']=self.claim('五十年后')
        report,f=self.run_draft()
        self.assertEqual(report.draft.queries[0].semantics.time_horizon.value,'五十年后')
        self.assertFalse(f.last_gate['semantic_correctness_verified'])
        self.assertFalse(report.estimation_handoff_allowed)

    def test_unknown_goal_rejected(self):
        self.raw['queries'][0]['goal']={'state':'UNKNOWN'}
        with self.assertRaises(A0QualityValidationError):self.run_draft()

    def test_request_preserves_all_sources_without_labels(self):
        _,user,catalog=make_compact_request(self.case)
        payload=json.loads(user.split('\n',1)[1].split('\n\n输出 Schema',1)[0])
        self.assertEqual(payload['business_question'],self.case.business_question)
        self.assertEqual(payload['source_catalog'],catalog)
        self.assertEqual(set(payload),{'case_id','business_question','sources','response_language','source_catalog'})
        self.assertLess(len(user),len(make_ref_request(self.case)[1]))

    def test_no_extra_model_call_on_failure(self):
        p=MockProvider({'queries':[]});f=CompactFormulator(p)
        with self.assertRaises(A0QualityValidationError):f.formulate(self.case)
        self.assertEqual(p.calls,1)

    def test_import_does_not_load_mathematical_core(self):
        p=subprocess.run([sys.executable,'-B','-c','import sys,cfm_id_llm.compact_formulator; print("cfm_id_bridge" in sys.modules,"pfn_pipeline" in sys.modules)'],capture_output=True,text=True,check=True)
        self.assertEqual(p.stdout.strip(),'False False')

    def test_no_common_fact_can_claim_not_applicable(self):
        self.raw['common']['exposure_mapping']={'state':'NOT_APPLICABLE'}
        _,f=self.run_draft()
        self.assertIn('INAPPLICABLE_COMMON_FACT',[x['code'] for x in f.last_gate['issues']])

    def test_declared_string_sentinels_keep_unknown_and_applicability(self):
        self.raw['queries'][0]['semantics']['comparator']='NOT_APPLICABLE'
        self.raw['queries'][0]['semantics']['time_horizon']='UNKNOWN'
        before=deepcopy(self.raw)
        report,f=self.run_draft()
        self.assertEqual(before,self.raw)
        self.assertIsNone(report.draft.queries[0].semantics.time_horizon.value)
        self.assertEqual(f.last_gate['slot_states']['q1']['comparator'],'NOT_APPLICABLE')
        _,user,_=make_compact_request(self.case)
        schema=json.loads(user.split('\n\n输出 Schema：\n')[1])
        self.assertIn({'enum':['UNKNOWN','NOT_APPLICABLE'],'type':'string'},schema['$defs']['CompactSemantics']['properties']['comparator']['anyOf'])

    def test_other_string_or_null_slots_not_repaired(self):
        for value in ['STATED','UNRESOLVED','没有对照',None]:
            raw=deepcopy(self.raw);raw['queries'][0]['semantics']['comparator']=value
            with self.subTest(value=value),self.assertRaises(A0QualityValidationError):self.run_draft(raw)

    def test_existing_spillover_contrast_is_rechecked_before_business_question(self):
        q=self.raw['queries'][0];q['kind']='SPILLOVER_EFFECT'
        q['semantics']['intervention']=self.claim('伙伴过半启用')
        q['semantics']['comparator']=self.claim('伙伴未过半启用')
        q['semantics']['neighbor_exposure']='UNKNOWN'
        self.raw['common']['exposure_mapping']=self.claim('伙伴过半的分组定义')
        before=deepcopy(self.raw);report,f=self.run_draft()
        self.assertIn('RECHECK_EXPOSURE_IN_EXISTING_CONTRAST',[x['code'] for x in f.last_gate['issues']])
        self.assertFalse(any(x['field']=='neighbor_exposure' for x in f.last_gate['proposed_business_questions']))
        self.assertEqual(before,self.raw)
        self.assertIsNone(report.draft.queries[0].semantics.neighbor_exposure.value)
        self.assertFalse(f.last_gate['identification_ready'])

if __name__=='__main__':unittest.main()
