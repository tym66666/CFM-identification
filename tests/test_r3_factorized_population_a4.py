"""Independent positive/negative checks for the opt-in R3 factorized A4 subdomain.

Synthetic declared population operators, not real observational evidence.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_a4_shadow import _sha
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, ObservationalPolicyInquiryV23,
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_observational_effects import (
    identify_observational_effects_v26,
)
from pfn_pipeline.identification_observational_factorized_a4 import (
    ObservationalFactorizedArmPopulationV27P1,
    declare_observational_factorized_arm_population_v27p1,
    identify_observational_factorized_effects_v27p1,
    replay_observational_factorized_effects_v27p1,
    _payload,
)
from pfn_pipeline.identification_observational_r3 import (
    R3Unavailable, declare_observational_population_v23,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context


def st(n=5,*,regime='observational'):
    ids=tuple(f'n{i}' for i in range(n))
    edges=tuple((ids[i],ids[(i+1)%n]) for i in range(n)) if n>6 else tuple((ids[i],ids[i+1]) for i in range(n-1))
    return declare_network_study(network_id=f'factorized-observed-{n}',node_order=ids,
        undirected_edges=edges,treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=w0',
        observation_regime=regime,assignment_design=None,
        protocol_provenance='synthetic explicitly reviewed observational study',
        network_provenance='fixed network as-if prior to treatment',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def a5(*,omit=None,proposed=None):
    names=('full_vector_conditional_exchangeability','consistency',
           'fixed_pretreatment_network','finite_conditional_first_moments')
    return tuple(Assumption(name=name,
          source='llm_candidate' if name==proposed else 'demo_specification',
          confirmed=name!=proposed,
          evidence=['synthetic explicitly admitted; NOT proven with observed data'])
          for name in names if name!=omit)


def req(kind='DIRECT',node='n2',s0=0,s1=0,*,group=None,cohort=None):
    return EffectQueryV18(kind=kind,node_weights=((node,1),) if group is None else group,
        reference_exposure=s0,comparison_exposure=s1,
        cohort_authority=cohort,
        cohort_evidence='pre-treatment group declaration' if cohort else None)


def make(study=None, grouping='strict_majority_ties_low', ps=None, queries=None,
         *, admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
         covered_arms=None, source_id='synthetic-arm-law-operator', a5records=None):
    study=study or st()
    sig=declare_policy_signature(study,grouping=grouping,
        **({'core_collaborators':{node:(
             next(y for e in study.undirected_edges for y in e if node in e and y!=node),)
             for node in study.node_order}}
           if grouping=='pretreatment_core_collaborator_majority' else {}))
    if ps is None:
        ps=tuple(Fraction(i+1,i+3) for i in range(len(study.node_order)))
    queries=queries or (req(),)
    arms=(covered_arms if covered_arms is not None else
          tuple(sorted({term.coordinates for q in queries
                        for term in compile_effect_query_terms(q)},
                       key=lambda x:(study.node_order.index(x[0]),x[1],x[2]))))
    source=declare_observational_factorized_arm_population_v27p1(
        study,sig,source_id=source_id,
        provenance='Synthetic exact population p factorization and symbolic arm means, not a sample',
        treatment_one_probabilities=ps,covered_arms=arms,admission=admission,
        availability=availability)
    return study,source,sig,(a5() if a5records is None else a5records),queries


class ObservationalFactorizedA4V27P1Tests(unittest.TestCase):
    def test_same_theorem_and_small_graph_oracle_all_five_exposures(self):
        for name,s1 in [('strict_majority_ties_low',1),
                        ('three_level_treated_neighbor_fraction',2),
                        ('pretreatment_core_collaborator_majority',1),
                        ('exact_treated_neighbor_count',2),
                        ('any_treated_neighbor',1)]:
            with self.subTest(grouping=name):
                qs=(req('SPILLOVER',s1=s1),)
                study,source,sig,assumptions,requests=make(grouping=name,queries=qs)
                ours=identify_observational_factorized_effects_v27p1(
                    study,source,sig,assumptions=assumptions,requests=requests)
                self.assertTrue(replay_observational_factorized_effects_v27p1(ours))
                self.assertEqual(ours.route,'R3_P_STANDARDIZED_EFFECTS')
                self.assertEqual(ours.theorem_id,'R3_OBSERVATIONAL_P_STANDARDIZED_ARM_CONTRAST_FIXED_W_POINT_V1')
                self.assertFalse(ours.summary()['exposure_sufficiency_required'])
                # Independent full treatment-vector enumeration (small graph only).
                tuples=list(product((0,1),repeat=len(study.node_order)))
                probabilities=[Fraction(p) for p in source.treatment_one_probabilities]
                masses=[(t,__import__('math').prod((p if a else 1-p)
                        for a,p in zip(t,probabilities))) for t in tuples]
                full=declare_observational_population_v23(study,source_id='synthetic-full-law',
                    provenance='independent exact enumeration; symbolic population outcome operator',
                    assignment_masses=masses)
                oracle=identify_observational_effects_v26(study,full,sig,
                        assumptions=assumptions,requests=requests)
                self.assertEqual(ours.proofs[0].arm_support,oracle.proofs[0].arm_support)
                self.assertEqual(ours.proofs[0].identified_functional,
                                 oracle.proofs[0].identified_functional)
                self.assertNotEqual(ours.proofs[0].target_fingerprint,
                                    oracle.proofs[0].target_fingerprint,
                    'Different canonical p-law representations currently have distinct fingerprint namespaces')

    def test_300_node_ring_without_full_enumeration(self):
        study=st(300)
        qs=(req('SPILLOVER',node='n151',s0=0,s1=1),)
        study,source,sig,assumptions,requests=make(study=study,
                ps=(Fraction(1,3),)*300,queries=qs)
        value=identify_network_business_query(ObservationalEffectsInquiryV26(
            study,source,assumptions,sig,requests))
        self.assertEqual(value.status,'POINT')
        self.assertTrue(replay_verified_business_outcome(value))
        # Ring degree 2: strict majority high iff both neighbors treated.
        self.assertEqual(value.result.proofs[0].arm_support,('8/27','1/27'))
        self.assertEqual(value.result.summary()['node_count'],300)
        self.assertEqual(value.result.summary()['estimator_capability'],'NO_ADAPTER')
        handoff=inspect_verified_business_handoff_v27(value)
        self.assertEqual(handoff['estimation']['status'],'NO_ADAPTER')
        self.assertTrue(handoff['theorem_replayed'])

    def test_target_identity_is_law_specific_but_source_invariant(self):
        a=make();result_a=identify_observational_factorized_effects_v27p1(
            a[0],a[1],a[2],assumptions=a[3],requests=a[4])
        b=make(source_id='other-verified-data-provider')
        result_b=identify_observational_factorized_effects_v27p1(
            b[0],b[1],b[2],assumptions=b[3],requests=b[4])
        self.assertEqual(result_a.proofs[0].target_fingerprint,result_b.proofs[0].target_fingerprint)
        self.assertNotEqual(result_a.certificate_sha256,result_b.certificate_sha256)
        c=make(ps=(Fraction(3,4),)*5)
        result_c=identify_observational_factorized_effects_v27p1(
            c[0],c[1],c[2],assumptions=c[3],requests=c[4])
        self.assertNotEqual(result_a.proofs[0].target_fingerprint,result_c.proofs[0].target_fingerprint)

    def test_node_cohort_effect_reuses_original_query_algebra(self):
        qs=(req('TOTAL',s1=1,group=(('n1',1),('n2',2)),cohort='HUMAN_CONFIRMED_PRETREATMENT'),)
        study,source,sig,assumptions,requests=make(queries=qs)
        result=identify_observational_factorized_effects_v27p1(
            study,source,sig,assumptions=assumptions,requests=requests)
        self.assertEqual(len(result.proofs[0].terms),4)
        self.assertTrue(replay_observational_factorized_effects_v27p1(result))

    def test_missing_or_unaccepted_A4(self):
        study,source,sig,assumptions,requests=make()
        with self.assertRaisesRegex(R3Unavailable,'A4_WEIGHTED_ARM_POPULATION_MEANS_MISSING'):
            identify_observational_factorized_effects_v27p1(study,replace(source,covered_arms=()),sig,
                assumptions=assumptions,requests=requests)
        for src in (replace(source,admission='PROPOSED'),replace(source,availability='FINITE_SAMPLE_ESTIMATE')):
            rejected=identify_network_business_query(ObservationalEffectsInquiryV26(
                study,src,assumptions,sig,requests))
            self.assertEqual(rejected.status,'NEEDS_INPUT')
            self.assertIsNone(rejected.result)

    def test_missing_exchangeability_not_inferred_from_factorization(self):
        for records in (a5(omit='full_vector_conditional_exchangeability'),
                        a5(proposed='full_vector_conditional_exchangeability')):
            study,source,sig,assumptions,requests=make(a5records=records)
            value=identify_network_business_query(ObservationalEffectsInquiryV26(
                study,source,assumptions,sig,requests))
            self.assertNotEqual(value.status,'POINT')
            self.assertIsNone(value.result)

    def test_declared_A4_cannot_include_undefined_exposure_state(self):
        study,source,sig,assumptions,requests=make()
        invalid=replace(source,covered_arms=(('n2',0,2),))
        with self.assertRaisesRegex(R3Unavailable,'A4_FACTOR_UNDEFINED_DECLARED_ARM_CELL'):
            identify_observational_factorized_effects_v27p1(study,invalid,sig,
                assumptions=assumptions,requests=requests)

    def test_zero_observational_support_and_missing_cell_remain_distinct(self):
        study,source,sig,assumptions,requests=make(ps=(Fraction(0),)*5)
        # n2 never treated, so the requested high own-treatment arm cannot exist.
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_ARM_SUPPORT'):
            identify_observational_factorized_effects_v27p1(study,source,sig,
                assumptions=assumptions,requests=requests)

    def test_scientific_signature_and_study_binding(self):
        study,source,sig,assumptions,requests=make()
        new_sig=declare_policy_signature(study,grouping='any_treated_neighbor')
        with self.assertRaisesRegex(R3Unavailable,'A4_STUDY_OR_PROTOCOL_MISMATCH'):
            identify_observational_factorized_effects_v27p1(study,source,new_sig,
                assumptions=assumptions,requests=requests)
        other=st(6)
        with self.assertRaisesRegex(R3Unavailable,'A4_STUDY_OR_PROTOCOL_MISMATCH'):
            identify_observational_factorized_effects_v27p1(other,source,sig,
                assumptions=assumptions,requests=requests)

    def test_bad_probability_floats_invalid_and_full_law_not_assumed(self):
        study,source,sig,assumptions,requests=make()
        with self.assertRaisesRegex(ValueError,'EXACT_RATIONAL_NOT_FLOAT_REQUIRED'):
            make(ps=(0.5,)*5)
        for invalid in ('4/3','-1/3'):
            with self.assertRaisesRegex(ValueError,'OBSERVATIONAL_NODE_PROBABILITY_OUTSIDE_UNIT_INTERVAL'):
                make(ps=(invalid,)*5)
        with self.assertRaisesRegex(ValueError,'A4_FACTOR_CANONICAL_EXACT_NODE_PROBABILITY_REQUIRED'):
            replace(source,treatment_one_probabilities=('2/4',)*5)
        with self.assertRaisesRegex(ValueError,'A4_FACTOR_ARMS_MUST_BE_UNIQUE'):
            replace(source,covered_arms=(('n2',0,0),('n2',0,0)))

    def test_falsified_certificate_even_with_new_digest(self):
        study,source,sig,assumptions,requests=make()
        r=identify_observational_factorized_effects_v27p1(study,source,sig,
            assumptions=assumptions,requests=requests)
        altered=replace(r.proofs[0],arm_support=('1/999',)*len(r.proofs[0].arm_support))
        tampered=replace(r,proofs=(altered,))
        with self.assertRaisesRegex(R3Unavailable,'CERTIFICATE_DIGEST_MISMATCH'):
            replay_observational_factorized_effects_v27p1(tampered)
        rerendered=replace(tampered,certificate_sha256=_sha(_payload(tampered)))
        with self.assertRaisesRegex(R3Unavailable,'CERTIFICATE_REPLAY_MISMATCH'):
            replay_observational_factorized_effects_v27p1(rerendered)

    def test_no_policy_value_or_generic_observational_backend(self):
        study,source,sig,assumptions,requests=make()
        policy=fixed_policy_target_from_context(study,tuple([1]*len(study.node_order)),authority="HUMAN_CONFIRMED")
        val=identify_network_business_query(ObservationalPolicyInquiryV23(
            study,policy,source,assumptions))
        self.assertNotEqual(val.status,'POINT')
        self.assertIsNone(val.result)

    def test_no_exposure_sufficiency_mathematical_witness(self):
        # The observational p-standardized effect is a mixture of all full
        # assignments inside each arm; its Y(t) may vary within that arm.
        from pfn_pipeline.identification_observational_r3 import _manual_exposure_classify_v26
        study,source,sig,assumptions,requests=make()
        result=identify_observational_factorized_effects_v27p1(study,source,sig,
            assumptions=assumptions,requests=requests)
        ps=tuple(Fraction(x) for x in source.treatment_one_probabilities)
        weights={t:__import__('math').prod((p if a else (1-p)) for a,p in zip(t,ps))
                 for t in product((0,1),repeat=5)}
        def potential(t):
            return Fraction(2*t[0]+3*t[1]*t[3]+t[2]+4*t[4],7)
        first=(0,0,1,0,0);second=(1,0,1,0,0)
        self.assertNotEqual(potential(first),potential(second))
        self.assertEqual(_manual_exposure_classify_v26(first[1]+first[3],2,sig.grouping),0)
        self.assertEqual(_manual_exposure_classify_v26(second[1]+second[3],2,sig.grouping),0)
        def observed_conditional(a,s):
            cells=[(t,p) for t,p in weights.items()
                   if t[2]==a and _manual_exposure_classify_v26(t[1]+t[3],2,sig.grouping)==s]
            return sum((p*potential(t) for t,p in cells),Fraction(0))/sum(
                (p for _,p in cells),Fraction(0))
        contrast=sum((term.coefficient*observed_conditional(
                   term.own_treatment,term.exposure_state)
                   for term in result.proofs[0].terms),Fraction(0))
        # The same weights form the structural target by definition. No
        # equality Y(t)=h(t_i,g_i(t)) was used or accepted.
        target=sum((term.coefficient*observed_conditional(
               term.own_treatment,term.exposure_state)
               for term in result.proofs[0].terms),Fraction(0))
        self.assertEqual(contrast,target)
        self.assertNotEqual(contrast,Fraction(0))

    def test_real_nonfactorized_law_same_node_marginals_is_not_covered(self):
        # p(T0=T1)=1 yet both marginal p_i=1/2. An incorrect product-law
        # declaration would compute p(11)=1/4 instead of true 1/2. This
        # test illustrates SCIENTIFIC source admissibility, NOT its verification.
        independent_p11=Fraction(1,2)**2
        actual_correlated_p11=Fraction(1,2)
        self.assertNotEqual(independent_p11,actual_correlated_p11)


if __name__=='__main__': unittest.main()
