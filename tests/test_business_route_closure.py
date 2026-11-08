"""Pre-v2.7 v2.6 hardening: route/target/envelope integrity and cross-route consistency.

All 'POINT' fixtures are synthetic symbolic population operators under expressly
admitted assumptions, never actual individual effects or business estimates.
"""
from __future__ import annotations
from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline.identification_business import (
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21,
    FinitePolicyInquiryV21, ObservationalPolicyInquiryV23,
    ObservationalEffectsInquiryV26, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_coverage import (
    _task_d1, _arm_bundle, _fixed, _study, _assumptions, _full_source,
)
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency,
)
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context, declare_network_study


def _r3():
    nodes=('a','b','c')
    st=declare_network_study(network_id='route-closure-r3-small',
      node_order=nodes,undirected_edges=(('a','b'),('b','c')),
      treatment_variable='AI',outcome_variable='Sales',outcome_kind='continuous',
      context_reference='W=synthetic_pre',observation_regime='observational',
      assignment_design=None, protocol_provenance='explicit synthetic observational study',
      network_provenance='pretreatment known path',
      graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    src=declare_observational_population_v23(st,
      source_id='population-a4-synthetic', provenance='full population *symbolic* operator',
      assignment_masses=[(z,Fraction(1,8)) for z in product((0,1),repeat=3)])
    assumed=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
                  status='ADMITTED',evidence=['synthetic model postulates this A5, not empirically learned'])
        for n in ('full_vector_conditional_exchangeability','consistency',
                  'fixed_pretreatment_network','finite_conditional_first_moments'))
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    return st,src,assumed,sig


