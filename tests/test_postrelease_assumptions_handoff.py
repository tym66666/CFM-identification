"""Post-release v2.7 P0 scope and no-estimator handoff safeguards.

The test fixtures are synthetic. Passing software replay does not establish the
empirical validity of randomized/exchangeability/sufficiency assumptions.
"""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from pfn_pipeline import inspect_verified_business_handoff_v27 as public_handoff, implemented_assumption_catalog_v27 as public_catalog
from pfn_pipeline.identification_assumption_inventory import (
    implemented_assumption_catalog_v27, requirements_for_route_v27,
)
from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec,TwoStageQuotaMixtureDesignV27
from examples.run_two_stage import arm as make_d6_arm
from examples.run_postrelease_coverage import main,STEM
import test_business_route_closure as fixture_module


class V27PostReleaseHandoffAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These represent every officially reachable typed business POINT route,
        # including a genuinely off-support R3-Signature (not secretly R3-Full).
        fixture_module.BusinessRouteClosureV26.setUpClass()
        cls.fixtures=fixture_module.BusinessRouteClosureV26
        net=NetworkExposureSpec(network_id='v27-two-stage-cross-group-six',
            node_ids=list('abcdef'),undirected_edges=[('a','c'),('a','e'),('b','d'),('b','f'),('c','e'),('d','f')])
        design=TwoStageQuotaMixtureDesignV27(groups=(('a','b'),('c','d'),('e','f')),
            quota_profiles=((1,1,1),(2,1,0)),profile_probabilities=('1/2','1/2'))
        cls.d6=make_d6_arm(net,design,node='a',own=1,s=1)
        cls.denied=make_d6_arm(net,design,node='a',own=1,s=1,profile_admitted=False)

    def test_known_route_requirements_are_only_defined_for_real_routes(self):
        catalog=implemented_assumption_catalog_v27()
        self.assertEqual(public_catalog(),catalog)
        self.assertIs(public_handoff,inspect_verified_business_handoff_v27)
        self.assertFalse(catalog['universal_finite_catalog'])
        self.assertEqual(len(catalog['assumptions']),8)
        self.assertEqual(len(catalog['route_ids']),8)
        r2=requirements_for_route_v27('R2_MEAN_SIGNATURE')
        self.assertIn('mean_signature_sufficiency',r2['required_names'])
        self.assertNotIn('mean_signature_sufficiency',requirements_for_route_v27('R1A_RANDOMIZED_ARM')['required_names'])
        self.assertNotIn('full_vector_randomization',requirements_for_route_v27('R3_P_STANDARDIZED_EFFECTS')['required_names'])
        self.assertIn('full_vector_conditional_exchangeability',requirements_for_route_v27('R3_P_STANDARDIZED_EFFECTS')['required_names'])
        self.assertIn('first_stage_profile_no_direct_outcome_effect',
                      requirements_for_route_v27('R1A_RANDOMIZED_ARM',design_kind='two_stage_quota_mixture_binary_v2_7')['required_names'])
        with self.assertRaises(ValueError):requirements_for_route_v27('NEW_UNPROVED_THEOREM')
        with self.assertRaises(ValueError):requirements_for_route_v27('R3_FULL_ASSIGNMENT',design_kind='two_stage_quota_mixture_binary_v2_7')

    def test_all_eight_business_routes_replay_without_fictitious_estimator(self):
        fixtures=(self.fixtures.arm,self.fixtures.composition,self.fixtures.fixed,
                  self.fixtures.finite,self.fixtures.r2,self.fixtures.r3full,
                  self.fixtures.r3effects,self.fixtures.r3signature)
        self.assertEqual({x.route for x in fixtures},set(implemented_assumption_catalog_v27()['route_ids']))
        for out in fixtures:
            with self.subTest(route=out.route):
                r=inspect_verified_business_handoff_v27(out)
                self.assertTrue(r['theorem_replayed'])
                self.assertTrue(r['target_fingerprints'])
                self.assertEqual(r['identification']['status'],'POINT')
                self.assertEqual(r['estimation']['status'],'NO_ADAPTER')
                self.assertIsNone(r['estimation']['request'])
                self.assertIsNone(r['finite_sample_estimate'])
                self.assertIsNone(r['policy_value_estimate'])
                self.assertFalse(r['scientific_assumptions_verified_in_real_world'])
                if out.query_type in ('FIXED_POLICY','OBSERVATIONAL_POLICY','FINITE_POLICY_MIXTURE'):
                    self.assertEqual(r['policy']['status'],'IDENTIFIED_VALUE_FORMULA_ONLY')
                else:self.assertEqual(r['policy']['status'],'NOT_A_FIXED_POLICY_VALUE')

    def test_d6_A5_is_required_and_missing_A5_blocks_downstream(self):
        success=inspect_verified_business_handoff_v27(self.d6)
        self.assertIn('first_stage_profile_no_direct_outcome_effect',success['route_requirements']['required_names'])
        refused=inspect_verified_business_handoff_v27(self.denied)
        self.assertFalse(refused['theorem_replayed'])
        self.assertEqual(refused['estimation']['status'],'IDENTIFICATION_BLOCKED')
        self.assertIsNone(refused['estimation']['request'])
        self.assertEqual(refused['policy']['status'],'IDENTIFICATION_BLOCKED')

    def test_tampered_route_and_target_fingerprint_fail_closed(self):
        from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21
        with self.assertRaises(ValueError):
            inspect_verified_business_handoff_v27(replace(self.fixtures.fixed,route='R1A_RANDOMIZED_ARM'))
        corrupt=replace(self.fixtures.fixed.result,target_fingerprint='0'*64)
        with self.assertRaises(ValueError):
            inspect_verified_business_handoff_v27(replace(self.fixtures.fixed,result=corrupt))
        with self.assertRaises(TypeError):
            inspect_verified_business_handoff_v27({'status':'POINT'})


