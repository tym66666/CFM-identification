"""Boundary and end-to-end regressions for the opt-in workflow, without network."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cfm_id import mean_order_business as legacy
from evaluation import mean_order_workflow as workflow, mean_order_count_guidance as request
from evaluation import mean_order_factored_reading as protocol, mean_order_factored_review as adapter
from examples.mean_order_business_fixture import make_case, endpoint_reviews, business_review
from examples.mean_order_workflow_fixture import export_fixture, replay_synthetic


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = make_case()
        self.bundle = self.case['bundle']
        self.wire = protocol.reference_wire(self.bundle, self.case['candidate'])
        self.fixture = export_fixture(self.case, provenance='Independent hypothetical reference frozen before execution')

    def replay(self, wire=None, fixture=None):
        return replay_synthetic(self.bundle, self.wire if wire is None else wire,
                                self.fixture if fixture is None else fixture)

    def test_request_exact_and_private_payload_rejected(self):
        system, user = request.make_request(self.bundle)
        self.assertEqual(workflow.make_request(self.bundle), dict(system=system,user=user))
        for extra in ('science','references','review','expected_problem'):
            with self.subTest(extra=extra), self.assertRaises(workflow.WorkflowError):
                workflow.make_request(dict(self.bundle, **{extra: self.fixture}))

    def test_external_read_requires_both_permissions_and_calls_provider_once(self):
        provider = Mock(); provider.generate_json.return_value = self.wire
        for kw in ({}, {'allow_external':True}, {'allow_document_sharing':True},
                   {'allow_external':1,'allow_document_sharing':True}):
            with self.assertRaises(workflow.WorkflowError):
                workflow.read_once(self.bundle, provider, **kw)
        provider.generate_json.assert_not_called()
        out = workflow.read_once(self.bundle,provider,allow_external=True,allow_document_sharing=True)
        provider.generate_json.assert_called_once_with(system_prompt=workflow.make_request(self.bundle)['system'],
            user_prompt=workflow.make_request(self.bundle)['user'])
        self.assertEqual(out['state'],'REVIEW_REQUIRED'); self.assertFalse(out['result']['core_called'])
        self.assertEqual(out['candidate_origin'],'PROVIDER_RESPONSE')

    def test_provider_failure_never_echoes_credential_or_becomes_semantic_failure(self):
        provider = Mock();provider.generate_json.side_effect = RuntimeError('SECRET_SENTINEL_DO_NOT_ECHO')
        with self.assertRaises(workflow.WorkflowError) as caught:
            workflow.read_once(self.bundle,provider,allow_external=True,allow_document_sharing=True)
        self.assertEqual(str(caught.exception),'LLM_REQUEST_FAILED_NO_REPLY')
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(provider.generate_json.call_count,1)

    def test_inspect_and_missing_review_cannot_call_solver(self):
        with patch.object(legacy,'submit',side_effect=AssertionError('no scientific approval')):
            for out in (workflow.inspect_candidate(self.bundle,self.wire,science=self.case['science']),
                        workflow.submit_reviewed(self.bundle,self.wire,science=self.case['science'])):
                self.assertEqual(out['state'],'REVIEW_REQUIRED')
                self.assertFalse(out['result']['core_called'])
                self.assertIsNone(out['answer']['exact_interval'])
                self.assertFalse(out['review_worksheet']['is_approval'])

    def test_partial_and_raw_reply_preserved(self):
        before=deepcopy(self.wire);out=self.replay()
        self.assertEqual(out['state'],'PARTIAL')
        self.assertEqual(out['answer']['exact_interval'],['1/5','1'])
        self.assertTrue(out['result']['bounded_certificate_replayed'])
        self.assertEqual(out['wire_candidate'],before);self.assertEqual(self.wire,before)
        self.assertTrue(out['synthetic_reference_check']['passed'])
        self.assertFalse(out['production_admission']);self.assertFalse(out['estimation_handoff_allowed'])

    def test_point_supported_comparison(self):
        c=make_case(first=[1,1,0,0],second=[0,0,1,1])
        w=protocol.reference_wire(c['bundle'],c['candidate'])
        f=export_fixture(c,provenance='Independently specified supported-policy reference')
        out=replay_synthetic(c['bundle'],w,f)
        self.assertEqual(out['state'],'POINT');self.assertTrue(out['result']['bounded_certificate_replayed'])
        self.assertEqual(out['answer']['exact_interval'],['0','0'])

    def test_missing_scope_retains_specific_question_and_does_not_repair(self):
        wire=deepcopy(self.wire);wire['order_reading']['claims'][1]['scope']='UNKNOWN'
        with patch.object(legacy,'submit',side_effect=AssertionError('incomplete reading')):
            out=self.replay(wire)
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertFalse(out['synthetic_reference_check']['passed'])
        self.assertTrue(any('原试点未出现' in q for q in out['clarification_questions']))
        self.assertEqual(out['wire_candidate'],wire)

    def test_unresolved_adoption_and_observed_projection_keep_full_wire(self):
        for changes in (dict(declaration='尚不明确'),
                        dict(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')):
            wire=deepcopy(self.wire);wire['order_reading']['claims'][1].update(changes)
            out=self.replay(wire)
            self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['result']['core_called'])
            self.assertEqual(out['wire_candidate'],wire)
            if changes['declaration']=='仅报告观察':
                self.assertFalse(out['review_worksheet']['projection_receipt']['legacy_projection_is_lossless'])

    def test_conflict_and_unsupported_remain_distinct_from_nonidentification(self):
        conflict=deepcopy(self.wire);conflict['order_reading']['reported_conflict']=True
        out=self.replay(conflict);self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertTrue(any('矛盾' in q for q in out['clarification_questions']))
        pathwise=deepcopy(self.wire);pathwise['order_reading']['claims'][1]['quantity']='每次潜在结果'
        out=self.replay(pathwise);self.assertEqual(out['state'],'UNSUPPORTED')
        self.assertIn('PATHWISE_RESTRICTION_NOT_ADAPTED',out['unsupported_restrictions'])
        self.assertFalse(out['result']['bounded_backend_called']);self.assertIsNone(out['answer']['exact_interval'])

    def test_wrong_known_target_with_valid_shape_withholds_independent_review(self):
        wire=deepcopy(self.wire);q=wire['comparison']['reading']['questions']['q1'];q['first'],q['second']=q['second'],q['first']
        with patch.object(legacy,'submit',side_effect=AssertionError('wrong business target')):
            out=self.replay(wire)
        self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertFalse(out['synthetic_reference_check']['passed'])
        self.assertEqual(out['answer']['reason_code'],'INDEPENDENT_FACTORED_SEMANTIC_REVIEW_WITHHELD')
        self.assertEqual(out['wire_candidate'],wire)

    def test_target_missing_fields_have_questions_without_filling_them(self):
        wire=deepcopy(self.wire);q=wire['comparison']['reading']['questions']['q1']
        q['population']=None;q['aggregation']='不明确';q['first']['A']=None;q['second']['B']=None
        out=workflow.inspect_candidate(self.bundle,wire)
        self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['result']['core_called'])
        questions=out['clarification_questions']
        for part in ('评价哪些对象','汇总方式','所问安排中“A”','比较基准中“B”'):
            self.assertTrue(any(part in text for text in questions))
        self.assertEqual(out['wire_candidate'],wire)
        self.assertEqual(set(out['target_missing'][0]['missing']),{'population','aggregation','first.A','second.B'})

    def test_unclear_intent_is_a_question_not_a_guessed_comparison(self):
        wire=deepcopy(self.wire);wire['comparison']['reading']['intents']['q1']['kind']='不明确'
        out=workflow.inspect_candidate(self.bundle,wire)
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertTrue(any('比较两个安排' in text for text in out['clarification_questions']))
        self.assertEqual(out['wire_candidate'],wire)

    def test_wrong_source_or_extra_approval_blocks(self):
        bad=deepcopy(self.wire);bad['order_reading']['claims'][0]['source_ids']=['src_'+'0'*64]
        extra=dict(self.wire,scientific_approval=True)
        for wire in (bad,extra,[],{'order_reading':{'claims':[7]}}):
            out=workflow.inspect_candidate(self.bundle,wire)
            self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['result']['core_called'])

    def test_stale_full_wire_review_still_rejected_by_existing_adapter(self):
        chain=endpoint_reviews(self.case,self.case['candidate']);old=business_review(self.case,self.case['candidate'],chain)
        review=adapter.ReviewedFactoredReading(**adapter.worksheet(self.bundle,self.wire,legacy_review=old),
            reviewer='Synthetic test reviewer',evidence='Independent test assertion of original full wire',
            reviewed_full_wire_semantics_and_sources=True,reviewed_projection_and_losses=True,synthetic_fixture=True)
        wire=deepcopy(self.wire);wire['order_reading']['claims'].reverse()
        out=workflow.submit_reviewed(self.bundle,wire,science=self.case['science'],review=old,factored_review=review,**chain)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['result']['core_called'])

    def test_fixture_cannot_bind_another_bundle(self):
        bundle=deepcopy(self.bundle);bundle['documents']['new.txt']='新材料。'
        with self.assertRaises(workflow.WorkflowError):replay_synthetic(bundle,self.wire,self.fixture)

    def test_fixture_does_not_silently_discard_an_extra_endpoint(self):
        for field in ('inquiries','information'):
            fixture=deepcopy(self.fixture);fixture['base'][field]['unmodeled']=fixture['base'][field]['first']
            with self.assertRaises(workflow.WorkflowError):self.replay(fixture=fixture)

    def test_cli_request_inspect_replay_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name,obj in [('bundle',self.bundle),('candidate',self.wire),('fixture',self.fixture)]:
                workflow.write_json(p/(name+'.json'),obj)
            common=['--bundle',str(p/'bundle.json')]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(workflow.main(['request',*common,'--output',str(p/'request.json')]),0)
                self.assertEqual(workflow.main(['inspect',*common,'--candidate',str(p/'candidate.json'),'--output',str(p/'inspect.json')]),0)
                argv=['replay-synthetic',*common,'--candidate',str(p/'candidate.json'),'--fixture',str(p/'fixture.json'),'--output',str(p/'result.json')]
                self.assertEqual(workflow.main(argv),2);self.assertFalse((p/'result.json').exists())
                self.assertEqual(workflow.main(argv+['--allow-synthetic-review']),0)
                original=(p/'result.json').read_bytes()
                self.assertEqual(workflow.main(argv+['--allow-synthetic-review']),2)
                self.assertEqual((p/'result.json').read_bytes(),original)
            self.assertEqual(workflow.load_json(p/'request.json'),workflow.make_request(self.bundle))
            self.assertEqual(workflow.load_json(p/'inspect.json')['state'],'REVIEW_REQUIRED')
            self.assertEqual(workflow.load_json(p/'result.json')['state'],'PARTIAL')

    def test_json_parse_failure_duplicate_and_nonfinite_fail_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'
            for text in ('{bad','{"x":1,"x":2}','{"x":NaN}'):
                p.write_text(text,encoding='utf-8')
                with self.assertRaises(workflow.WorkflowError):workflow.load_json(p)


if __name__=='__main__':unittest.main()