def _r2_for_d1():
    study=_study('d1')
    target=fixed_policy_target_from_context(study,(1,1,0),authority='TRUSTED_FIXTURE')
    sig=declare_policy_signature(study,grouping='strict_majority_ties_low')
    # Every target signature is individually supported under D1 iid 1/2.
    treated={'0':1,'1':1,'2':0}
    edges=study.undirected_edges
    neigh={node:set() for node in study.node_order}
    for a,b in edges: neigh[a].add(b);neigh[b].add(a)
    cells=tuple((node,treated[node],int(sum(treated[n] for n in neigh[node])>len(neigh[node])//2))
                for node in study.node_order)
    src=declare_signature_population_source(study,sig,
      source_id='r2-synthetic-arm-sufficient',operator='NODE_SIGNATURE_MEANS',
      outcome_nodes=study.node_order,signature_cells=cells,
      admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
      provenance='synthetic signature population operator')
    a5=admit_mean_signature_sufficiency(study,sig,covered_nodes=study.node_order,
      assumption=Assumption(name='mean_signature_sufficiency', source='demo_specification',
         confirmed=True,status='ADMITTED', evidence=['synthetic posited mean sufficiency']))
    return study,target,sig,src,a5


class BusinessRouteClosureV26(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task=_task_d1()
        cls.arm=identify_network_business_query(ArmInquiryV21(task))
        _,batch,a4=_arm_bundle()
        cls.composition=identify_network_business_query(EffectsInquiryV21(
            batch,a4,(EffectQueryV18(kind='DIRECT',node_weights=(('0','1'),),
                                   reference_exposure=0,comparison_exposure=0),)))
        cls.fixed=_fixed('d1',(1,1,0))
        second=_fixed('d1',(0,1,1))
        cls.finite=identify_network_business_query(FinitePolicyInquiryV21(
            (cls.fixed.result,second.result),('1/2','1/2')))
        cls.r2=_fixed('d2',(1,)*5,suff=True)
        st,src,a5,sig=_r3()
        cls.r3full=identify_network_business_query(ObservationalPolicyInquiryV23(
            st,fixed_policy_target_from_context(st,(1,1,1),authority='TRUSTED_FIXTURE'),src,a5))
        cls.r3effects=identify_network_business_query(ObservationalEffectsInquiryV26(
            st,src,a5,sig,(EffectQueryV18(kind='DIRECT',node_weights=(('b','1'),),
                                         reference_exposure=0,comparison_exposure=0),)))
        # R3-Signature must be exercised on a genuinely off-support policy.
        # The preceding 3-node all-on policy is in full support and therefore
        # returns R3-FULL even when sufficiency has also been declared.
        nodes=('hub','leaf1','leaf2','leaf3','leaf4')
        star=declare_network_study(network_id='route-closure-r3-star5',
            node_order=nodes,undirected_edges=tuple(('hub',n) for n in nodes[1:]),
            treatment_variable='AI',outcome_variable='Sales',outcome_kind='continuous',
            context_reference='W=synthetic_pre',observation_regime='observational',
            assignment_design=None,protocol_provenance='synthetic observational fixed quota law',
            network_provenance='pretreatment fixed star',
            graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
        masses=[(tuple(0 if k==omitted else 1 for k in range(5)),Fraction(1,5))
                for omitted in range(5)]
        star_source=declare_observational_population_v23(star,
            source_id='off-support-star5-synthetic-population',
            provenance='synthetic population symbolic conditional outcome operator',
            assignment_masses=masses)
        star_sig=declare_policy_signature(star,grouping='strict_majority_ties_low')
        star_suff=admit_mean_signature_sufficiency(star,star_sig,covered_nodes=nodes,
            assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',
                confirmed=True,status='ADMITTED',evidence=['explicit hypothetical mean sufficiency']))
        cls.r3signature=identify_network_business_query(ObservationalPolicyInquiryV23(
            star,fixed_policy_target_from_context(star,(1,)*5,authority='TRUSTED_FIXTURE'),
            star_source,a5,star_sig,star_suff))
        assert cls.r3signature.route=='R3_MEAN_SIGNATURE'

    def test_all_business_wrapper_types_replay(self):
        examples=(self.arm,self.composition,self.fixed,self.finite,
                  self.r2,self.r3full,self.r3effects,self.r3signature)
        for x in examples:
            with self.subTest(route=x.route, query=x.query_type):
                self.assertEqual(x.status,'POINT')
                self.assertTrue(replay_verified_business_outcome(x))
                self.assertIsNone(x.result.estimation_request)

    def test_renaming_business_query_type_cannot_reuse_theorem_proof(self):
        examples=(self.arm,self.composition,self.fixed,self.finite,
                  self.r2,self.r3full,self.r3effects,self.r3signature)
        for x in examples:
            with self.subTest(route=x.route):
                impostor='OBSERVATIONAL_EFFECTS' if x.query_type!='OBSERVATIONAL_EFFECTS' else 'FIXED_POLICY'
                with self.assertRaisesRegex(ValueError,'query_type/route mismatch'):
                    replay_verified_business_outcome(replace(x,query_type=impostor))

    def test_cross_route_same_policy_target_identity_when_both_valid(self):
        study,target,sig,r2src,suff=_r2_for_d1()
        r1b=identify_network_business_query(FixedPolicyInquiryV21(
            study,target,_assumptions(),r1b_sources=(_full_source(study),)))
        r2=identify_network_business_query(FixedPolicyInquiryV21(
            study,target,_assumptions(),r2_signature=sig,r2_sufficiency=suff,r2_sources=(r2src,)))
        self.assertEqual((r1b.status,r1b.route),('POINT','R1B_FULL_ASSIGNMENT'))
        self.assertEqual((r2.status,r2.route),('POINT','R2_MEAN_SIGNATURE'))
        self.assertEqual(r1b.result.target_fingerprint,r2.result.target_fingerprint)
        self.assertEqual(r1b.result.target.target_digest,r2.result.target.target_digest)
        self.assertTrue(replay_verified_business_outcome(r1b))
        self.assertTrue(replay_verified_business_outcome(r2))

    def test_r1b_precedence_and_r2_fallback_have_same_policy_identity(self):
        study,target,sig,r2src,suff=_r2_for_d1()
        combo=FixedPolicyInquiryV21(study,target,_assumptions(),
                   r1b_sources=(_full_source(study),),r2_signature=sig,
                   r2_sufficiency=suff,r2_sources=(r2src,))
        preferred=identify_network_business_query(combo)
        self.assertEqual(preferred.route,'R1B_FULL_ASSIGNMENT')
        # When its A4 is only arm-level, R1b must refuse, and admitted R2
        # remains available without changing the target or weakening A5.
        invalid=_full_source(study,operator='NODE_ARM_MEANS')
        fallback=identify_network_business_query(replace(combo,r1b_sources=(invalid,)))
        self.assertEqual((fallback.status,fallback.route),('POINT','R2_MEAN_SIGNATURE'))
        self.assertTrue(fallback.attempted_routes)
        self.assertEqual(fallback.attempted_routes[0][0],'R1B_FULL_ASSIGNMENT')
        self.assertEqual(fallback.result.target_fingerprint,preferred.result.target_fingerprint)
        self.assertTrue(replay_verified_business_outcome(fallback))

    def test_unaccepted_sufficiency_must_not_unlock_fallback(self):
        study,target,sig,r2src,suff=_r2_for_d1()
        proposed=replace(suff,assumption=Assumption(name='mean_signature_sufficiency',
               source='llm_candidate',status='PROPOSED',confirmed=False,evidence=['proposed only']))
        out=identify_network_business_query(FixedPolicyInquiryV21(
            study,target,_assumptions(),r1b_sources=(_full_source(study,operator='NODE_ARM_MEANS'),),
            r2_signature=sig,r2_sufficiency=proposed,r2_sources=(r2src,)))
        self.assertNotEqual(out.status,'POINT')
        self.assertIsNone(out.result)

    def test_observational_missing_exchangeability_fails_closed(self):
        st,src,a5,sig=_r3()
        req=EffectQueryV18(kind='DIRECT',node_weights=(('b','1'),),
                    reference_exposure=0,comparison_exposure=0)
        out=identify_network_business_query(ObservationalEffectsInquiryV26(
          st,src,tuple(a for a in a5 if a.name!='full_vector_conditional_exchangeability'),sig,(req,)))
        self.assertEqual(out.status,'NEEDS_INPUT')
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(out)

    def test_distinguish_observational_standardized_vs_policy_query(self):
        self.assertNotEqual(self.r3full.route,self.r3effects.route)
        self.assertNotEqual(self.r3full.query_type,self.r3effects.query_type)
        self.assertEqual(len(self.r3effects.result.observational_law_fingerprint),64)
        self.assertNotEqual(self.r3full.result.target_fingerprint,
                            self.r3effects.result.proofs[0].target_fingerprint)

if __name__=='__main__':unittest.main()