class V27PostReleaseCoverageAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            cls.report=main(Path(tmp))

    def test_reexecuted_48_and_live_d6_11_are_disjoint(self):
        r=self.report
        self.assertEqual(r['case_total'],59)
        self.assertEqual(r['breakdown_by_version'],{'v2.2':32,'v2.3':5,'v2.6':11,'v2.7':11})
        self.assertEqual(r['counts'],{'POINT':33,'NEEDS_INPUT':9,'BLOCKED_OR_TARGET_GAP':17})
        self.assertEqual(len({c['case_id'] for c in r['cards']}),59)
        d6=[x for x in r['cards'] if x['fixture_origin']=='v2.7']
        self.assertEqual(len(d6),11)
        self.assertEqual(sum(x['l2_identification']=='POINT' for x in d6),8)
        self.assertEqual(sum(x['l2_identification']=='NEEDS_INPUT' for x in d6),2)
        self.assertEqual(sum(x['l2_identification']=='UNSUPPORTED' for x in d6),1)
        self.assertFalse(any(x['numeric_business_value'] is not None for x in r['cards']))

    def test_preserve_original_b20_b24_and_scientific_scope(self):
        data=self.report
        self.assertIn('NOT an empirical real-world business coverage percentage',data['benchmark_scope'])
        self.assertTrue(all(x['original_case_point_upgraded'] is False for x in data['delta_audits']))
        self.assertIn('zero',data['delta_audits'][0]['interpretation'])
        self.assertIn('NEW symbolic A4',data['delta_audits'][1]['interpretation'])

    def test_deterministic_json_html_csv(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            main(Path(a));main(Path(b))
            for suffix in ('json','html','csv'):
                self.assertEqual((Path(a)/(STEM+'.'+suffix)).read_bytes(),
                                 (Path(b)/(STEM+'.'+suffix)).read_bytes())


if __name__=='__main__':unittest.main()
