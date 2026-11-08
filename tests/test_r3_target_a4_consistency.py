"""Opt-in, read-only cross-R3 target identity / A4 source-consistency adversarial tests.

Synthetic population licenses are deliberately stipulated and not real-world proof.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
from math import prod
import unittest

from test_r3_factorized_population_a4 import make, req, st
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, ObservationalExposureAdjustedEffectsInquiryV27P2,
    VerifiedBusinessOutcomeV21, identify_network_business_query,
)
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
from pfn_pipeline.identification_observational_exposure_adjustment import (
    declare_stratified_observational_arm_population_v27p2,admit_exposure_adjustment_a5_v27p2,
)
from pfn_pipeline.identification_r3_target_a4_audit import (
    inspect_r3_target_a4_v28p0,compare_r3_target_a4_v28p0,
    inspect_r3_joint_handoff_v28p0,
)


def route_factorized(study=None, ps=None, source_id='synthetic-l1', query=None):
    study,src,sig,a5,requests=make(study=study,ps=ps,source_id=source_id,
                                  queries=None if query is None else (query,))
    result=identify_network_business_query(ObservationalEffectsInquiryV26(
        study,src,a5,sig,requests))
    assert result.status=='POINT',result.summary()
    return result


def route_finite(like, source_id='synthetic-l2', provenance='independent exact law',
                 ps=None):
    res=like.result; st=res.study; sig=res.signature
    ps=tuple(Fraction(v) for v in res.source.treatment_one_probabilities) if ps is None else tuple(ps)
    cells=[]
    for t in product((0,1),repeat=len(ps)):
        weight=prod((p if a else 1-p for a,p in zip(t,ps)))
        if weight:
            cells.append((t,weight))
    source=declare_observational_population_v23(st,source_id=source_id,
        provenance=provenance,assignment_masses=cells)
    value=identify_network_business_query(ObservationalEffectsInquiryV26(
        st,source,res.assumptions,sig,res.requests))
    assert value.status=='POINT',value.summary()
    return value


def route_adjusted(like, source_id='synthetic-adjustment'):
    res=like.result; study=res.study; sig=res.signature; requests=res.requests
    arms={term.coordinates for r in requests for term in __import__(
        'pfn_pipeline.identification_composition',fromlist=['compile_effect_query_terms']).compile_effect_query_terms(r)}
    cells=tuple((b,*arm) for b in ('b0','b1') for arm in sorted(arms))
    ps=tuple(res.source.treatment_one_probabilities)
    src=declare_stratified_observational_arm_population_v27p2(study,sig,
        source_id=source_id,provenance='synthetic stratified symbolic population operator',
        adjustment_variable='employee_region_pre',
        strata=(('b0','1/3',ps),('b1','2/3',ps)),covered_cells=cells)
    def adm(name):
        return Assumption(name=name,source='demo_specification',confirmed=True,
            evidence=['Synthetic stipulation for exact theorem test, not empirical validation'])
    license=admit_exposure_adjustment_a5_v27p2(study,sig,
        covered_nodes=tuple(sorted({n for n,_,_ in arms})),
        potential_outcome_exposure_sufficiency=adm('potential_outcome_exposure_sufficiency'),
        exposure_level_conditional_exchangeability=adm('exposure_level_conditional_exchangeability'))
    assumptions=tuple(adm(x) for x in ('consistency','fixed_pretreatment_network',
                                      'finite_conditional_first_moments'))
    outcome=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
        study,src,assumptions,sig,license,requests))
    assert outcome.status=='POINT',outcome.summary()
    return outcome


class R3CrossTargetA4Tests(unittest.TestCase):
    def test_exact_full_vs_independent_have_same_cross_rep_target_not_old_fingerprint(self):
        fact=route_factorized(); finite=route_finite(fact)
        self.assertNotEqual(fact.result.proofs[0].target_fingerprint,
                            finite.result.proofs[0].target_fingerprint)
        report=compare_r3_target_a4_v28p0(fact,finite)
        self.assertEqual(report.relationship,'SAME_TARGET')
        self.assertTrue(report.can_merge_as_one_symbolic_target)
        self.assertEqual(report.a4_consistency,'EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT')
        self.assertEqual(report.left.cross_representation_fingerprints,
                         report.right.cross_representation_fingerprints)
        checked=inspect_r3_joint_handoff_v28p0((fact,finite))
        self.assertTrue(checked['target_merge_certified'])
        self.assertFalse(checked['conditional_mean_values_reconciled'])
        self.assertEqual(checked['estimation']['status'],'NO_ADAPTER')

    def test_same_abstract_target_with_two_distinct_provenance_sources(self):
        a=route_factorized(source_id='provider-A')
        b=route_factorized(source_id='provider-B')
        checked=inspect_r3_joint_handoff_v28p0((a,b))
        self.assertTrue(checked['target_merge_certified'])
        self.assertIsNone(checked['estimation']['request'])
        self.assertNotEqual(a.result.certificate_sha256,b.result.certificate_sha256)

    def test_two_different_observational_laws_in_one_scope_are_inconsistent(self):
        a=route_factorized(source_id='provider-A')
        b=route_factorized(ps=tuple(Fraction(2,3) for _ in range(5)),source_id='provider-B')
        report=compare_r3_target_a4_v28p0(a,b)
        self.assertEqual(report.a4_consistency,'CONFLICTING_MARGINAL_TREATMENT_LAWS')
        self.assertIn('A4_SAME_STUDY_MARGINAL_LAW_CONFLICT',report.reasons)
        self.assertFalse(report.same_target_certified)
        with self.assertRaisesRegex(ValueError,'A4_SOURCE_CONFLICT'):
            inspect_r3_joint_handoff_v28p0((a,b),require_single_target=False)

    def test_full_vs_factorized_law_disagreement_cannot_merge(self):
        a=route_factorized()
        b=route_finite(a,ps=tuple(Fraction(2,3) for _ in range(5)))
        report=compare_r3_target_a4_v28p0(a,b)
        self.assertFalse(report.can_merge_as_one_symbolic_target)
        self.assertEqual(report.a4_consistency,'CONFLICTING_MARGINAL_TREATMENT_LAWS')

    def test_same_source_id_with_changed_provenance_rejected_even_when_law_same(self):
        a=route_factorized(source_id='one-source')
        b=route_finite(a,source_id='one-source',provenance='another provenance claim')
        self.assertIn('A4_SAME_SOURCE_ID_DIFFERENT_PROVENANCE',
                      compare_r3_target_a4_v28p0(a,b).reasons)
        with self.assertRaisesRegex(ValueError,'A4_SOURCE_CONFLICT'):
            inspect_r3_joint_handoff_v28p0((a,b))

    def test_same_source_id_changed_model_rejected(self):
        a=route_factorized(source_id='same-id')
        b=route_factorized(ps=tuple(Fraction(1,4) for _ in range(5)),source_id='same-id')
        report=compare_r3_target_a4_v28p0(a,b)
        self.assertIn('A4_SAME_SOURCE_ID_DIFFERENT_MODEL',report.reasons)
        self.assertFalse(report.can_merge_as_one_symbolic_target)

    def test_different_contrast_under_same_law_cannot_merge_as_target(self):
        a=route_factorized()
        b=route_factorized(query=req(kind='SPILLOVER',s0=0,s1=1))
        report=compare_r3_target_a4_v28p0(a,b)
        self.assertEqual(report.relationship,'DISTINCT_DECLARED_TARGET')
        self.assertEqual(report.a4_consistency,'EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT')
        with self.assertRaisesRegex(ValueError,'TARGET_EQUIVALENCE_NOT_CERTIFIED'):
            inspect_r3_joint_handoff_v28p0((a,b))
        checked=inspect_r3_joint_handoff_v28p0((a,b),require_single_target=False)
        self.assertFalse(checked['target_merge_certified'])

    def test_adjusted_and_standardized_direct_not_certified_equivalent(self):
        pstd=route_factorized()
        adjusted=route_adjusted(pstd)
        report=compare_r3_target_a4_v28p0(pstd,adjusted)
        self.assertEqual(report.relationship,'CROSS_TARGET_SEMANTICS_NOT_CERTIFIED_EQUIVALENT')
        self.assertEqual(report.a4_consistency,'EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT')
        self.assertFalse(report.same_target_certified)
        with self.assertRaisesRegex(ValueError,'TARGET_EQUIVALENCE_NOT_CERTIFIED'):
            inspect_r3_joint_handoff_v28p0((pstd,adjusted))

    def test_large_independent_laws_can_be_compared_without_expansion(self):
        study=st(300)
        a=route_factorized(study=study,ps=(Fraction(1,3),)*300,source_id='A')
        b=route_factorized(study=study,ps=(Fraction(1,3),)*300,source_id='B')
        info=compare_r3_target_a4_v28p0(a,b)
        self.assertEqual(info.left.marginal_law_comparison,'LARGE_INDEPENDENT_LAW')
        self.assertTrue(info.can_merge_as_one_symbolic_target)
        c=route_factorized(study=study,ps=(Fraction(1,4),)*300,source_id='C')
        self.assertEqual(compare_r3_target_a4_v28p0(a,c).a4_consistency,
                         'CONFLICTING_MARGINAL_TREATMENT_LAWS')

    def test_different_study_context_not_merged(self):
        a=route_factorized()
        b=route_factorized(study=st(6))
        report=compare_r3_target_a4_v28p0(a,b)
        self.assertEqual(report.relationship,'DIFFERENT_STUDY_OR_PROTOCOL')
        self.assertFalse(report.same_target_certified)

    def test_tampered_wrapper_route_fingerprint_and_nonpoint_fail_closed(self):
        a=route_factorized()
        with self.assertRaisesRegex(ValueError,'query_type/route mismatch'):
            inspect_r3_target_a4_v28p0(replace(a,query_type='FIXED_POLICY'))
        altered=replace(a.result.proofs[0],target_fingerprint='0'*64)
        with self.assertRaisesRegex(Exception,'CERTIFICATE_DIGEST_MISMATCH'):
            inspect_r3_target_a4_v28p0(replace(a,result=replace(a.result,proofs=(altered,))))
        with self.assertRaisesRegex(ValueError,'REQUIRES_VERIFIED_POINT'):
            inspect_r3_target_a4_v28p0(replace(a,status='NEEDS_INPUT',result=None))

    def test_non_r3_and_invalid_joint_batch_rejected(self):
        a=route_factorized()
        with self.assertRaisesRegex(ValueError,'TYPED_BOUNDED'):
            inspect_r3_joint_handoff_v28p0((a,))
        with self.assertRaisesRegex(ValueError,'TYPED_BOUNDED'):
            inspect_r3_joint_handoff_v28p0([a,a])
        with self.assertRaisesRegex(ValueError,'TYPED_BOUNDED'):
            inspect_r3_joint_handoff_v28p0(tuple(a for _ in range(17)))
        with self.assertRaisesRegex(ValueError,'SUPPORTS_ONLY_EXISTING_R3'):
            inspect_r3_target_a4_v28p0(replace(a,route='R1A_RANDOMIZED_ARM',result=None))


    def test_replay_approved_r3_full_policy_is_not_an_arm_target(self):
        from test_observational_r3_and_signature_diagnostics import (
            star5_obs,a5 as policy_a5,
        )
        from pfn_pipeline.identification_business import ObservationalPolicyInquiryV23
        pst,src,target=star5_obs()
        # Existing full-policy source admits some assignment; a correctly
        # requested supported assignment is selected from its exact law.
        supported=src.assignment_masses[0][0]
        from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
        policy=fixed_policy_target_from_context(pst,supported,authority='TRUSTED_FIXTURE')
        out=identify_network_business_query(ObservationalPolicyInquiryV23(
            pst,policy,src,policy_a5()))
        self.assertEqual(out.route,'R3_FULL_ASSIGNMENT')
        receipt=inspect_r3_target_a4_v28p0(out)
        self.assertEqual(receipt.target_class,'OBSERVATIONAL_FIXED_POLICY_VALUE')
        self.assertIsNone(receipt.cross_representation_fingerprints)
        self.assertEqual(receipt.marginal_law_comparison,'EXACT_FULL_LAW')

    def test_cross_adjustment_uses_distinct_target_class_even_if_law_agrees(self):
        from pfn_pipeline.identification_observational_nodewise_adjustment import (
            declare_nodewise_local_arm_population_v28,admit_nodewise_adjustment_a5_v28,
        )
        from pfn_pipeline.identification_business import ObservationalNodewiseAdjustedEffectsInquiryV28
        from pfn_pipeline.identification_composition import compile_effect_query_terms
        pstd=route_factorized()
        res=pstd.result
        study=res.study;sig=res.signature;requests=res.requests
        n=len(study.node_order)
        ps=res.source.treatment_one_probabilities
        adj={node:set() for node in study.node_order}
        for a,b in study.undirected_edges:adj[a].add(b);adj[b].add(a)
        x0=(0,)*n;x1=(1,)*n
        arms={term.coordinates for r in requests for term in compile_effect_query_terms(r)}
        covered={(node,x[node_index],sum(x[study.node_order.index(j)] for j in adj[node]),a,s)
                 for x in (x0,x1) for node,a,s in arms
                 for node_index in (study.node_order.index(node),)}
        source=declare_nodewise_local_arm_population_v28(study,sig,
            source_id='nodewise independent A4',provenance='synthetic exact population',
            feature_name='before_campaign_binary_feature',
            profiles=(('low','1/2',x0,ps),('high','1/2',x1,ps)),covered_cells=covered)
        def adm(name):
            return Assumption(name=name,source='demo_specification',confirmed=True,
                evidence=['Synthetic mathematical setting, NOT scientifically verified'])
        lic=admit_nodewise_adjustment_a5_v28(study,sig,
            feature_name='before_campaign_binary_feature',
            covered_nodes=tuple(sorted({n for n,_,_ in arms})),
            potential_outcome_exposure_sufficiency=adm('potential_outcome_exposure_sufficiency'),
            local_covariate_exposure_mean_exchangeability=adm('local_covariate_exposure_mean_exchangeability'))
        items=tuple(adm(n) for n in ('consistency','fixed_pretreatment_network','finite_conditional_first_moments'))
        nodewise=identify_network_business_query(ObservationalNodewiseAdjustedEffectsInquiryV28(
            study,source,items,sig,lic,requests))
        self.assertEqual(nodewise.status,'POINT')
        report=compare_r3_target_a4_v28p0(pstd,nodewise)
        self.assertEqual(report.a4_consistency,'EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT')
        self.assertEqual(report.relationship,'CROSS_TARGET_SEMANTICS_NOT_CERTIFIED_EQUIVALENT')
        self.assertFalse(report.can_merge_as_one_symbolic_target)

    def test_correlated_marginal_mixture_equals_full_law_not_independent_product(self):
        # Marginalizing common B creates correlated T even though P(T|B)
        # factorizes. Check equality against full-vector enumeration, and do
        # not assert equality with the independent law used by the first case.
        from pfn_pipeline.identification_observational_exposure_adjustment import (
            declare_stratified_observational_arm_population_v27p2,admit_exposure_adjustment_a5_v27p2,
        )
        from pfn_pipeline.identification_composition import compile_effect_query_terms
        case=route_factorized();st=case.result.study;sig=case.result.signature;requests=case.result.requests
        n=len(st.node_order)
        props_a=(Fraction(1,4),)*n;props_b=(Fraction(3,4),)*n
        arms={term.coordinates for r in requests for term in compile_effect_query_terms(r)}
        src=declare_stratified_observational_arm_population_v27p2(st,sig,
            source_id='B mix symbolic operator',provenance='synthetic g-formula setting',
            adjustment_variable='B_pre',
            strata=(('a','1/2',props_a),('b','1/2',props_b)),
            covered_cells=[(b,*arm) for b in ('a','b') for arm in sorted(arms)])
        def adm(name):
            return Assumption(name=name,source='demo_specification',confirmed=True,
                evidence=['Synthetic mathematical stipulation, not empirical evidence'])
        lic=admit_exposure_adjustment_a5_v27p2(st,sig,
            covered_nodes=tuple(sorted({n for n,_,_ in arms})),
            potential_outcome_exposure_sufficiency=adm('potential_outcome_exposure_sufficiency'),
            exposure_level_conditional_exchangeability=adm('exposure_level_conditional_exchangeability'))
        a5=tuple(adm(n) for n in ('consistency','fixed_pretreatment_network','finite_conditional_first_moments'))
        adjusted=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
            st,src,a5,sig,lic,requests))
        self.assertEqual(adjusted.status,'POINT')
        other=compare_r3_target_a4_v28p0(case,adjusted)
        self.assertEqual(other.a4_consistency,'CONFLICTING_MARGINAL_TREATMENT_LAWS')
        # Enumerate the same correlated mixture as a full observational law.
        full_law=[]
        for t in product((0,1),repeat=n):
            mass=sum((w*prod(p if x else 1-p for x,p in zip(t,probs))
                      for w,probs in ((Fraction(1,2),props_a),(Fraction(1,2),props_b))),Fraction(0))
            if mass:full_law.append((t,mass))
        full=declare_observational_population_v23(st,source_id='independent full mix',
            provenance='exact full marginal',assignment_masses=full_law)
        full_result=identify_network_business_query(ObservationalEffectsInquiryV26(
            st,full,case.result.assumptions,sig,requests))
        self.assertEqual(full_result.status,'POINT')
        report=compare_r3_target_a4_v28p0(full_result,adjusted)
        self.assertEqual(report.a4_consistency,'EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT')
        self.assertEqual(report.relationship,'CROSS_TARGET_SEMANTICS_NOT_CERTIFIED_EQUIVALENT')

    def test_public_lazy_api_matches_direct(self):
        from pfn_pipeline import inspect_r3_target_a4_v28p0 as exported
        self.assertIs(exported,inspect_r3_target_a4_v28p0)
        self.assertEqual(exported(route_factorized()).target_class,
                         'OBSERVATIONAL_P_STANDARDIZED_CONTRAST')


if __name__=='__main__':
    unittest.main()
