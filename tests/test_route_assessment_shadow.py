"""Opt-in A1/A4 -> A5/A6 -> family-route shadow contract checks."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import copy
import unittest

from pfn_pipeline import make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_route_shadow import (
    ARM_FAMILY, FIXED_POLICY_CANDIDATE, family_catalog,
    TargetSemanticsV15, arm_target_from_task, fixed_policy_target_from_study,
    assess_family_route, replay_family_route,
)


def net():
    return NetworkExposureSpec(network_id='route-shadow-star-5', node_ids=['0','1','2','3','4'],
                               undirected_edges=[('0','1'),('0','2'),('0','3'),('0','4')])


def task(design='D1', a=1, s=0, exposure='strict_majority'):
    kw=dict(node_id='0',own_treatment_value=a,exposure_value=s,
            exposure_definition=exposure,
            source='route-shadow reviewed experimental design protocol',
            evidence='known full-vector randomization is a certified experimental design assumption',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
    if design=='D1':
        return make_heterogeneous_bernoulli_arm_task(
            net(),propensities={n:'1/2' for n in net().node_ids},**kw)
    if design=='D2':
        return make_complete_randomization_arm_task(net(),m=2,**kw)
    if design=='D2Q4':
        return make_complete_randomization_arm_task(net(),m=4,**kw)
    raise ValueError(design)


def src(t,operator='NODE_ARM_MEANS',*,source_id='source:default',admission='ADMITTED',
        availability='SYMBOLIC_POPULATION_OPERATOR',regime='experimental',assignment_cells=()):
    q=t.identification_spec['query']
    return declare_a4_source(
        t,source_id=source_id,operator=operator,
        provenance='explicit reviewed population-information statement',
        admission=admission,availability=availability,
        regime=regime,node_order=t.node_ids,outcome_nodes=t.node_ids,
        arm_cells=((q['target_node_id'],q['own_treatment_value'],q['exposure_value']),)
                     if operator=='NODE_ARM_MEANS' else (),
        assignment_cells=assignment_cells)


class RouteShadowV15Tests(unittest.TestCase):
    def assess_arm(self,t=None,items=None,**kwargs):
        t=t or task()
        q=arm_target_from_task(t)
        r=assess_family_route(t,q,tuple(items or (src(t),)),family_id=ARM_FAMILY)
        return t,q,r

    def assess_policy(self,t=None,items=None,z=(0,0,0,0,0),**kwargs):
        t=t or task()
        q=fixed_policy_target_from_study(t,z,authority=kwargs.get('authority','TRUSTED_FIXTURE'))
        r=assess_family_route(t,q,tuple(items or (src(t,'ASSIGNMENT_NODE_MEANS',
                                        assignment_cells=(z,)),)),family_id=FIXED_POLICY_CANDIDATE)
        return t,q,r

    def test_catalog_makes_registered_vs_candidate_explicit(self):
        a,b=family_catalog()
        self.assertTrue(a.executable_in_existing_engine)
        self.assertFalse(b.executable_in_existing_engine)
        self.assertNotEqual(a.information_requirement,b.information_requirement)

    def test_existing_arm_ready_and_replay(self):
        t,q,r=self.assess_arm()
        self.assertEqual(r.route_status,'CANDIDATE_READY')
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.current_legacy_status,'POINT')
        self.assertIsNone(r.mathematical_identification_from_router)
        self.assertTrue(replay_family_route(t,q,(src(t),),r))

    def test_strong_info_old_a4_gate_disagrees(self):
        t=task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0].update(
            name='P(T_vector,Y_vector|W)',variables=['treatment','outcome','context'],
            basis='WHOLE_NETWORK_ASSIGNMENT_LAW_V1',
            joint_scope='whole_network_assignment',outcome_representation='full_joint_law',
            whole_network_assignment_law_available=True)
        t=replace(t,identification_spec=raw)
        _,_,r=self.assess_arm(t,[src(t,'FULL_JOINT_LAW')])
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.route_status,'LEGACY_GATE_DISAGREEMENT')
        self.assertEqual(r.current_legacy_reason,'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED')

    def test_weak_info_old_point_but_route_blocks(self):
        t=task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0].update(
            joint_scope='node_local_marginals_only',whole_network_assignment_law_available=False)
        t=replace(t,identification_spec=raw)
        _,_,r=self.assess_arm(t,[src(t,'PAIRWISE_MARGINALS')])
        self.assertEqual(r.information_status,'INFORMATION_BLOCKED')
        self.assertEqual(r.current_legacy_status,'UNSUPPORTED')
        self.assertEqual(r.mathematical_identification_from_router,None)

    def test_fixed_policy_assignment_info_satisfied_no_backend(self):
        t,q,r=self.assess_policy()
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')
        self.assertEqual(r.backend_capability,'CANDIDATE_NOT_REGISTERED')
        self.assertTrue(replay_family_route(t,q,(src(t,'ASSIGNMENT_NODE_MEANS',
                                                       assignment_cells=((0,0,0,0,0),)),),r))

    def test_same_Q_arm_only_information_blocked(self):
        t,q,r=self.assess_policy()
        alternate=assess_family_route(t,q,(src(t),),family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(q.target_digest,alternate.target_digest)
        self.assertEqual(alternate.route_status,'INFORMATION_BLOCKED')
        self.assertEqual(alternate.backend_capability,'CANDIDATE_NOT_REGISTERED')
        self.assertEqual(alternate.information_status,'INSUFFICIENT')

    def test_full_joint_can_satisfy_fixed_policy_observable(self):
        t,q,r=self.assess_policy(items=(src(task(),'FULL_JOINT_LAW'),))
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')

    def test_off_support_policy_Q_still_defined(self):
        t=task('D2Q4',a=1,s=1)
        q=fixed_policy_target_from_study(t,(1,1,1,1,1),authority='TRUSTED_FIXTURE')
        r=assess_family_route(t,q,(src(t,'FULL_JOINT_LAW'),),family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(r.route_status,'OFF_SUPPORT_ALTERNATE_THEOREM')
        self.assertEqual(r.validity_status,'OFF_SUPPORT')
        self.assertEqual(r.target_match,'MATCHED')
        self.assertNotEqual(r.route_status,'TARGET_UNDEFINED')

    def test_zero_support_arm_not_partial(self):
        t=task('D2',a=1,s=1)
        _,_,r=self.assess_arm(t,[src(t)])
        self.assertEqual(r.route_status,'TARGET_UNDEFINED')
        self.assertEqual(r.validity_status,'UNDEFINED')

    def test_unadmitted_source_without_other_source(self):
        t,q,r=self.assess_arm(items=(src(task(),admission='UNRESOLVED'),))
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.information_status,'NEEDS_INPUT')

    def test_finite_sample_source_blocked(self):
        t=task(); _,_,r=self.assess_arm(t,[src(t,availability='FINITE_SAMPLE_ESTIMATE')])
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_duplicate_source_id_conflict(self):
        t=task(); good=src(t); bad=src(t,'PAIRWISE_MARGINALS')
        q=arm_target_from_task(t)
        r=assess_family_route(t,q,(good,bad),family_id=ARM_FAMILY)
        self.assertEqual(r.route_status,'SOURCE_CONFLICT')

    def test_distinct_sources_not_presumed_conflicting(self):
        t=task(); good=src(t,source_id='r1'); weaker=src(t,'PAIRWISE_MARGINALS',source_id='r2')
        _,_,r=self.assess_arm(t,(good,weaker))
        self.assertEqual(r.route_status,'CANDIDATE_READY')
        self.assertEqual(r.information_status,'SATISFIED')

    def test_missing_source_needs_input(self):
        t=task(); q=arm_target_from_task(t)
        r=assess_family_route(t,q,(),family_id=ARM_FAMILY)
        self.assertEqual(r.route_status,'NEEDS_INPUT')

    def test_q_g_and_node_order_source_binding(self):
        t=task(); source=src(t)
        for bad in (replace(source,node_order=tuple(reversed(t.node_ids))),
                    replace(source,assignment_law_fingerprint='wrong'),
                    replace(source,exposure_fingerprint='wrong')):
            _,_,r=self.assess_arm(t,(bad,))
            self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_unconfirmed_target_blocked(self):
        t=task()
        q=replace(arm_target_from_task(t),authority='PROPOSED',target_digest='')
        r=assess_family_route(t,q,(src(t),),family_id=ARM_FAMILY)
        self.assertEqual(r.route_status,'NEEDS_INPUT')

    def test_changing_arm_cannot_reuse_target(self):
        t=task(); q=arm_target_from_task(t)
        changed=replace(q,arm=(0,0),target_digest='')
        r=assess_family_route(t,changed,(src(t),),family_id=ARM_FAMILY)
        self.assertEqual(r.route_status,'SPECIFICATION_CONFLICT')

    def test_arm_target_different_design_identity(self):
        self.assertNotEqual(arm_target_from_task(task('D1')).target_digest,
                            arm_target_from_task(task('D2')).target_digest)

    def test_fixed_policy_target_independent_of_design_and_g(self):
        p1=fixed_policy_target_from_study(task('D1'),(0,0,0,0,0),authority='TRUSTED_FIXTURE')
        p2=fixed_policy_target_from_study(task('D2'),(0,0,0,0,0),authority='TRUSTED_FIXTURE')
        self.assertEqual(p1.target_digest,p2.target_digest)
        p3=fixed_policy_target_from_study(task('D1',exposure='three_level_treated_neighbor_fraction'),
                                          (0,0,0,0,0),authority='TRUSTED_FIXTURE')
        self.assertEqual(p1.target_digest,p3.target_digest)

    def test_target_digest_does_not_include_authority_or_resolution(self):
        t=task()
        original=arm_target_from_task(t)
        alternative=replace(original, authority='PROPOSED', query_resolution='UNRESOLVED',
                            target_digest='')
        self.assertEqual(original.target_digest, alternative.target_digest)
        self.assertNotEqual(original.authority, alternative.authority)
        p=fixed_policy_target_from_study(t,(0,0,0,0,0),authority='TRUSTED_FIXTURE')
        p2=replace(p,authority='PROPOSED',target_digest='')
        self.assertEqual(p.target_digest,p2.target_digest)

    def test_typed_required_observable_is_family_specific(self):
        t,_,a=self.assess_arm()
        self.assertEqual(a.required_observable.operator,'NODE_ARM_CONDITIONAL_MEAN')
        self.assertEqual(a.required_observable.arm_cell,('0',1,0))
        _,p,b=self.assess_policy(t)
        self.assertEqual(b.required_observable.operator,'NODE_ASSIGNMENT_MEANS_FOR_POLICY')
        self.assertEqual(b.required_observable.node_ids,t.node_ids)
        self.assertIsNone(b.required_observable.exposure_fingerprint)

    def test_unreviewed_policy_cannot_pass_router(self):
        t=task(); p=fixed_policy_target_from_study(t,(0,0,0,0,0),authority='PROPOSED')
        r=assess_family_route(t,p,(src(t,'ASSIGNMENT_NODE_MEANS',assignment_cells=((0,0,0,0,0),)),),
                              family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.target_match,'UNCONFIRMED')

    def test_wrong_family_rejected_not_rerouted(self):
        t=task(); q=arm_target_from_task(t)
        r=assess_family_route(t,q,(src(t),),family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(r.route_status,'FAMILY_NOT_APPLICABLE')

    def test_unconfirmed_assumption_needs_input(self):
        t=task(); raw=copy.deepcopy(t.identification_spec)
        for a in raw['assumptions']:
            if a['name']=='full_vector_randomization':
                a.update(confirmed=False,status='UNRESOLVED',source='unresolved_input')
        changed=replace(t,identification_spec=raw)
        _,_,r=self.assess_arm(changed,(src(changed),))
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.assumption_status,'NEEDS_INPUT')

    def test_not_admitted_assumption_does_not_become_partial(self):
        t=task(); raw=copy.deepcopy(t.identification_spec)
        for a in raw['assumptions']:
            if a['name']=='full_vector_randomization':
                a.update(confirmed=False,status='NOT_ADMITTED')
        changed=replace(t,identification_spec=raw)
        _,_,r=self.assess_arm(changed,(src(changed),))
        self.assertEqual(r.route_status,'ASSUMPTIONS_NOT_ADMITTED')

    def test_source_tampering_replay_fails(self):
        t,q,r=self.assess_arm()
        with self.assertRaises(ValueError):
            replay_family_route(t,q,(replace(src(t),provenance='different source evidence'),),r)
        with self.assertRaises(ValueError):
            replay_family_route(t,q,(src(t),),replace(r,route_status='CANDIDATE_READY',digest='fake'))

    def test_review_authority_is_separate_from_Q_but_bound_to_receipt(self):
        t=task(); source=src(t)
        a=arm_target_from_task(t)
        result=assess_family_route(t,a,(source,),family_id=ARM_FAMILY)
        b=replace(a,authority='HUMAN_CONFIRMED',target_digest='')
        self.assertEqual(a.target_digest,b.target_digest)
        changed=assess_family_route(t,b,(source,),family_id=ARM_FAMILY)
        # Arm query remains tied to original trusted TaskSpec contract, hence
        # route refuses silent edits even if scientific target identity same.
        self.assertEqual(changed.route_status,'SPECIFICATION_CONFLICT')
        with self.assertRaises(ValueError):
            replay_family_route(t,b,(source,),result)

    def test_no_implicit_unknown_family(self):
        t=task()
        with self.assertRaises(ValueError):
            assess_family_route(t,arm_target_from_task(t),(src(t),),family_id='backdoor_ate')

    def test_policy_partial_nodes_blocked(self):
        t=task(); q=fixed_policy_target_from_study(t,(0,0,0,0,0),authority='TRUSTED_FIXTURE')
        partial=declare_a4_source(t,source_id='partial',operator='ASSIGNMENT_NODE_MEANS',
                    provenance='reviewed source',admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
                    outcome_nodes=('0',),node_order=t.node_ids,assignment_cells=((0,0,0,0,0),))
        r=assess_family_route(t,q,(partial,),family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_policy_conditional_zero_q_refuses_even_with_full_law(self):
        t=task('D2Q4'); q=fixed_policy_target_from_study(t,(0,0,0,0,0),authority='TRUSTED_FIXTURE')
        r=assess_family_route(t,q,(src(t,'FULL_JOINT_LAW'),),family_id=FIXED_POLICY_CANDIDATE)
        self.assertEqual(r.route_status,'OFF_SUPPORT_ALTERNATE_THEOREM')

    def test_observational_information_can_be_available_without_a5_license(self):
        # A4 can deliver observed associations in observational data; the
        # existence of the law by itself never grants causal randomization.
        t=task(); o=src(t,'FULL_JOINT_LAW',regime='observational')
        _,_,r=self.assess_arm(t,(o,))
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertIsNone(r.mathematical_identification_from_router)


if __name__=='__main__':
    unittest.main()
