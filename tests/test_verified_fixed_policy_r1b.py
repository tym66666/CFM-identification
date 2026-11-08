"""R1b v1.9 theorem/route/verifier tests; independent small-network oracle.

Tests identify the *population functional*, not an estimated policy value.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline.identification_policy_r1b import (
    R1bPolicyUnavailable, identify_verified_fixed_policy,
    replay_verified_fixed_policy, _independent_q,
)
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, declare_network_a4_source, fixed_policy_target_from_context,
)
from pfn_pipeline.identification_route_shadow import FIXED_POLICY_CANDIDATE
from pfn_pipeline.network_inquiry_shadow import assess_nonarm_network_inquiry

NODES=('a','b','c','d')
EDGES=(('a','b'),('a','c'),('b','d'))
SUPPORTED=(1,0,1,0)


def make_study(kind='D1',*,regime='experimental',nodes=NODES,graph='DECLARED_PRETREATMENT_FIXED',
               treatment='T', context='W:business'):
    designs={
        'D1': {'kind':'heterogeneous_bernoulli_binary_v1',
               'propensities':{n: p for n,p in zip(nodes,('1/3','1/2','2/3','1/4'))}},
        'D2': {'kind':'complete_randomization_binary_v1','m':2},
        'D3': {'kind':'two_group_fixed_quota_binary_v1',
               'groups':[list(nodes[:2]),list(nodes[2:])],
               'treated_quotas':[1,1]},
    }
    return declare_network_study(
        network_id='policy-toy4',node_order=nodes,undirected_edges=EDGES,
        treatment_variable=treatment,outcome_variable='sales',outcome_kind='continuous',
        context_reference=context,observation_regime=regime,
        assignment_design=designs[kind] if regime=='experimental' else None,
        protocol_provenance='synthetic reviewed study design',network_provenance='fixed toy network',
        graph_timing_claim=graph)


def assumptions(*, omitted=(), proposed=()):
    names=('known_assignment_law','full_vector_randomization','consistency',
           'fixed_pretreatment_network','finite_conditional_first_moments')
    return tuple(Assumption(name=n,source='demo_specification',
              confirmed=n not in proposed,
              evidence=['reviewed synthetic assumptions'])
              for n in names if n not in omitted)


def a4(study,kind='ASSIGNMENT_NODE_MEANS',*, z=SUPPORTED,nodes=None,
       availability='SYMBOLIC_POPULATION_OPERATOR',admission='ADMITTED',source_id='A4-reviewed'):
    return declare_network_a4_source(
        study, source_id=source_id,operator=kind,
        provenance='explicit population operator for synthetic test',
        admission=admission,availability=availability,
        outcome_nodes=study.node_order if nodes is None else nodes,
        assignment_cells=(z,) if kind=='ASSIGNMENT_NODE_MEANS' else (),
        exposure_fingerprint='unrelated-exposure' if kind=='NODE_ARM_MEANS' else None)


def target(study,z=SUPPORTED,weights=None,authority='TRUSTED_FIXTURE'):
    return fixed_policy_target_from_context(study,tuple(z),authority=authority,
            unit_weights=tuple(weights) if weights else None)


def solve(kind='D1',**kw):
    st=make_study(kind)
    tgt=target(st,**kw)
    src=a4(st,z=tgt.policy_assignment)
    return identify_verified_fixed_policy(st,tgt,(src,),assumptions=assumptions())


def independent_potential_outcome(node_index,z):
    """Depends on distant treatments, so does NOT assume exposure sufficiency."""
    return (Fraction(3*node_index+2*sum(z)+z[node_index], 7)
            + Fraction(11*z[(node_index+2)%len(z)] + 5*z[0]*z[3], 13))


def oracle_policy(st,z,weights):
    return sum(Fraction(w)*independent_potential_outcome(j,z)
               for j,w in enumerate(weights))


def oracle_conditional_observable(st,z,weights):
    engine=AssignmentSpec(st.design())
    denominator=Fraction(0); numerator=Fraction(0)
    for assignment in product((0,1),repeat=len(st.node_order)):
        q=engine.full_assignment_probability(st.network(),dict(zip(st.node_order,assignment)))
        if assignment==z:
            denominator+=q
            numerator+=q*oracle_policy(st,z,weights)
    if not denominator: return None
    return numerator/denominator


class R1bPolicyPoint(unittest.TestCase):
    def test_all_designs_point_and_independent_oracle(self):
        for kind in ('D1','D2','D3'):
            with self.subTest(design=kind):
                r=solve(kind)
                self.assertEqual((r.status,r.verification_status),('POINT','VERIFIED'))
                self.assertEqual(Fraction(r.assignment_probability),
                    _independent_q(r.study,r.target.policy_assignment))
                self.assertEqual(Fraction(r.assignment_probability),
                    AssignmentSpec(r.study.design()).full_assignment_probability(
                        r.study.network(),dict(zip(r.study.node_order,r.target.policy_assignment))))
                self.assertEqual(oracle_conditional_observable(r.study,SUPPORTED,
                                 r.target.unit_weights),oracle_policy(r.study,SUPPORTED,
                                 r.target.unit_weights))
                self.assertTrue(replay_verified_fixed_policy(r))
                self.assertIsNone(r.estimation_request)
                self.assertNotIn('estimated_value',r.summary())

    def test_exact_probabilities_three_designs(self):
        self.assertEqual(Fraction(solve('D1').assignment_probability), Fraction(1,12))
        self.assertEqual(Fraction(solve('D2').assignment_probability), Fraction(1,6))
        self.assertEqual(Fraction(solve('D3').assignment_probability), Fraction(1,4))

    def test_weights_are_exact_and_zero_weight_nodes_not_required(self):
        st=make_study();tg=target(st,weights=('2/3','0','1/3','0'))
        src=a4(st,nodes=('a','c'))
        result=identify_verified_fixed_policy(st,tg,(src,),assumptions=assumptions())
        self.assertEqual(result.weighted_nodes,('a','c'))
        self.assertEqual(result.node_weights,('2/3','1/3'))
        self.assertEqual(len(result.required_observables),2)
        self.assertEqual(oracle_policy(st,SUPPORTED,tg.unit_weights),
                         oracle_conditional_observable(st,SUPPORTED,tg.unit_weights))

    def test_source_full_laws_derive_assignment_means(self):
        st=make_study();tg=target(st)
        for operator in ('NODE_FULL_LAW','FULL_JOINT_LAW'):
            with self.subTest(operator=operator):
                r=identify_verified_fixed_policy(st,tg,(a4(st,kind=operator),),
                                                 assumptions=assumptions())
                self.assertIn('FULL_LAW' if operator=='NODE_FULL_LAW' else 'FULL_JOINT',r.a4_rule_id)
                self.assertTrue(replay_verified_fixed_policy(r))

    def test_arm_only_and_partial_assignment_source_fail(self):
        st=make_study();tg=target(st)
        for source in (a4(st,'NODE_ARM_MEANS'),a4(st,z=(0,0,0,0))):
            with self.subTest(operator=source.operator):
                with self.assertRaises(R1bPolicyUnavailable) as err:
                    identify_verified_fixed_policy(st,tg,(source,),assumptions=assumptions())
                self.assertEqual(err.exception.reason_code,'INFORMATION_BLOCKED')

    def test_finite_sample_is_not_population(self):
        st=make_study()
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(st,target(st),
                (a4(st,availability='FINITE_SAMPLE_ESTIMATE'),),assumptions=assumptions())
        self.assertEqual(err.exception.reason_code,'INFORMATION_BLOCKED')

    def test_proposed_or_unresolved_source_cannot_license(self):
        st=make_study()
        for admission in ('PROPOSED','UNRESOLVED','CONTRADICTED'):
            with self.subTest(admission=admission):
                with self.assertRaises(R1bPolicyUnavailable):
                    identify_verified_fixed_policy(st,target(st),(a4(st,admission=admission),),
                        assumptions=assumptions())

    def test_randomization_not_confirmed(self):
        st=make_study()
        for aa in (assumptions(omitted=('full_vector_randomization',)),
                   assumptions(proposed=('full_vector_randomization',))):
            with self.assertRaises(R1bPolicyUnavailable) as err:
                identify_verified_fixed_policy(st,target(st),(a4(st),),assumptions=aa)
            self.assertEqual(err.exception.reason_code,'NEEDS_INPUT')

    def test_zero_support_policy_defined_but_this_route_fails(self):
        for kind in ('D2','D3'):
            st=make_study(kind);z=(1,1,1,1)
            with self.assertRaises(R1bPolicyUnavailable) as err:
                identify_verified_fixed_policy(st,target(st,z),(a4(st,z=z),),assumptions=assumptions())
            self.assertEqual(err.exception.reason_code,'OFF_SUPPORT_ALTERNATE_THEOREM')

    def test_missing_policy_support_does_not_change_target_identity(self):
        a=make_study('D1');b=make_study('D2')
        self.assertEqual(target(a).target_digest,target(b).target_digest)
        self.assertNotEqual(a.protocol_digest,b.protocol_digest)
        self.assertNotEqual(solve('D1').certificate_sha256,solve('D2').certificate_sha256)

    def test_unconfirmed_target_and_nonpretreatment_graph(self):
        st=make_study()
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(st,target(st,authority='PROPOSED'),
                                           (a4(st),),assumptions=assumptions())
        self.assertEqual(err.exception.reason_code,'NEEDS_INPUT')
        other=make_study(graph='UNRESOLVED')
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(other,target(other),
                                           (a4(other),),assumptions=assumptions())
        self.assertEqual(err.exception.reason_code,'NETWORK_PRETREATMENT_STATUS_UNRESOLVED')

    def test_observational_not_given_randomized_license(self):
        st=make_study(regime='observational')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(st,target(st),(a4(st),),assumptions=assumptions())

    def test_cross_protocol_and_cross_node_order_rejected(self):
        st=make_study();other=make_study('D2')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(st,target(st),(a4(other),),assumptions=assumptions())
        alt=make_study(treatment='DifferentAI')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(alt,target(alt),(a4(st),),assumptions=assumptions())

    def test_tampered_certificate_or_source_replay_fails(self):
        r=solve()
        for tampered in (
            replace(r,assignment_probability='1'),
            replace(r,identified_functional='0'),
            replace(r,verification_status='REJECTED'),
            replace(r,selected_a4_source_digest='0'*64),
            replace(r,certificate_sha256='1'*64),
            replace(r,sources=(replace(r.sources[0],provenance='tampered'),)),
            replace(r,assumptions=assumptions(omitted=('consistency',))),
        ):
            with self.subTest(case=str(tampered.certificate_sha256[:3])):
                with self.assertRaises(R1bPolicyUnavailable):
                    replay_verified_fixed_policy(tampered)

    def test_assumption_evidence_changes_certificate_not_scientific_target(self):
        st=make_study();tg=target(st);src=(a4(st),)
        a=assumptions()
        b=tuple(x.model_copy(update={'details':'re-reviewed'}) for x in a)
        first=identify_verified_fixed_policy(st,tg,src,assumptions=a)
        second=identify_verified_fixed_policy(st,tg,src,assumptions=b)
        self.assertEqual(first.target_fingerprint,second.target_fingerprint)
        self.assertNotEqual(first.certificate_sha256,second.certificate_sha256)

    def test_different_source_selection_same_target_different_proof(self):
        st=make_study();tg=target(st)
        a=identify_verified_fixed_policy(st,tg,(a4(st),),assumptions=assumptions())
        b=identify_verified_fixed_policy(st,tg,(a4(st,kind='NODE_FULL_LAW'),),assumptions=assumptions())
        self.assertEqual(a.target_fingerprint,b.target_fingerprint)
        self.assertNotEqual(a.certificate_sha256,b.certificate_sha256)

    def test_shadow_candidacy_still_does_not_claim_point(self):
        st=make_study();tg=target(st);src=(a4(st),)
        r=assess_nonarm_network_inquiry(st,tg,src,family_id=FIXED_POLICY_CANDIDATE,
                                        assumptions=assumptions())
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')
        self.assertIsNone(r.mathematical_identification_from_router)
        verified=identify_verified_fixed_policy(st,tg,src,assumptions=assumptions())
        self.assertEqual(verified.status,'POINT')


from pfn_pipeline.identification_policy_r1b import (
    identify_verified_finite_policy_mixture, replay_verified_finite_policy_mixture,
)

class R1bFiniteStochasticPolicy(unittest.TestCase):
    def test_two_supported_atoms_recover_stochastic_policy_value(self):
        for design in ('D1','D2','D3'):
            with self.subTest(design=design):
                st=make_study(design)
                z1=(1,0,1,0);z2=(0,1,0,1)
                components=tuple(identify_verified_fixed_policy(st,target(st,z),
                    (a4(st,z=z,source_id='source:'+''.join(map(str,z))),),
                    assumptions=assumptions()) for z in (z1,z2))
                r=identify_verified_finite_policy_mixture(components,
                                                       policy_probabilities=('1/4','3/4'))
                expected=Fraction(1,4)*oracle_policy(st,z1,components[0].target.unit_weights)
                expected+=Fraction(3,4)*oracle_policy(st,z2,components[1].target.unit_weights)
                observed=Fraction(1,4)*oracle_conditional_observable(st,z1,components[0].target.unit_weights)
                observed+=Fraction(3,4)*oracle_conditional_observable(st,z2,components[1].target.unit_weights)
                self.assertEqual(expected,observed)
                self.assertTrue(replay_verified_finite_policy_mixture(r))
                self.assertEqual(r.status,'POINT')
                self.assertEqual(len(r.summary()['policy_support']),2)
                self.assertIsNone(r.estimation_request)

    def test_policy_atom_permutation_has_same_target_id_and_proof(self):
        st=make_study(); z=(1,0,1,0);z2=(0,1,0,1)
        a=identify_verified_fixed_policy(st,target(st,z), (a4(st,z=z),),assumptions=assumptions())
        b=identify_verified_fixed_policy(st,target(st,z2),(a4(st,z=z2),),assumptions=assumptions())
        x=identify_verified_finite_policy_mixture((a,b),policy_probabilities=('1/3','2/3'))
        y=identify_verified_finite_policy_mixture((b,a),policy_probabilities=('2/3','1/3'))
        self.assertEqual(x.target_fingerprint,y.target_fingerprint)
        self.assertEqual(x.certificate_sha256,y.certificate_sha256)

    def test_reject_zero_or_wrong_normalization_or_float_policy_probabilities(self):
        st=make_study();a=solve()
        for weights in (('0',),('1/3',),(-1,), (0.5,), ('nan',)):
            with self.subTest(weights=weights):
                with self.assertRaises((R1bPolicyUnavailable,ValueError)):
                    identify_verified_finite_policy_mixture((a,),policy_probabilities=weights)

    def test_reject_duplicate_policy_atom_and_mismatched_protocol(self):
        a=solve()
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_finite_policy_mixture((a,a),policy_probabilities=('1/2','1/2'))
        b=solve('D2')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_finite_policy_mixture((a,b),policy_probabilities=('1/2','1/2'))

    def test_mixture_certificate_tampering_rejected(self):
        a=solve()
        r=identify_verified_finite_policy_mixture((a,),policy_probabilities=('1',))
        for wrong in (replace(r,identified_functional='fake'),replace(r,target_fingerprint='0'*64),
                      replace(r,certificate_sha256='1'*64)):
            with self.assertRaises(R1bPolicyUnavailable):
                replay_verified_finite_policy_mixture(wrong)


class R1bAdditionalBoundaries(unittest.TestCase):
    def test_permuted_nodes_cannot_use_another_studys_source(self):
        original=make_study()
        reordered=make_study(nodes=('b','a','c','d'))
        self.assertNotEqual(original.shared_scope_digest,reordered.shared_scope_digest)
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(reordered,target(reordered),
                (a4(original),),assumptions=assumptions())

    def test_nonfull_joint_outcome_nodes_do_not_entail_policy(self):
        st=make_study()
        partial=a4(st,kind='FULL_JOINT_LAW',nodes=('a','b'))
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(st,target(st),(partial,),assumptions=assumptions())
        self.assertEqual(err.exception.reason_code,'INFORMATION_BLOCKED')

    def test_conflicting_same_id_source_declarations_block(self):
        st=make_study();src=a4(st)
        inconsistent=replace(src,provenance='different declaration')
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(st,target(st),
                (src,inconsistent),assumptions=assumptions())
        self.assertEqual(err.exception.reason_code,'SOURCE_CONFLICT')

    def test_policy_scientific_identity_includes_intervention_variable(self):
        ai=solve(); other=make_study(treatment='NewMedication')
        oth=identify_verified_fixed_policy(other,target(other),(a4(other),),
                                         assumptions=assumptions())
        self.assertEqual(ai.target.target_digest,oth.target.target_digest)
        self.assertNotEqual(ai.target_fingerprint,oth.target_fingerprint)
        self.assertNotEqual(ai.certificate_sha256,oth.certificate_sha256)

    def test_reconstructed_invalid_saved_result_even_with_fake_digest(self):
        from pfn_pipeline.identification_a4_shadow import _sha
        from pfn_pipeline.identification_policy_r1b import _result_payload
        orig=solve();changed=replace(orig,identified_functional='FALSE POLICY FORMULA')
        changed=replace(changed,certificate_sha256=_sha(_result_payload(changed)))
        with self.assertRaisesRegex(R1bPolicyUnavailable,'POLICY_CERTIFICATE_REPLAY_MISMATCH'):
            replay_verified_fixed_policy(changed)

    def test_pydantic_assumption_copy_cannot_bypass_status_verification(self):
        st=make_study(); base=list(assumptions())
        index=next(i for i,a in enumerate(base) if a.name=='full_vector_randomization')
        # model_copy does not run the original pydantic validator.
        base[index]=base[index].model_copy(update={'confirmed':False})
        with self.assertRaises(R1bPolicyUnavailable) as err:
            identify_verified_fixed_policy(st,target(st),(a4(st),),assumptions=tuple(base))
        self.assertEqual(err.exception.reason_code,'ASSUMPTION_STATUS_INCONSISTENT')

if __name__=='__main__': unittest.main()
