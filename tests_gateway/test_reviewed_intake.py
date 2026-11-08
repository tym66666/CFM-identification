"""Review boundaries and text reply roundtrip; no credentials/network."""
from copy import deepcopy
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json, subprocess, sys, unittest, tempfile
from cfm_id_llm.reviewed_intake import (
    ReviewedIntake, build_review_result, append_business_reply,
    render_confirmation_html, make_review_request, make_patch_request, build_patch_result, PatchedIntake)
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.schemas import BusinessCase
from tests_gateway import test_compact_formulator as fixtures


class ReviewTests(unittest.TestCase):
    def setUp(self):
        f = fixtures.CompactTests(); f.setUp()
        self.case, self.raw = f.case, f.raw

    def run_review(self, raw=None, items=None, initial=None):
        return build_review_result(self.case, initial or self.raw,
            {'draft': raw or self.raw, 'open_items': items or []})

    def test_review_preserves_both_versions_and_no_scientific_permission(self):
        before = deepcopy(self.raw); revised = deepcopy(self.raw)
        revised['queries'][0]['semantics']['time_horizon']['value'] = '实施后八周'
        result = self.run_review(revised)
        self.assertEqual(self.raw, before)
        self.assertTrue(result['changes'])
        card = result['confirmation_card']
        self.assertEqual(card['status'], 'DRAFT_FOR_BUSINESS_REVIEW')
        for flag in ['business_approval','scientific_approval','core_called','identification_ready','estimation_handoff_allowed','semantic_correctness_verified']:
            self.assertIs(card[flag], False)
        self.assertFalse(result['quality']['formal_core_spec_generated'])

    def test_confirmation_renders_every_current_field_without_approving_new_claims(self):
        from cfm_id_llm.compact_formulator import CompactCommon, CompactSemantics
        for stated in (False, True):
            with self.subTest(stated=stated):
                raw = deepcopy(self.raw)
                if stated:
                    ref = raw['common']['analysis_unit']['refs']
                    # Deliberately unverified source-referenced claims: rendering
                    # must preserve/escape them without granting any permission.
                    raw['common']['variable_causal_graph'] = dict(state='STATED',
                        value='待核对的变量关系 <script>untrusted</script>', refs=ref)
                    raw['common']['available_information'] = dict(state='STATED',
                        value='待核对的总体分布声明', refs=ref)
                result = self.run_review(raw)
                card = result['confirmation_card']
                items = {r['field']: r for r in card['common']}
                self.assertEqual(set(items), set(CompactCommon.model_fields)-{'assignment_family','covariates'})
                self.assertTrue(all(r['label'] for r in items.values()))
                self.assertEqual({r['field'] for r in card['queries'][0]['items']}, set(CompactSemantics.model_fields))
                for field in ('variable_causal_graph','available_information'):
                    self.assertEqual(items[field]['state'], 'STATED' if stated else 'UNKNOWN')
                    self.assertEqual(items[field]['value'], raw['common'][field]['value'] if stated else None)
                html = render_confirmation_html(self.case, result)
                self.assertNotIn('<script>', html)
                if stated:
                    self.assertIn('&lt;script&gt;', html)
                self.assertFalse(card['business_approval'])
                self.assertFalse(card['scientific_approval'])
                self.assertFalse(card['core_called'])
                self.assertFalse(card['identification_ready'])

    def test_blank_required_slot_without_source_audit_stays_internal(self):
        revised = deepcopy(self.raw); revised['queries'][0]['semantics']['time_horizon']='UNKNOWN'
        card = self.run_review(revised)['confirmation_card']
        self.assertEqual(card['status'], 'MATERIAL_RECHECK_REQUIRED')
        self.assertEqual(card['questions'], [])
        self.assertIn('MISSING_SOURCE_AUDIT', [x['code'] for x in card['internal_recheck']])

    def test_reviewed_gap_becomes_plain_question_not_a_filled_value(self):
        revised = deepcopy(self.raw); revised['queries'][0]['semantics']['time_horizon']='UNKNOWN'
        item={'path':'queries.q1.semantics.time_horizon','reason':'NOT_SPECIFIED','explanation':'目标时点没有说明。'}
        r=self.run_review(revised,[item]); card=r['confirmation_card']
        self.assertEqual(card['status'],'BUSINESS_CLARIFICATION_REQUIRED')
        self.assertEqual(len(card['questions']),1)
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['time_horizon']['value'])
        self.assertNotIn('JSON',card['questions'][0]['question'])

    def test_partial_known_information_kept_alongside_open_issue(self):
        item={'path':'queries.q1.semantics.aggregation','reason':'AMBIGUOUS','explanation':'需要确认统计权重。'}
        card=self.run_review(items=[item])['confirmation_card']
        self.assertEqual(card['status'],'BUSINESS_CLARIFICATION_REQUIRED')
        self.assertEqual(card['queries'][0]['items'][4]['value'],'全部站点等权平均')

    def test_conflicting_source_is_not_automatic_approval(self):
        item={'path':'queries.q1.semantics.time_horizon','reason':'CONFLICT','explanation':'两个文件给出了不同时间。'}
        card=self.run_review(items=[item])['confirmation_card']
        self.assertEqual(card['questions'][0]['reason'],'CONFLICT')
        self.assertFalse(card['business_approval'])

    def test_invalid_paths_and_duplicate_items_rejected(self):
        item={'path':'queries.q9.semantics.time_horizon','reason':'NOT_SPECIFIED','explanation':'需要确认。'}
        with self.assertRaises(A0QualityValidationError):self.run_review(items=[item])
        item['path']='queries.q1.semantics.time_horizon'
        with self.assertRaises(A0QualityValidationError):self.run_review(items=[item,item])

    def test_open_issue_cannot_cite_another_case(self):
        item={'path':'queries.q1.semantics.time_horizon','reason':'NOT_SPECIFIED','explanation':'需要确认。','refs':['other_001']}
        with self.assertRaises(A0QualityValidationError):self.run_review(items=[item])

    def test_fewer_queries_than_initial_requires_internal_review(self):
        initial=deepcopy(self.raw);initial['queries'].append(deepcopy(initial['queries'][0]))
        card=self.run_review(initial=initial)['confirmation_card']
        self.assertIn('QUERY_REMOVED_DURING_REVIEW',[x['code'] for x in card['internal_recheck']])

    def test_reply_is_text_source_and_never_mutates_initial_or_approves(self):
        r=self.run_review(); before=self.case.model_dump(mode='json')
        updated=append_business_reply(self.case,r['confirmation_card'],'我们看两个月后的情况，所有站点每站算一份。')
        self.assertEqual(self.case.model_dump(mode='json'),before)
        self.assertEqual(updated.business_question,self.case.business_question)
        self.assertEqual(updated.sources[-1].text,'我们看两个月后的情况，所有站点每站算一份。')
        self.assertEqual(updated.sources[-1].kind.value,'BUSINESS_NARRATIVE')
        self.assertNotEqual(build_catalog(updated)[0]['ref'],build_catalog(self.case)[0]['ref'])
        self.assertFalse(r['confirmation_card']['business_approval'])

    def test_stale_card_and_blank_reply_rejected(self):
        card=self.run_review()['confirmation_card']
        updated=append_business_reply(self.case,card,'请按两个月来评估。')
        with self.assertRaises(ValueError):append_business_reply(updated,card,'确认。')
        with self.assertRaises(ValueError):append_business_reply(self.case,card,'   ')

    def test_old_reference_not_reused_after_new_business_reply(self):
        card=self.run_review()['confirmation_card']
        updated=append_business_reply(self.case,card,'请按两个月来评估。')
        with self.assertRaises(A0QualityValidationError):make_review_request(updated,self.raw)

    def test_request_has_original_sources_and_no_gold_or_approval(self):
        _,user,_=make_review_request(self.case,self.raw)
        payload=json.loads(user.split('\n',1)[1].split('\n\n复核输出 Schema')[0])
        self.assertEqual(payload['business_question'],self.case.business_question)
        self.assertEqual(set(payload),{'case_id','business_question','sources','source_catalog'})
        schema=json.loads(user.split('\n\n复核输出 Schema：\n')[1])
        paths=schema['$defs']['OpenItem']['properties']['path']['enum']
        self.assertIn('queries.q1.semantics.comparator',paths)
        self.assertNotIn('queries.0.semantics.comparator',paths)

    def test_two_model_calls_and_no_hidden_retry(self):
        parent=self
        class Provider:
            name='mock';calls=0
            def generate_json(self,**kwargs):
                self.calls+=1
                return deepcopy(parent.raw if self.calls==1 else {'draft':parent.raw,'open_items':[]})
        p=Provider();r=ReviewedIntake(p).formulate(self.case)
        self.assertEqual(p.calls,2);self.assertFalse(r['quality']['core_called'])
        class Bad(Provider):
            def generate_json(self,**kwargs):self.calls+=1;return {'queries':[]}
        bad=Bad()
        with self.assertRaises(A0QualityValidationError):ReviewedIntake(bad).formulate(self.case)
        self.assertEqual(bad.calls,1)

    def test_model_approval_fields_are_rejected(self):
        for field in ('business_approval','scientific_approval','identification_ready'):
            with self.subTest(field=field),self.assertRaises(A0QualityValidationError):
                build_review_result(self.case,self.raw,{'draft':self.raw,'open_items':[],field:True})

    def test_html_escapes_untrusted_values(self):
        r=self.run_review();r['confirmation_card']['queries'][0]['goal']='<script>alert(1)</script>'
        html=render_confirmation_html(self.case,r)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('查看依据',html)

    def test_no_math_core_loaded(self):
        p=subprocess.run([sys.executable,'-B','-c','import sys,cfm_id_llm.reviewed_intake; print("cfm_id_bridge" in sys.modules,"pfn_pipeline" in sys.modules)'],capture_output=True,text=True,check=True)
        self.assertEqual(p.stdout.strip(),'False False')

    def test_cli_plain_question_and_plain_reply_without_user_json(self):
        from cfm_id_llm.natural_intake_cli import main
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);a=base/'model1.json';b=base/'model2.json'
            a.write_text(json.dumps(self.raw,ensure_ascii=False),encoding='utf8')
            b.write_text(json.dumps({'draft':self.raw,'open_items':[]},ensure_ascii=False),encoding='utf8')
            first=base/'first';second=base/'second'
            with redirect_stdout(StringIO()):
                code=main(['--question',self.case.business_question,'--case-id',self.case.case_id,
                    '--review-mode','rewrite','--mock-extraction',str(a),'--mock-review',str(b),'--output-dir',str(first)])
            self.assertEqual(code,0)
            before=(first/'public_input.json').read_bytes()
            with redirect_stdout(StringIO()):
                code=main(['--resume',str(first),'--reply','我们想改看三个月后的情况。','--preview','--output-dir',str(second)])
            self.assertEqual(code,0)
            self.assertEqual((first/'public_input.json').read_bytes(),before)
            new=json.loads((second/'public_input.json').read_text(encoding='utf8'))
            self.assertEqual(new['sources'][-1]['text'],'我们想改看三个月后的情况。')
            self.assertTrue((first/'business_confirmation.html').exists())

    def test_cli_rejects_overwrite_and_missing_online_consent(self):
        from cfm_id_llm.natural_intake_cli import main
        with tempfile.TemporaryDirectory() as d,redirect_stdout(StringIO()):
            self.assertEqual(main(['--question','我们想知道效果。','--preview','--output-dir',d]),2)
            out=Path(d)/'external'
            self.assertEqual(main(['--question','我们想知道效果。','--provider','openai-chat','--model','unused','--output-dir',str(out)]),2)
            self.assertFalse(out.exists())

    def test_patch_changes_only_named_field_and_retains_evidence(self):
        before=deepcopy(self.raw)
        replacement=deepcopy(self.raw['queries'][0]['semantics']['time_horizon'])
        replacement['value']='实施八周后'
        raw={'patches':[{'path':'queries.q1.semantics.time_horizon','replacement':replacement,'reason':'核对时间表述。'}]}
        r=build_patch_result(self.case,self.raw,raw)
        self.assertEqual(self.raw,before)
        self.assertEqual(r['reviewed_wire']['draft']['queries'][0]['semantics']['aggregation']['value'],'全部站点等权平均')
        self.assertEqual(len(r['changes']),1)
        self.assertFalse(r['confirmation_card']['business_approval'])

    def test_patch_unknown_without_source_audit_cannot_be_complete(self):
        raw={'patches':[{'path':'queries.q1.semantics.time_horizon','replacement':'UNKNOWN','reason':'需要重新确认。'}]}
        r=build_patch_result(self.case,self.raw,raw)
        self.assertEqual(r['confirmation_card']['status'],'MATERIAL_RECHECK_REQUIRED')

    def test_patch_cannot_add_query_or_scientific_field_or_reuse_bad_ref(self):
        for path in ['queries.q9.semantics.time_horizon','common.assumptions','queries.q1.kind']:
            with self.subTest(path=path),self.assertRaises(A0QualityValidationError):
                build_patch_result(self.case,self.raw,{'patches':[{'path':path,'replacement':'UNKNOWN','reason':'需要修改。'}]})
        replacement=deepcopy(self.raw['queries'][0]['semantics']['time_horizon']);replacement['refs']=['foreign']
        with self.assertRaises(A0QualityValidationError):
            build_patch_result(self.case,self.raw,{'patches':[{'path':'queries.q1.semantics.time_horizon','replacement':replacement,'reason':'需要修改。'}]})

    def test_duplicate_patches_are_rejected(self):
        patch={'path':'queries.q1.semantics.time_horizon','replacement':'UNKNOWN','reason':'需要修改。'}
        with self.assertRaises(A0QualityValidationError):build_patch_result(self.case,self.raw,{'patches':[patch,patch]})
        kind={'query_id':'q1','kind':'DIRECT_EFFECT'}
        with self.assertRaises(A0QualityValidationError):build_patch_result(self.case,self.raw,{'query_kinds':[kind,kind]})

    def test_patch_request_bound_to_case_and_declared_paths(self):
        _,user,_=make_patch_request(self.case,self.raw)
        schema=json.loads(user.split('\n\n输出 Schema：\n')[1])
        paths=schema['$defs']['FieldPatch']['properties']['path']['enum']
        self.assertIn('queries.q1.semantics.time_horizon',paths)
        self.assertNotIn('common.assumptions',paths)

    def test_patch_flow_has_exactly_two_model_calls(self):
        parent=self
        class P:
            name='mock';calls=0
            def generate_json(self,**kwargs):
                self.calls+=1;return deepcopy(parent.raw) if self.calls==1 else {'patches':[]}
        p=P();r=PatchedIntake(p).formulate(self.case)
        self.assertEqual(p.calls,2);self.assertFalse(r['confirmation_card']['core_called'])

    def test_policy_remaining_assignment_average_can_be_inapplicable(self):
        raw=deepcopy(self.raw);q=raw['queries'][0];q['kind']='POLICY_OPTIMIZATION'
        q['semantics']['policy_assignment']=deepcopy(q['semantics']['intervention'])
        q['semantics']['standardization_distribution']='NOT_APPLICABLE'
        r=build_patch_result(self.case,raw,{'patches':[]})
        self.assertFalse(any(x['code']=='INVALID_NOT_APPLICABLE' for x in r['confirmation_card']['internal_recheck']))
        self.assertTrue(r['quality']['prompt_version'].endswith('v0.15.3'))
        self.assertFalse(r['confirmation_card']['scientific_approval'])
        q['kind']='DIRECT_EFFECT'
        r=build_patch_result(self.case,raw,{'patches':[]})
        self.assertTrue(any(x['code']=='INVALID_NOT_APPLICABLE' and x['path'].endswith('standardization_distribution') for x in r['confirmation_card']['internal_recheck']))

    def test_optimizer_output_is_not_a_business_input_question(self):
        raw=deepcopy(self.raw);q=raw['queries'][0];q['kind']='POLICY_OPTIMIZATION'
        q['semantics']['policy_assignment']=deepcopy(q['semantics']['intervention'])
        q['semantics']['intervention']='UNKNOWN'
        note={'path':'queries.q1.semantics.intervention','reason':'NOT_SPECIFIED','explanation':'最优名单还没选出。'}
        r=build_patch_result(self.case,raw,{'open_items':[note]})
        card=r['confirmation_card']
        self.assertEqual(card['questions'],[])
        self.assertEqual(len(card['deferred_technical_review']),1)
        self.assertEqual(card['status'],'DRAFT_FOR_BUSINESS_REVIEW')
        self.assertFalse(card['identification_ready'])
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['intervention']['value'])
        note['reason']='CONFLICT'
        r=build_patch_result(self.case,raw,{'open_items':[note]})
        self.assertEqual(len(r['confirmation_card']['questions']),1)

    def test_changed_known_target_kind_cannot_silently_replace_initial(self):
        result=build_patch_result(self.case,self.raw,{'query_kinds':[{'query_id':'q1','kind':'SPILLOVER_EFFECT'}]})
        issues=result['confirmation_card']['internal_recheck']
        self.assertTrue(any(x['code']=='TARGET_KIND_CHANGE_REQUIRES_REVIEW' for x in issues))
        self.assertEqual(result['confirmation_card']['status'],'MATERIAL_RECHECK_REQUIRED')
        self.assertEqual(self.raw['queries'][0]['kind'],'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN')
        self.assertFalse(result['confirmation_card']['identification_ready'])

if __name__=='__main__':unittest.main()
