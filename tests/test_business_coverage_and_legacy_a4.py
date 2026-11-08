"""v2.2: every historical business card plus fail-closed legacy network A4."""
from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from pfn_pipeline.identification_coverage import run_business_coverage_v22, CARD_TITLES
from pfn_pipeline.identification import identify, replay_population_identification
from pfn_pipeline._internal.identification.schemas import (
    IdentificationSpec, NetworkExposureSpec, ThresholdNetworkExposureSpec, QuerySpec,
)
from pfn_pipeline._internal.identification.identification import (
    IdentificationEngine, NetworkPolicyValueBernoulliBackend,
    NetworkDirectEffectThresholdPointBackend, legacy_network_a4_quarantine,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier
from pfn_pipeline.identification_coverage import _task_d1


class CoverageFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=run_business_coverage_v22()
        cls.lookup={x['case_id']:x for x in cls.data['cards']}

    def test_exact_32_source_cards(self):
        self.assertEqual(len(CARD_TITLES),32)
        self.assertEqual(len(self.lookup),32)
        self.assertEqual(set(self.lookup),{f'B{i:02d}' for i in range(1,33)})

    def test_live_point_never_implies_numeric_estimation(self):
        for x in self.lookup.values():
            if x['l2_identification'].startswith('POINT'):
                self.assertEqual(x['l3_estimation'], 'NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT')
                self.assertTrue(x['evidence_type'].startswith(('LIVE_THEOREM_REPLAY','LIVE_TOY_BATCH')),
                    x['case_id'])

    def test_archived_er300_not_labeled_recomputed(self):
        x=self.lookup['B04']
        self.assertEqual(x['l2_identification'],'POINT_TOY_LIVE_ER300_PREVIOUS_RELEASE')
        self.assertIn('not recomputed',x['evidence_note'])

    def test_sample_only_population_operator_does_not_pass_identification_a4(self):
        card=self.lookup['B32']
        self.assertEqual(card['l2_identification'],'NOT_CERTIFIED')
        self.assertEqual(card['observed_reason'],'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED')
        self.assertEqual(card['l3_estimation'],'NOT_APPLICABLE_NO_POINT')

    def test_no_id_theorem_claim_from_unimplemented_route(self):
        for x in self.lookup.values():
            if x['evidence_type'].endswith('CONTRACT_GAP') or x['evidence_type']=='CONTRACT_GAP':
                self.assertNotEqual(x['l2_identification'],'POINT_VERIFIED')

    def test_each_card_honors_original_expected_class(self):
        allowed={
            'POINT':{'POINT_VERIFIED'},
            'POINT_PREVIOUS_ER300':{'POINT_TOY_LIVE_ER300_PREVIOUS_RELEASE'},
            'POINT_FINITE_TOY_ONLY':{'POINT_VERIFIED'},
            'POINT_WITH_ESTIMATION_GAP':{'POINT_VERIFIED'},
            'NEEDS_INPUT':{'NEEDS_INPUT','NOT_CERTIFIED'},
            'RE_SPECIFY':{'RE_SPECIFY'},
            'NO_POINT_ROUTE':{'NOT_CERTIFIED','NO_REGISTERED_THEOREM'},
            'ROUTE_GAP':{'NO_REGISTERED_THEOREM'},
            'PROXY_ONLY':{'PROXY_NOT_POLICY'},
            'A4_SAMPLE_ONLY_BLOCKED':{'NOT_CERTIFIED'},
        }
        for case in self.lookup.values():
            with self.subTest(case=case['case_id']):
                self.assertIn(case['l2_identification'],allowed[case['expected_class']])
                for key in ('target_class','a4_required_information',
                            'a5_required_assumptions','a6_support_and_validity',
                            'existing_estimation_adapter'):
                    self.assertTrue(case[key],key)

    def test_point_and_nonpoint_consistency(self):
        positives={'B01','B02','B03','B04','B05','B06','B07','B08','B09','B10',
                   'B12','B14','B15','B16','B18','B28'}
        actual={x['case_id'] for x in self.lookup.values()
                if x['l2_identification'].startswith('POINT')}
        self.assertEqual(actual,positives)


def _make_case_test(i):
    def verify(self):
        card=self.lookup[f'B{i:02d}']
        self.assertTrue(card['business_question'])
        self.assertEqual(card['case_id'],f'B{i:02d}')
        self.assertTrue(card['l0_target'])
        self.assertTrue(card['l1_route'])
        self.assertTrue(card['l2_identification'])
        self.assertTrue(card['l3_estimation'])
        self.assertTrue(card['evidence_type'])
        self.assertTrue(card['evidence_note'])
        if card['l2_identification']=='POINT_VERIFIED':
            self.assertIsNotNone(card['observed_route'])
            self.assertIsNone(card['observed_reason'])
        elif card['l2_identification']=='NO_REGISTERED_THEOREM':
            self.assertIsNotNone(card['observed_reason'])
    verify.__name__=f'test_case_B{i:02d}_actual_route_or_explicit_gap'
    return verify

for i in range(1,33):
    setattr(CoverageFixtureTests,f'test_case_B{i:02d}_actual_route_or_explicit_gap',_make_case_test(i))


class LegacyNetworkA4QuarantineTests(unittest.TestCase):
    @staticmethod
    def _policy_spec():
        raw=copy.deepcopy(_task_d1().identification_spec)
        raw['randomized_network_arm_theorem_contract']=None
        raw['query']={'type':'POLICY_VALUE','treatment':'treatment',
           'outcome':'outcome','authority':'TRUSTED_FIXTURE','resolution':'RESOLVED',
           'target_population':'overall_population',
           'reference_exposure_definition':'treated_neighbor_count_1hop',
           'policy_description':'deterministic_binary_network_policy'}
        # Old A4 only has variables and no observed policy population operator.
        raw['information_signature']['objects'][0].pop('randomized_arm_observable',None)
        raw['information_signature']['objects'][0]['variables']=[
            'context','treatment','neighbor_treatment_count','outcome']
        return IdentificationSpec.model_validate(raw)

    @staticmethod
    def _direct_spec():
        raw=copy.deepcopy(_task_d1().identification_spec)
        raw['randomized_network_arm_theorem_contract']=None
        raw['interference_structure_receipt']=None
        raw['network_exposure']={
            'network_id':'legacy-direct-three','node_ids':['0','1','2'],
            'undirected_edges':[('0','1'),('0','2')],
            'exposure_mapping':'treated_neighbor_share_threshold_1hop',
            'threshold':0.5,'fixed_network':True}
        raw['query']={'type':'DIRECT_EFFECT','treatment':'treatment','outcome':'outcome',
           'authority':'TRUSTED_FIXTURE','resolution':'RESOLVED',
           'reference_exposure_definition':'treated_neighbor_share_threshold_1hop',
           'target_exposure_semantics':'true_sufficient_exposure_state','exposure_value':1}
        raw['information_signature']['objects'][0].pop('randomized_arm_observable',None)
        raw['information_signature']['objects'][0]['regime']='observational'
        raw['information_signature']['objects'][0]['variables']=[
            'context','treatment','neighbor_threshold_exposure','outcome']
        return IdentificationSpec.model_validate(raw)

    def test_old_network_policy_variable_only_is_quarantined(self):
        spec=self._policy_spec()
        self.assertEqual(legacy_network_a4_quarantine(spec).reason_code,'LEGACY_NETWORK_A4_UNVERIFIED')
        self.assertFalse(NetworkPolicyValueBernoulliBackend().supports(spec))
        raw=NetworkPolicyValueBernoulliBackend().solve(spec)
        self.assertEqual((raw.status,raw.reason_code),('UNSUPPORTED','LEGACY_NETWORK_A4_UNVERIFIED'))
        self.assertEqual(IdentificationEngine().solve_verified(spec,IdentificationVerifier()).reason_code,
                         'LEGACY_NETWORK_A4_UNVERIFIED')

    def test_old_observational_threshold_variable_only_is_quarantined(self):
        spec=self._direct_spec()
        self.assertIsInstance(spec.network_exposure,ThresholdNetworkExposureSpec)
        self.assertFalse(NetworkDirectEffectThresholdPointBackend().supports(spec))
        self.assertEqual(NetworkDirectEffectThresholdPointBackend().solve(spec).reason_code,
                         'LEGACY_NETWORK_A4_UNVERIFIED')
        self.assertEqual(IdentificationEngine().solve_verified(spec,IdentificationVerifier()).reason_code,
                         'LEGACY_NETWORK_A4_UNVERIFIED')

    def test_retired_historical_solvers_are_not_directly_callable(self):
        for backend,spec in ((NetworkPolicyValueBernoulliBackend(),self._policy_spec()),
                             (NetworkDirectEffectThresholdPointBackend(),self._direct_spec())):
            with self.subTest(backend=backend.name):
                with self.assertRaisesRegex(RuntimeError,'LEGACY_NETWORK_A4_UNVERIFIED'):
                    backend.historical_supports_not_executable(spec)
                with self.assertRaisesRegex(RuntimeError,'LEGACY_NETWORK_A4_UNVERIFIED'):
                    backend.historical_solve_not_executable(spec)

    def test_quarantine_does_not_block_modern_randomized_arm(self):
        task=_task_d1()
        actual=identify(task)
        self.assertEqual((actual.status,actual.verification_status),('POINT','VERIFIED'))
        self.assertIsNone(legacy_network_a4_quarantine(IdentificationSpec.model_validate(task.identification_spec)))
        replay_population_identification(actual)

    def test_archived_point_receipts_cannot_replay_under_old_rule_ids(self):
        task=_task_d1()
        spec=IdentificationSpec.model_validate(task.identification_spec)
        raw=copy.deepcopy(identify(task).result)
        for rule in ('NETWORK_POLICY_VALUE_BERNOULLI_V1',
                     'NETWORK_DIRECT_EFFECT_THRESHOLD_POINT_V2'):
            forged=copy.deepcopy(raw)
            forged['certificate']['rule_id']=rule
            from pfn_pipeline._internal.identification.schemas import IdentificationResult
            checked=IdentificationVerifier().verify(spec,IdentificationResult.model_validate(forged))
            self.assertNotEqual(checked.verification_status,'VERIFIED')


if __name__=='__main__':unittest.main()
