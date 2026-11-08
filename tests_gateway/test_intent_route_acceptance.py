"""Full synthetic intent -> review -> real Core -> independent replay boundaries."""
from copy import deepcopy
from dataclasses import replace
import unittest

from cfm_id.business_entry import prepare_request, preview
from cfm_id.intent_submission import submit, submission_worksheet, ReviewedIntentSubmissionV057
from examples.intent_routes_fixture import (
    CASES, ROUTES, public_bundle, gold_reading, synthetic_context, reviewed_submission, inquiry,
)
from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome


class IntentRouteAcceptance(unittest.TestCase):
    def test_local_d1_effects_keep_reviews_and_replay_two_queries(self):
        from examples import nbib_d1_fixture as fixture
        from cfm_id.intent_submission import reviewed_projection
        item=deepcopy(fixture.load_case());b=item['bundle'];r=deepcopy(item['raw'])
        r['intents']={q:dict(kind='比较',quote=t) for q,t in b['question_slots'].items()}
        for q,c in r['questions'].items():
            c.pop('operation');c['peer_evidence']={s:b['question_slots'][q] for s in ('first','second')}
        item['raw']=reviewed_projection(b,r,'D1_EFFECTS')
        c=fixture.synthetic_context(item);p=item['packet']
        a=reviewed_submission(b,r,'D1_EFFECTS',p,c)
        out=submit(b,r,'D1_EFFECTS',packet=p,context=c,submission_review=a,synthetic_protocol_selected=True)
        self.assertEqual(out['state'],'CORE_POINT')
        self.assertEqual(len(out['query_views']),2)
        self.assertTrue(all(q['certificate_replayed'] for q in out['query_views']))

    def test_local_d2_staged_reading_and_changed_intent_review(self):
        from tests_gateway.test_business_question_intent_base import read,split
        from examples import nbib_d2_fixture as fixture
        from cfm_id.intent_submission import reviewed_projection
        from evaluation.business_core_pilot_base import canonical_hash
        b=read('public/positive_bundle.json');e=read('recorded/study_envelope.json')
        r=split(b,read('recorded/positive_candidate.json'),'水平')
        item=deepcopy(fixture.load_case());item.update(bundle=b,raw=reviewed_projection(b,r,'D2_ARM',e))
        item['packet']['bundle_sha256']=canonical_hash(b);p=item['packet'];c=fixture.synthetic_context(item)
        a=reviewed_submission(b,r,'D2_ARM',p,c,e)
        out=submit(b,r,'D2_ARM',e,p,context=c,submission_review=a,synthetic_protocol_selected=True)
        self.assertEqual(out['state'],'CORE_POINT')
        self.assertTrue(out['query_views'][0]['certificate_replayed'])
        r['intents']['q1']['quote']='另一项问题'
        before=list(c.core_port.calls)
        bad=submit(b,r,'D2_ARM',e,p,context=c,submission_review=a,synthetic_protocol_selected=True)
        self.assertNotEqual(bad['state'],'CORE_POINT')
        self.assertEqual(c.core_port.calls,before)

    def fixture(self, name, variant=None):
        b, r = public_bundle(name), gold_reading(name)
        p, c, a = synthetic_context(name, b, r, variant)
        return b, r, p, c, a

    def run_case(self, b, r, p, c, a):
        return submit(b, r, 'FIXED_POLICY', packet=p, context=c,
                      submission_review=a, synthetic_protocol_selected=True)

    def test_four_routes_positive_actual_core_and_replay(self):
        for name in CASES:
            with self.subTest(route=ROUTES[name]):
                b, r, p, c, a = self.fixture(name)
                out = self.run_case(b, r, p, c, a)
                self.assertEqual(out['state'], 'CORE_POINT')
                self.assertEqual(out['query_views'][0]['route'], ROUTES[name])
                self.assertTrue(out['identification']['results'][0]['certificate_replay'])
                self.assertEqual(c.core_port.last_real_results['q1']['verification_level'], 'CORE_REPLAY_VERIFIED')
                self.assertEqual(out['reading_candidate'], r)
                self.assertFalse(out['production_admission'])
                self.assertFalse(out['estimation_called'] or out['policy_called'])

    def test_worksheet_is_not_an_approval(self):
        b, r, p, c, _ = self.fixture(CASES[0])
        sheet = submission_worksheet(b, r, 'FIXED_POLICY', p, c)
        with self.assertRaises(ValueError): ReviewedIntentSubmissionV057.model_validate(sheet)
        out = self.run_case(b, r, p, c, sheet)
        self.assertEqual(out['state'], 'CHECK_BLOCKED')
        self.assertEqual(c.core_port.calls, [])

    def test_missing_review_never_calls_core_in_all_four_routes(self):
        for name in CASES:
            b, r, p, c, a = self.fixture(name)
            for packet, context, record in ((p,c,None), (p,None,a), (None,c,a)):
                with self.subTest(route=name, missing=(packet is None,context is None,record is None)):
                    out = self.run_case(b,r,packet,context,record)
                    self.assertEqual(out['state'], 'REVIEW_REQUIRED')
                    self.assertFalse(out['core_called'])
            self.assertEqual(c.core_port.calls, [])

    def test_a4_and_a5_packet_omissions_block_every_route(self):
        for name in CASES:
            for field in ('a4_reference','a5_reference'):
                with self.subTest(route=name, field=field):
                    b,r,p,c,a=self.fixture(name)
                    p['queries']['q1'].pop(field)
                    # Even a fresh outer wire review cannot grant missing science.
                    a=reviewed_submission(b,r,'FIXED_POLICY',p,c)
                    out=self.run_case(b,r,p,c,a)
                    self.assertEqual(out['state'],'CHECK_BLOCKED')
                    self.assertEqual(c.core_port.calls,[])

    def test_reading_and_study_tampering_invalidates_outer_review(self):
        for name in CASES:
            for change in ('target','text','study'):
                with self.subTest(route=name, change=change):
                    b,r,p,c,a=self.fixture(name)
                    if change=='target': r['questions']['q1']['first'][b['node_order'][0]]=0
                    elif change=='text': b['documents']['study.txt']+='新的未审核事实。'
                    else: p['queries']['q1']['study_sha256']='0'*64
                    out=self.run_case(b,r,p,c,a)
                    self.assertEqual(out['state'],'CHECK_BLOCKED')
                    self.assertEqual(c.core_port.calls,[])

    def test_rebinding_wire_does_not_override_independent_target(self):
        from evaluation.business_core_pilot_base import canonical_hash
        for name in CASES:
            b,r,p,c,_=self.fixture(name)
            r['questions']['q1']['first'][b['node_order'][0]]=0
            c=replace(c,approval=c.approval.model_copy(update={'model_draft_sha256':canonical_hash(r)}))
            a=reviewed_submission(b,r,'FIXED_POLICY',p,c)
            out=self.run_case(b,r,p,c,a)
            self.assertEqual(out['state'],'CHECK_BLOCKED')
            self.assertEqual(c.core_port.calls,[])

    def test_missing_arrangement_retains_level_and_known_coordinate(self):
        for name in CASES:
            b,r=public_bundle(name,'partial'),gold_reading(name,'partial')
            out=submit(b,r,'FIXED_POLICY')
            self.assertEqual(out['state'],'NEEDS_INPUT')
            receipt=out['intent_condition_review']['q1']
            self.assertEqual(receipt['intent']['kind'],'水平')
            self.assertNotIn('first.'+b['node_order'][0],receipt['missing_conditions'])
            self.assertEqual(out['reading_candidate']['questions']['q1']['first'][b['node_order'][0]],1)
            self.assertFalse(out['core_called'])

    def test_incomplete_comparison_is_not_a_policy_level(self):
        b,r=public_bundle(CASES[0],'comparison'),gold_reading(CASES[0],'comparison')
        out=submit(b,r,'FIXED_POLICY')
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertEqual(out['intent_condition_review']['q1']['intent']['kind'],'比较')
        self.assertFalse(out['core_called'])

    def test_missing_second_object_is_not_repaired(self):
        b,r=public_bundle(CASES[0],'comparison'),gold_reading(CASES[0],'comparison')
        r['questions']['q1']['second']=None
        out=submit(b,r,'FIXED_POLICY')
        self.assertEqual(out['state'],'READING_REVIEW_REQUIRED')
        self.assertIsNone(out['reading_candidate']['questions']['q1']['second'])
        self.assertFalse(out['core_called'])

    def test_complete_comparison_stays_unsupported_not_coerced_to_level(self):
        b,r=public_bundle(CASES[0],'comparison'),gold_reading(CASES[0],'comparison')
        r['questions']['q1']['first']={n:1 for n in b['node_order']}
        r['questions']['q1']['second']={n:0 for n in b['node_order']}
        self.assertEqual(submit(b,r,'FIXED_POLICY')['state'],'UNSUPPORTED')

    def test_illegal_contracts_are_rejected(self):
        for change in ('extra_approval','bool','null_state','stale_quote','invented_baseline','unknown_node'):
            b,r=public_bundle(CASES[0]),gold_reading(CASES[0])
            if change=='extra_approval': r['scientific_approval']=True
            elif change=='bool': r['questions']['q1']['first']['A']=True
            elif change=='null_state': r['questions']['q1']['first']=None
            elif change=='stale_quote': r['intents']['q1']['quote']='另一条业务问题'
            elif change=='invented_baseline': r['questions']['q1']['second']={n:0 for n in b['node_order']}
            else: r['questions']['q1']['first']['unknown']=1
            with self.subTest(change=change):
                self.assertEqual(preview(b,r,'FIXED_POLICY')['state'],'READING_REVIEW_REQUIRED')

    def test_off_support_without_sufficiency_is_not_certified(self):
        for name in ('randomized_signature','observational_signature'):
            b,r,p,c,a=self.fixture(name,'missing_sufficiency')
            out=self.run_case(b,r,p,c,a)
            self.assertEqual(out['state'],'UNSUPPORTED')
            self.assertTrue(out['core_called'])
            self.assertFalse(out['query_views'][0]['certificate_replayed'])
            self.assertEqual(out['candidate_model_calls'],0)

    def test_observational_missing_exchangeability_blocked_by_both_layers(self):
        for name in ('observational_full','observational_signature'):
            b,r,p,c,a=self.fixture(name,'missing_exchangeability')
            out=self.run_case(b,r,p,c,a)
            self.assertEqual(out['state'],'CHECK_BLOCKED')
            self.assertFalse(out['core_called'])
            mathematical=identify_network_business_query(inquiry(name,'missing_exchangeability'))
            self.assertNotEqual(mathematical.status,'POINT')
            with self.assertRaises(ValueError): replay_verified_business_outcome(mathematical)

    def test_wrong_route_crosswalk_cannot_be_resubmitted(self):
        b,r,p,c,a=self.fixture(CASES[0])
        c.core_port.crosswalks['q1']=c.core_port.crosswalks['q1'].model_copy(update={'approved_theorem_route':'R2_MEAN_SIGNATURE'})
        a=reviewed_submission(b,r,'FIXED_POLICY',p,c)
        out=self.run_case(b,r,p,c,a)
        self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertEqual(c.core_port.calls,[])

    def test_prompts_contain_no_private_science_or_route_answers(self):
        for name in CASES:
            req=prepare_request(public_bundle(name),'FIXED_POLICY')
            for word in ('SYNTHETIC_V057_A4','SYNTHETIC_V057_A5','r2_sufficiency','approved_theorem_route','gold_reading'):
                self.assertNotIn(word,req['user'])


if __name__=='__main__': unittest.main()
