"""v2.6: R3 p-standardized arm/effect math, provenance, A6, routing and reuse.

Independent exact assignment enumeration serves as an oracle; no PFN.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_a4_shadow import _sha
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
)
from pfn_pipeline.identification_observational_r3 import (
    R3Unavailable,declare_observational_population_v23,
    identify_observational_policy_v23,replay_observational_policy_v23,
)
from pfn_pipeline.identification_observational_effects import (
    identify_observational_effects_v26,replay_observational_effects_v26,
    _certificate_payload,
)
from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, identify_network_business_query,
    replay_verified_business_outcome,
)


def study(n=3,edges=(('n0','n1'),('n1','n2')),observational=True):
    return declare_network_study(network_id='observational-effects-v26',
      node_order=tuple(f'n{i}' for i in range(n)),undirected_edges=tuple(edges),
      treatment_variable='AI',outcome_variable='Sales',outcome_kind='continuous',
      context_reference='W=w_pre',
      observation_regime='observational' if observational else 'experimental',
      assignment_design=None if observational else {'kind':'complete_randomization_binary_v1','m':1},
      protocol_provenance='synthetic protocol',network_provenance='fixed graph',
      graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def assumptions(*,omit=None,proposed=None):
    names=('full_vector_conditional_exchangeability','consistency',
       'fixed_pretreatment_network','finite_conditional_first_moments')
    return tuple(Assumption(name=n,
       source='llm_candidate' if n==proposed else 'demo_specification',
       confirmed=n!=proposed,
       evidence=['explicit SYNTHETIC assumed for this test, not learned from data'])
       for n in names if n!=omit)


def population(st,weights=None,**kwargs):
    vecs=list(product((0,1),repeat=len(st.node_order)))
    if weights is None:
        masses=[(t,Fraction(1,len(vecs))) for t in vecs]
    else:
        masses=[(t,Fraction(w)) for t,w in weights]
    return declare_observational_population_v23(st,
       source_id=kwargs.pop('source_id','complete-population-operator-v26'),
       provenance='synthetic full assignment/node outcome conditional law, not samples',
       assignment_masses=masses,outcome_nodes=kwargs.pop('outcome_nodes',st.node_order),
       **kwargs)


def signature(st,kind='strict_majority_ties_low'):
    if kind=='pretreatment_core_collaborator_majority':
        neighbors={n:set() for n in st.node_order}
        for a,b in st.undirected_edges:neighbors[a].add(b);neighbors[b].add(a)
        return declare_policy_signature(st,grouping=kind,
            core_collaborators={n:tuple(sorted(neighbors[n])[:1]) for n in st.node_order})
    return declare_policy_signature(st,grouping=kind)


def effect(kind='DIRECT',node='n1',s0=0,s1=0,group=None,authority=None):
    weights=((node,1),) if group is None else tuple(group)
    return EffectQueryV18(kind=kind,node_weights=weights,
        reference_exposure=s0,comparison_exposure=s1,
        cohort_authority=authority,
        cohort_evidence='pretreatment declared subgroup' if authority else None)


def solve(st=None,src=None,sig=None,queries=None,a5=None):
    st=study() if st is None else st
    src=population(st) if src is None else src
    sig=signature(st) if sig is None else sig
    queries=(effect(),) if queries is None else queries
    return identify_observational_effects_v26(st,src,sig,assumptions=assumptions() if a5 is None else a5,requests=queries)


class R3ObservationalStandardizedEffectsTests(unittest.TestCase):
    def test_direct_effect_formula_and_exact_arm_support(self):
        r=solve()
        self.assertEqual(r.status,'POINT')
        self.assertEqual(r.verification_status,'VERIFIED')
        self.assertEqual(r.proofs[0].arm_support,('3/8','3/8'))
        self.assertEqual([(t.own_treatment,str(t.coefficient)) for t in r.proofs[0].terms],
                         [(0,'-1'),(1,'1')])
        self.assertTrue(replay_observational_effects_v26(r))
        self.assertFalse(r.summary()['exposure_sufficiency_required'])
        self.assertNotIn('mean_signature_sufficiency',r.summary()['assumptions_used'])
        self.assertIsNone(r.estimation_request)

    def test_spillover_and_total_distinct_from_fixed_policy(self):
        r=solve(queries=(effect('SPILLOVER',s0=0,s1=1), effect('TOTAL',s0=0,s1=1)))
        self.assertEqual(len(r.proofs),2)
        self.assertEqual(r.proofs[0].arm_support,('3/8','1/8'))
        self.assertEqual(r.proofs[1].arm_support,('3/8','1/8'))
        self.assertNotEqual(r.proofs[0].target_fingerprint,r.proofs[1].target_fingerprint)
        self.assertTrue(replay_observational_effects_v26(r))

    def test_group_aggregation_reuses_R1a_effect_recipe(self):
        group=(('n2','1'),('n0','2'))
        req=effect('TOTAL',s0=0,s1=1,group=group,authority='HUMAN_CONFIRMED_PRETREATMENT')
        terms=compile_effect_query_terms(req)
        self.assertEqual(set(t.coefficient for t in terms),{Fraction(2,3),Fraction(-2,3),Fraction(1,3),Fraction(-1,3)})
        r=solve(queries=(req,))
        self.assertEqual(len(r.proofs[0].terms),4)
        self.assertTrue(replay_observational_effects_v26(r))

    def test_group_without_pretreatment_authority_blocked(self):
        with self.assertRaisesRegex((ValueError,TypeError),'PRETREATMENT_GROUP_EVIDENCE_REQUIRED'):
            effect('DIRECT',group=(('n0',1),('n2',1)))

    def test_all_five_E_work_without_new_theorem_families(self):
        st=study()
        for e,s in [
            ('strict_majority_ties_low',1),('three_level_treated_neighbor_fraction',2),
            ('pretreatment_core_collaborator_majority',1),
            ('exact_treated_neighbor_count',2),('any_treated_neighbor',1)]:
            with self.subTest(e=e):
                sig=signature(st,e)
                r=solve(st=st,sig=sig,queries=(effect('SPILLOVER',s0=0,s1=s),))
                self.assertEqual(r.theorem_id,'R3_OBSERVATIONAL_P_STANDARDIZED_ARM_CONTRAST_FIXED_W_POINT_V1')
                self.assertTrue(replay_observational_effects_v26(r))

    def test_assignment_correlated_observational_law_not_independent(self):
        st=study()
        cells=[((0,0,0),Fraction(1,5)),((1,1,1),Fraction(2,5)),
               ((1,0,1),Fraction(1,5)),((0,1,0),Fraction(1,5))]
        src=population(st,cells)
        r=solve(st=st,src=src,queries=(effect('SPILLOVER',s0=0,s1=1),))
        # With n1 treated, (010) is low and (111) high, with non-product law.
        self.assertEqual(r.proofs[0].arm_support,('1/5','2/5'))
        self.assertTrue(replay_observational_effects_v26(r))

    def test_law_is_part_of_causal_target_identity_not_source_id(self):
        st=study();src=population(st)
        x=solve(st=st,src=src)
        y=solve(st=st,src=replace(src,source_id='different-source-same-population-law'))
        self.assertEqual(x.proofs[0].target_fingerprint,y.proofs[0].target_fingerprint)
        self.assertNotEqual(x.certificate_sha256,y.certificate_sha256)
        skew=population(st,[(t,Fraction(1,2) if t==(1,1,1) else Fraction(1,14))
                            for t in product((0,1),repeat=3)])
        # weights above sum 1/2 + 7/14 = 1
        z=solve(st=st,src=skew)
        self.assertNotEqual(x.proofs[0].target_fingerprint,z.proofs[0].target_fingerprint)

    def test_independent_oracle_p_standardized_potential_outcomes(self):
        # Y_i(t) can vary across assignments *sharing a signature*. No mean
        # sufficiency is claimed. Under full-vector exchangeability we can
        # independently evaluate the standardized causal contrast.
        st=study();src=population(st)
        result=solve(st=st,src=src,queries=(effect('SPILLOVER',s0=0,s1=1),))
        def y(t):
            return Fraction(2*t[0]+4*t[2]+t[1]+t[0]*t[1]*t[2],10)
        weights={t:Fraction(p) for t,p in src.assignment_masses}
        def mu(a,s):
            cells=[t for t in weights if t[1]==a and int(t[0]+t[2]>1)==s]
            denominator=sum((weights[t] for t in cells),Fraction(0))
            return sum((weights[t]*y(t) for t in cells),Fraction(0))/denominator
        expected=mu(1,1)-mu(1,0)
        obs=Fraction(0)
        for term,den in zip(result.proofs[0].terms,result.proofs[0].arm_support):
            self.assertEqual(Fraction(den),sum((weights[t] for t in weights
                    if t[1]==term.own_treatment and int(t[0]+t[2]>1)==term.exposure_state),Fraction(0)))
            obs+=term.coefficient*mu(term.own_treatment,term.exposure_state)
        self.assertEqual(obs,expected)
        # Distinct full vectors inside the low-signature cell have different outcomes.
        self.assertNotEqual(y((0,1,0)),y((1,1,0)))

    def test_zero_arm_support_denied_even_when_full_policy_supported(self):
        st=study()
        src=population(st,[((0,0,0),Fraction(1,2)),((1,1,1),Fraction(1,2))])
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_ARM_SUPPORT'):
            solve(st=st,src=src,queries=(effect('SPILLOVER',s0=0,s1=1),))

    def test_missing_exchangeability_or_proposed_exchangeability(self):
        for a5 in (assumptions(omit='full_vector_conditional_exchangeability'),
                   assumptions(proposed='full_vector_conditional_exchangeability')):
            with self.subTest(a5=a5), self.assertRaisesRegex(R3Unavailable,'NEEDS_INPUT'):
                solve(a5=a5)

    def test_observational_is_not_experimental(self):
        st=study(observational=False)
        source=population(study())
        with self.assertRaisesRegex(R3Unavailable,'OBSERVATIONAL_STUDY_REQUIRED'):
            solve(st=st,src=source)

    def test_sample_not_population_a4(self):
        st=study()
        src=population(st,availability='FINITE_SAMPLE_ESTIMATE')
        with self.assertRaisesRegex(R3Unavailable,'A4_POPULATION_OPERATOR_REQUIRED'):
            solve(st=st,src=src)

    def test_unadmitted_or_wrong_source_rejected(self):
        st=study();src=population(st)
        for bad in (replace(src,admission='PROPOSED'),replace(src,protocol_digest='other')):
            with self.subTest(bad=bad),self.assertRaises(R3Unavailable):
                solve(st=st,src=bad)

    def test_missing_outcome_node_rejected(self):
        st=study();src=population(st,outcome_nodes=('n0',))
        with self.assertRaisesRegex(R3Unavailable,'A4_WEIGHTED_OUTCOME_NODES_MISSING'):
            solve(st=st,src=src)

    def test_signature_from_different_network_rejected(self):
        st=study();bad=study(3,(('n0','n1'),('n0','n2')))
        with self.assertRaisesRegex(R3Unavailable,'SIGNATURE_STUDY_MISMATCH'):
            solve(st=st,sig=signature(bad))

    def test_E2_isolate_undefined_for_used_node(self):
        st=study(3,(('n0','n1'),))
        with self.assertRaisesRegex(R3Unavailable,'UNDEFINED_EXPOSURE_FOR_POLICY_NODE'):
            solve(st=st,sig=signature(st,'three_level_treated_neighbor_fraction'),
                 queries=(effect(node='n2'),))

    def test_E5_isolate_can_still_have_zero_high_cell(self):
        st=study(3,(('n0','n1'),))
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_ARM_SUPPORT'):
            solve(st=st,sig=signature(st,'any_treated_neighbor'),
                 queries=(effect('SPILLOVER',node='n2',s0=0,s1=1),))

    def test_invalid_exposure_label_is_not_clamped(self):
        with self.assertRaisesRegex(R3Unavailable,'INVALID_TARGET_EXPOSURE_STATE'):
            solve(queries=(effect('DIRECT',s0=7,s1=7),))

    def test_target_node_outside_study_blocked(self):
        with self.assertRaisesRegex(R3Unavailable,'TARGET_NODE_OUTSIDE_STUDY'):
            solve(queries=(effect(node='someone-else'),))

    def test_tampering_hash_detected(self):
        r=solve()
        for bad in [replace(r,verification_status='UNVERIFIED'),
                    replace(r,proofs=(replace(r.proofs[0],identified_functional='999'),)),
                    replace(r,observational_law_fingerprint='fake')]:
            with self.subTest(bad=bad),self.assertRaises(R3Unavailable):
                replay_observational_effects_v26(bad)

    def test_rehash_forged_support_detected_by_rederivation(self):
        r=solve()
        forged=replace(r,proofs=(replace(r.proofs[0],arm_support=('99','99')),))
        forged=replace(forged,certificate_sha256=_sha(_certificate_payload(forged)))
        with self.assertRaisesRegex(R3Unavailable,'R3_EFFECT_CERTIFICATE_REPLAY_MISMATCH'):
            replay_observational_effects_v26(forged)

    def test_unified_business_entry_can_replay_R3_effects(self):
        st=study();src=population(st)
        inquiry=ObservationalEffectsInquiryV26(st,src,assumptions(),signature(st),
             (effect('DIRECT'),effect('SPILLOVER',s0=0,s1=1),effect('TOTAL',s0=0,s1=1)))
        result=identify_network_business_query(inquiry)
        self.assertEqual(result.status,'POINT')
        self.assertEqual(result.route,'R3_P_STANDARDIZED_EFFECTS')
        self.assertEqual(result.query_type,'OBSERVATIONAL_EFFECTS')
        self.assertEqual(len(result.result.proofs),3)
        self.assertTrue(replay_verified_business_outcome(result))
        self.assertEqual(result.summary()['identification']['estimator_capability'],'NO_ADAPTER')

    def test_business_denies_missing_assumptions(self):
        st=study()
        inquiry=ObservationalEffectsInquiryV26(st,population(st),
             assumptions(omit='full_vector_conditional_exchangeability'),signature(st),
             (effect('DIRECT'),))
        result=identify_network_business_query(inquiry)
        self.assertEqual(result.status,'NEEDS_INPUT')
        self.assertEqual(result.reason_code,'NEEDS_INPUT')
        self.assertIsNone(result.result)
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(result)

    def test_business_distinguishes_unsupported_zero_arm_support(self):
        st=study();src=population(st,[((0,0,0),Fraction(1,2)),((1,1,1),Fraction(1,2))])
        inquiry=ObservationalEffectsInquiryV26(st,src,assumptions(),signature(st),
             (effect('SPILLOVER',s0=0,s1=1),))
        result=identify_network_business_query(inquiry)
        self.assertEqual(result.status,'UNSUPPORTED')
        self.assertEqual(result.reason_code,'ZERO_OBSERVATIONAL_ARM_SUPPORT')

    def test_replay_business_detects_changed_route_even_when_sha_valid(self):
        st=study();good=identify_network_business_query(
            ObservationalEffectsInquiryV26(st,population(st),assumptions(),signature(st),
            (effect('TOTAL',s0=0,s1=1),)))
        changed=replace(good,route='R3_FULL_ASSIGNMENT')
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(changed)

    def test_R3_original_policy_signature_E4_E5_verifier_reuse(self):
        st=study(5,tuple(('n0',f'n{i}') for i in range(1,5)))
        masses=[(tuple(int(i!=removed) for i in range(5)),Fraction(1,5)) for removed in range(5)]
        src=population(st,masses)
        tgt=fixed_policy_target_from_context(st,(1,)*5,authority='TRUSTED_FIXTURE')
        for exposure in ('any_treated_neighbor','strict_majority_ties_low'):
            sig=signature(st,exposure)
            claim=Assumption(name='mean_signature_sufficiency',source='demo_specification',
                    confirmed=True,evidence=['SYNTHETIC A5 for test'])
            suf=admit_mean_signature_sufficiency(st,sig,assumption=claim,covered_nodes=st.node_order)
            from pfn_pipeline.identification_observational_r3 import identify_observational_policy_v23
            with self.subTest(exposure=exposure):
                r=identify_observational_policy_v23(st,tgt,src,assumptions=assumptions(),
                    signature=sig,sufficiency=suf)
                self.assertEqual(r.route,'R3_MEAN_SIGNATURE')
                self.assertTrue(replay_observational_policy_v23(r))
        sig=signature(st,'exact_treated_neighbor_count')
        suf=admit_mean_signature_sufficiency(st,sig,assumption=claim,covered_nodes=st.node_order)
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_SIGNATURE_SUPPORT'):
            identify_observational_policy_v23(st,tgt,src,assumptions=assumptions(),signature=sig,sufficiency=suf)

    def test_cross_topology_and_exposure_support_replayed(self):
        networks={
          'path':(('n0','n1'),('n1','n2'),('n2','n3')),
          'ring':(('n0','n1'),('n1','n2'),('n2','n3'),('n3','n0')),
          'star':(('n0','n1'),('n0','n2'),('n0','n3')),
          'complete':tuple((f'n{i}',f'n{j}') for i in range(4) for j in range(i+1,4)),
        }
        count=0
        for name,edges in networks.items():
            st=study(4,edges)
            for exp in ('strict_majority_ties_low','exact_treated_neighbor_count','any_treated_neighbor'):
                with self.subTest(name=name,exp=exp):
                    r=solve(st=st,sig=signature(st,exp),queries=(effect('DIRECT',node='n0'),))
                    self.assertTrue(replay_observational_effects_v26(r))
                    count+=1
        self.assertEqual(count,12)

    def test_r3_effect_cannot_use_llm_sufficiency_as_ignorability(self):
        st=study(); bad=assumptions(proposed='full_vector_conditional_exchangeability')
        with self.assertRaisesRegex(R3Unavailable,'NEEDS_INPUT'):
            solve(st=st,a5=bad)

    def test_only_observational_population_law_not_declared_randomization(self):
        st=study();r=solve(st=st)
        self.assertEqual(st.observation_regime,'observational')
        self.assertIsNone(st.assignment_design_json)
        self.assertNotIn('full_vector_randomization',r.summary()['assumptions_used'])

    def test_no_duplicate_policy_family_created(self):
        st=study()
        src=population(st)
        policy=fixed_policy_target_from_context(st,(1,1,1),authority='TRUSTED_FIXTURE')
        r=identify_observational_policy_v23(st,policy,src,assumptions=assumptions())
        e=solve(st=st,src=src)
        self.assertTrue(replay_observational_policy_v23(r))
        self.assertEqual(r.route,'R3_FULL_ASSIGNMENT')
        self.assertEqual(e.route,'R3_P_STANDARDIZED_EFFECTS')
        self.assertNotEqual(e.proofs[0].target_fingerprint,r.target_fingerprint)


if __name__=='__main__':unittest.main()
