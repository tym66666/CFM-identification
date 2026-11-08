"""Regression tests for opt-in, non-authoritative A4 shadow integration.

No PFN, no 2**300 enumeration, and no changes to legacy identification.
"""
from __future__ import annotations

from dataclasses import replace
import copy
import unittest
from fractions import Fraction

from pfn_pipeline import (
    identify, make_heterogeneous_bernoulli_arm_task,
    make_complete_randomization_arm_task, make_two_group_quota_arm_task,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification_a4_shadow import (
    declare_a4_source, verified_arm_support, replay_verified_arm_support,
    assess_a4_shadow, replay_a4_shadow,
)


def network():
    return NetworkExposureSpec(network_id='A4:star5',
        node_ids=['0','1','2','3','4'],
        undirected_edges=[('0', '1'), ('0', '2'), ('0', '3'), ('0', '4')])


def task(design='D1', exposure='strict_majority', a=1, s=0, node='0'):
    kw=dict(node_id=node, own_treatment_value=a, exposure_value=s,
            source='signed experimental protocol: integration fixture',
            evidence='explicit reviewed randomization; not inferred from outcomes',
            admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE',
            exposure_definition=exposure)
    if exposure == 'pretreatment_core_collaborator_majority':
        kw['core_collaborators'] = {'0':('1','2'), '1':('0',), '2':('0',),
                                   '3':('0',), '4':('0',)}
    n=network()
    if design=='D1':
        return make_heterogeneous_bernoulli_arm_task(n, propensities={i:'1/2' for i in n.node_ids},**kw)
    if design=='D2':
        return make_complete_randomization_arm_task(n,m=2,**kw)
    if design=='D3':
        return make_two_group_quota_arm_task(n,groups=(('0','1','2'),('3','4')),
                                               treated_quotas=(1,1),**kw)
    raise ValueError(design)


def source(t, operator='NODE_ARM_MEANS', admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
           outcome_nodes=None, node_order=None, arm_cells=None, assignment_cells=(), regime='experimental'):
    q=t.identification_spec['query']
    if operator == 'NODE_ARM_MEANS' and arm_cells is None:
        arm_cells=((q['target_node_id'], q['own_treatment_value'], q['exposure_value']),)
    return declare_a4_source(t, source_id='documented:' + operator,
        operator=operator, provenance='reviewed population operator; not from sample statistics',
        admission=admission, availability=availability,
        outcome_nodes=tuple(t.node_ids if outcome_nodes is None else outcome_nodes),
        node_order=tuple(t.node_ids if node_order is None else node_order),
        arm_cells=() if arm_cells is None else arm_cells,
        assignment_cells=assignment_cells,regime=regime)


class A4ShadowIntegration(unittest.TestCase):
    def test_baseline_direct_true_point_and_replay(self):
        t=task()
        observed=source(t)
        out=assess_a4_shadow(t,observed)
        self.assertEqual(out.legacy_identification.status,'POINT')
        self.assertEqual(out.legacy_identification.verification_status,'VERIFIED')
        self.assertEqual(out.receipt.information_status,'SATISFIED')
        self.assertEqual(out.receipt.rule_id,'A4_DIRECT_NODE_ARM_V1')
        self.assertEqual(out.difference,'AGREE_A4_READY')
        self.assertTrue(replay_a4_shadow(t,observed,out))
        self.assertIsNone(out.mathematical_status_of_shadow)

    def test_weak_local_info_old_false_positive(self):
        t=task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0].update(
            joint_scope='node_local_marginals_only',
            whole_network_assignment_law_available=False,
            outcome_representation=None,
            description='Only P(T,Y) and P(S,Y), no joint node arm means')
        changed=replace(t,identification_spec=raw)
        result=assess_a4_shadow(changed,source(changed,'PAIRWISE_MARGINALS'))
        self.assertEqual(result.legacy_identification.status,'UNSUPPORTED')
        self.assertEqual(result.legacy_identification.result['reason_code'],'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED')
        self.assertEqual(result.receipt.information_status,'BLOCKED')
        self.assertEqual(result.receipt.reason,'OPERATOR_NOT_ENTAILED')
        self.assertEqual(result.difference,'NO_A4_GATE_CONCLUSION')
        self.assertTrue(replay_a4_shadow(changed,source(changed,'PAIRWISE_MARGINALS'),result))

    def test_strong_full_joint_old_false_negative(self):
        t=task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0].update(
            name='P(T_vector,Y_vector|W)',
            variables=['treatment','outcome','context'],
            basis='WHOLE_NETWORK_ASSIGNMENT_LAW_V1',
            joint_scope='whole_network_assignment',
            whole_network_assignment_law_available=True,
            outcome_representation='full_joint_law')
        changed=replace(t,identification_spec=raw)
        result=assess_a4_shadow(changed,source(changed,'FULL_JOINT_LAW'))
        self.assertEqual(result.legacy_identification.result['reason_code'],
                         'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED')
        self.assertEqual(result.receipt.information_status,'SATISFIED')
        self.assertEqual(result.receipt.rule_id,'A4_FULL_JOINT_TO_ARM_V1')
        self.assertEqual(result.difference,'LEGACY_A4_TOO_RESTRICTIVE')
        self.assertTrue(replay_a4_shadow(changed,source(changed,'FULL_JOINT_LAW'),result))
        # An A4 receipt must NOT upgrade the original to POINT.
        self.assertNotEqual(result.legacy_identification.status,'POINT')

    def test_node_full_law_is_derived(self):
        t=task(); out=assess_a4_shadow(t,source(t,'NODE_FULL_LAW',outcome_nodes=('0',)))
        self.assertEqual(out.receipt.information_status,'SATISFIED')
        self.assertEqual(out.receipt.rule_id,'A4_NODE_FULL_LAW_TO_ARM_V1')

    def test_full_joint_requires_all_outcome_nodes(self):
        t=task(); out=assess_a4_shadow(t,source(t,'FULL_JOINT_LAW',outcome_nodes=('0',)))
        self.assertEqual(out.receipt.reason,'FULL_JOINT_REQUIRES_ALL_NODE_OUTCOMES')

    def test_partial_assignment_means_not_safely_extrapolated(self):
        t=task(); out=assess_a4_shadow(t,source(t,'ASSIGNMENT_NODE_MEANS',assignment_cells=((1,1,0,0,0),)))
        self.assertEqual(out.receipt.information_status,'RULE_NOT_IMPLEMENTED')
        self.assertNotEqual(out.receipt.information_status,'SATISFIED')

    def test_finite_sample_declared_does_not_meet_population_requirement(self):
        t=task(); out=assess_a4_shadow(t,source(t,availability='FINITE_SAMPLE_ESTIMATE'))
        self.assertEqual(out.receipt.reason,'FINITE_SAMPLE_IS_NOT_POPULATION_OPERATOR')

    def test_unresolved_source_is_not_promoted(self):
        t=task(); out=assess_a4_shadow(t,source(t,admission='PROPOSED'))
        self.assertEqual(out.receipt.information_status,'UNRESOLVED')

    def test_context_and_order_mismatch_block(self):
        t=task(); s=source(t)
        self.assertEqual(assess_a4_shadow(t,replace(s,node_order=tuple(reversed(t.node_ids)))).receipt.reason,
                         'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')
        self.assertEqual(assess_a4_shadow(t,replace(s,context='W:other')).receipt.reason,
                         'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')

    def test_design_exposure_spec_digest_mismatch_block(self):
        t=task(); s=source(t)
        self.assertEqual(assess_a4_shadow(t,replace(s,assignment_law_fingerprint='incorrect')).receipt.reason,
                         'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')
        self.assertEqual(assess_a4_shadow(t,replace(s,exposure_fingerprint='incorrect')).receipt.reason,
                         'SOURCE_EXPOSURE_MISMATCH')

    def test_replay_rejects_tampered_support_and_receipt(self):
        t=task(); s=source(t); a=assess_a4_shadow(t,s)
        self.assertTrue(replay_verified_arm_support(t,a.support))
        with self.assertRaises(ValueError):
            replay_verified_arm_support(t,replace(a.support,support='1/7'))
        with self.assertRaises(ValueError):
            replay_a4_shadow(t,s,replace(a,receipt=replace(a.receipt,information_status='SATISFIED',rule_id='FAKE')))

    def test_source_changes_replay_fails(self):
        t=task(); s=source(t); a=assess_a4_shadow(t,s)
        with self.assertRaises(ValueError):
            replay_a4_shadow(t,replace(s,provenance='changed declaration'),a)

    def test_same_source_new_task_never_reuses_support(self):
        a=task(design='D1'); b=task(design='D2')
        x=assess_a4_shadow(b,source(a))
        self.assertEqual(x.receipt.reason,'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')
        c=task(exposure='three_level_treated_neighbor_fraction')
        self.assertEqual(assess_a4_shadow(c,source(a)).receipt.reason,
                         'SOURCE_SCOPE_OR_LAW_OR_NODE_ORDER_MISMATCH')

    def test_numerical_support_reuses_exact_backend(self):
        t=task('D2', a=1,s=0)
        ev=verified_arm_support(t)
        self.assertEqual(ev.support,'2/5')
        self.assertTrue(replay_verified_arm_support(t,ev))
        self.assertNotIn('ENUMERATE',ev.independent_verifier_rule)

    def test_zero_arm_support_preserved(self):
        t=task('D2',a=1,s=1)
        ev=verified_arm_support(t)
        self.assertEqual(ev.support,'0')
        o=assess_a4_shadow(t,source(t))
        self.assertEqual(o.receipt.information_status,'TARGET_UNDEFINED')
        self.assertEqual(o.receipt.reason,'ZERO_ARM_SUPPORT')

    def test_all_nine_design_exposure_combinations(self):
        for design in ('D1','D2','D3'):
            for exposure in ('strict_majority','three_level_treated_neighbor_fraction',
                             'pretreatment_core_collaborator_majority'):
                with self.subTest(design=design,exposure=exposure):
                    t=task(design,exposure,a=0,s=(1 if exposure=='three_level_treated_neighbor_fraction' and design in ('D2','D3') else 0))
                    proof=verified_arm_support(t)
                    self.assertTrue(replay_verified_arm_support(t,proof))
                    result=assess_a4_shadow(t,source(t))
                    self.assertEqual(result.receipt.information_status,'SATISFIED')

    def test_observational_A4_entailment_not_a_randomization_license(self):
        t=task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0]['regime']='observational'
        changed=replace(t,identification_spec=raw)
        sc=source(changed,operator='NODE_FULL_LAW',outcome_nodes=('0',),regime='observational')
        a=assess_a4_shadow(changed,sc)
        self.assertEqual(a.receipt.information_status,'SATISFIED')
        self.assertNotEqual(a.legacy_identification.status,'POINT')
        self.assertIsNone(a.mathematical_status_of_shadow)

    def test_bad_cell_or_assignment_declaration_rejected(self):
        t=task()
        with self.assertRaises(ValueError):
            source(t,operator='NODE_ARM_MEANS',arm_cells=(('0',1,-1),))
        with self.assertRaises(ValueError):
            source(t,operator='ASSIGNMENT_NODE_MEANS',assignment_cells=((1,0),))
        with self.assertRaises(ValueError):
            source(t,operator='ASSIGNMENT_NODE_MEANS',assignment_cells=((1,1,0,1,2),))

    def test_shadow_leaves_original_theorem_untouched(self):
        t=task()
        before=identify(t)
        _=assess_a4_shadow(t,source(t,operator='FULL_JOINT_LAW'))
        after=identify(t)
        self.assertEqual(before.result,after.result)
        self.assertEqual(before.diagnostics,after.diagnostics)
        self.assertEqual(before.estimation_request,after.estimation_request)

    def test_replay_rejects_clone_of_original_task(self):
        t=task(); s=source(t); a=assess_a4_shadow(t,s)
        with self.assertRaises(ValueError):
            replay_a4_shadow(replace(t),s,a)


if __name__ == '__main__':
    unittest.main()
