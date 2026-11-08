"""Check allocation, evaluation population and incomplete targets separately."""
from copy import deepcopy
import unittest
from examples.intent_target_variants_fixture import (
    CASES,public_bundle,gold_reading,independent_coordinates,inquiry,synthetic_context,
    actual_scientific_sources,actual_scientific_licenses,sha,
)
from cfm_id.intent_submission import submit
from evaluation.business_fixed_intent_base import project
from cfm_id_bridge.bridge import formal_target_fingerprint_v29


class TargetVariationAcceptance(unittest.TestCase):
    def test_eight_predeclared_variants_through_full_submission(self):
        for name,f in CASES.items():
            with self.subTest(case=name):
                b,r=public_bundle(name),gold_reading(name)
                if f['final']=='NEEDS_INPUT':out=submit(b,r,'FIXED_POLICY')
                else:
                    p,c,a=synthetic_context(name,b,r)
                    out=submit(b,r,'FIXED_POLICY',packet=p,context=c,submission_review=a,synthetic_protocol_selected=True)
                self.assertEqual(out['state'],f['final'])
                if f['final']=='CORE_POINT':
                    self.assertEqual(out['query_views'][0]['route'],f['route'])
                    self.assertTrue(out['query_views'][0]['certificate_replayed'])
                elif f['final']=='NEEDS_INPUT':self.assertFalse(out['core_called'])
                else:
                    self.assertTrue(out['core_called'])
                    self.assertEqual(out['query_views'][0]['reason_code'],'ZERO_POLICY_SIGNATURE_SUPPORT')
                    self.assertFalse(out['query_views'][0]['certificate_replayed'])
                self.assertFalse(out['production_admission'] or out['estimation_called'] or out['policy_called'])
                self.assertEqual(out['candidate_model_calls'],0)

    def test_population_changes_weights_not_treatment_allocation(self):
        a,b=inquiry('mixed_all'),inquiry('mixed_b')
        self.assertEqual(a.target.policy_assignment,b.target.policy_assignment)
        self.assertEqual(b.target.policy_assignment,(1,0,1))
        self.assertEqual(b.target.unit_weights,('0','1','0'))
        self.assertNotEqual(formal_target_fingerprint_v29(a),formal_target_fingerprint_v29(b))
        self.assertEqual(sha(a.study),sha(b.study))
        self.assertEqual(actual_scientific_sources(a),actual_scientific_sources(b))
        self.assertEqual(actual_scientific_licenses(a),actual_scientific_licenses(b))

    def test_support_pair_changes_only_evaluated_population(self):
        a,b=inquiry('signature_subgroup'),inquiry('signature_unsupported_all')
        self.assertEqual(a.target.policy_assignment,b.target.policy_assignment)
        self.assertEqual(a.target.unit_weights,('0','1/2','1/2','0','0'))
        self.assertEqual(actual_scientific_sources(a),actual_scientific_sources(b))
        self.assertEqual(actual_scientific_licenses(a),actual_scientific_licenses(b))

    def test_unknown_treatment_outside_evaluation_cohort_is_not_deleted(self):
        b,r=public_bundle('missing_assignment_b'),gold_reading('missing_assignment_b')
        out=submit(b,r,'FIXED_POLICY')
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertEqual(out['intent_condition_review']['q1']['missing_conditions'],['first.C'])
        self.assertEqual(out['reading_candidate']['questions']['q1']['first'],{'A':1,'B':0,'C':None})
        self.assertEqual(out['reading_candidate']['questions']['q1']['population'],['B'])
        with self.assertRaises(ValueError):independent_coordinates('missing_assignment_b')

    def test_population_order_does_not_change_semantics(self):
        name='signature_subgroup';b,r=public_bundle(name),gold_reading(name)
        r['questions']['q1']['population'].reverse()
        self.assertEqual(project(b,r)[0],{'q1':independent_coordinates(name)})
        p,c,a=synthetic_context(name,b,r)
        self.assertEqual(submit(b,r,'FIXED_POLICY',packet=p,context=c,submission_review=a,synthetic_protocol_selected=True)['state'],'CORE_POINT')

    def test_old_population_review_cannot_approve_a_new_population(self):
        b,r=public_bundle('mixed_all'),gold_reading('mixed_all')
        p,c,a=synthetic_context('mixed_all',b,r)
        r['questions']['q1']['population']=['B']
        out=submit(b,r,'FIXED_POLICY',packet=p,context=c,submission_review=a,synthetic_protocol_selected=True)
        self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertEqual(c.core_port.calls,[])

    def test_reviewer_rejects_all_on_substitution_or_population_confusion(self):
        for wrong in ('all_on','treated_population'):
            b,r=public_bundle('mixed_b'),gold_reading('mixed_b')
            if wrong=='all_on':r['questions']['q1']['first']={n:1 for n in b['node_order']}
            else:r['questions']['q1']['population']=['A','C']
            with self.assertRaisesRegex(ValueError,'INDEPENDENT_VARIANT'):synthetic_context('mixed_b',b,r)

    def test_single_unit_unknown_aggregation_is_not_silently_repaired(self):
        b,r=public_bundle('mixed_b'),gold_reading('mixed_b')
        r['questions']['q1']['aggregation']='不明确'
        out=submit(b,r,'FIXED_POLICY')
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertEqual(out['intent_condition_review']['q1']['missing_conditions'],['aggregation'])
        self.assertEqual(out['reading_candidate'],r)
        self.assertFalse(out['core_called'])


if __name__=='__main__':unittest.main()
