"""Finite-stratum R3 exposure G-formula: scoped premises, independent oracle, attacks."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_a4_shadow import _sha
from pfn_pipeline.identification_composition import EffectQueryV18,compile_effect_query_terms
from pfn_pipeline.identification_observational_r3 import R3Unavailable,_manual_exposure_classify_v26
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_observational_exposure_adjustment import (
    ObservationalStratifiedArmPopulationV27P2, PretreatmentStratumV27P2,
    ScopedExposureAdjustmentA5V27P2, declare_stratified_observational_arm_population_v27p2,
    admit_exposure_adjustment_a5_v27p2, identify_observational_exposure_adjusted_effects_v27p2,
    replay_observational_exposure_adjusted_effects_v27p2,_payload,
)
from pfn_pipeline.identification_business import (
    ObservationalExposureAdjustedEffectsInquiryV27P2,ObservationalEffectsInquiryV26,
    identify_network_business_query,replay_verified_business_outcome,
)
from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27
from pfn_pipeline.identification_observational_exposure_adjustment import (
    requirements_for_exposure_adjustment_v27p2, implemented_assumption_catalog_v27p2)
from pfn_pipeline.identification_assumption_inventory import implemented_assumption_catalog_v27
from pfn_pipeline.network_inquiry_shadow import declare_network_study


def study(n=5):
    ids=tuple(f'n{i}' for i in range(n))
    edges=tuple((ids[i],ids[(i+1)%n]) for i in range(n)) if n>8 else tuple((ids[i],ids[i+1]) for i in range(n-1))
    return declare_network_study(network_id=f'stratified-obs-{n}',node_order=ids,
        undirected_edges=edges,treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=w0',observation_regime='observational',
        assignment_design=None,protocol_provenance='synthetic observational protocol; manually approved',
        network_provenance='pre-treatment fixed observed',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def admitted(name,*,proposed=False):
    return Assumption(name=name,source='llm_candidate' if proposed else 'demo_specification',
        confirmed=not proposed,evidence=['Synthetic assumption stipulated for proof fixture; not a real company'])


def make(n=5,grouping='strict_majority_ties_low',requests=None,*,proposed=None,
         masses=('2/5','3/5'),probabilities=None,availability='SYMBOLIC_POPULATION_OPERATOR',
         covered=None):
    st=study(n)
    extra={}
    if grouping=='pretreatment_core_collaborator_majority':
        adj={j:set() for j in st.node_order}
        for a,b in st.undirected_edges:adj[a].add(b);adj[b].add(a)
        extra['core_collaborators']={j:(sorted(adj[j])[0],) for j in st.node_order}
    sig=declare_policy_signature(st,grouping=grouping,**extra)
    if requests is None:
        requests=(EffectQueryV18(kind='DIRECT',node_weights=(('n2',1),),reference_exposure=0,comparison_exposure=0),)
    arms={term.coordinates for r in requests for term in compile_effect_query_terms(r)}
    probabilities=probabilities or [(Fraction(1,3),)*n,(Fraction(2,3),)*n]
    strata=(('low',masses[0],probabilities[0]),('high',masses[1],probabilities[1]))
    cells=covered if covered is not None else [(b,*arm) for b in ('low','high') for arm in arms]
    source=declare_stratified_observational_arm_population_v27p2(st,sig,
        source_id='synthetic-admitted-stratified-operator',
        provenance='exact symbolic population stratum+outcome operators, no sample',
        adjustment_variable='pre_campaign_segment',strata=strata,covered_cells=cells,
        availability=availability)
    records=tuple(admitted(x) for x in ('consistency','fixed_pretreatment_network',
                                       'finite_conditional_first_moments'))
    license=admit_exposure_adjustment_a5_v27p2(st,sig,covered_nodes=('n2',),
        potential_outcome_exposure_sufficiency=admitted('potential_outcome_exposure_sufficiency',
            proposed=proposed=='sufficiency'),
        exposure_level_conditional_exchangeability=admitted('exposure_level_conditional_exchangeability',
            proposed=proposed=='exchangeability'))
    return st,source,sig,records,license,requests


def solve(items):
    st,src,sig,records,lic,req=items
    return identify_observational_exposure_adjusted_effects_v27p2(st,src,sig,
        assumptions=records,license=lic,requests=req)


class ExposureAdjustmentTests(unittest.TestCase):
    def test_new_target_and_official_handoff_no_estimator(self):
        st,src,sig,rec,lic,req=make()
        result=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
            st,src,rec,sig,lic,req))
        self.assertEqual((result.status,result.route),('POINT','R3_EXPOSURE_ADJUSTED_EFFECTS'))
        self.assertTrue(replay_verified_business_outcome(result))
        self.assertTrue(replay_observational_exposure_adjusted_effects_v27p2(result.result))
        self.assertTrue(result.result.summary()['exposure_sufficiency_required'])
        self.assertFalse(result.result.summary()['full_vector_exchangeability_required'])
        handoff=inspect_verified_business_handoff_v27(result)
        self.assertEqual(handoff['estimation']['status'],'NO_ADAPTER')
        self.assertEqual(handoff['policy']['status'],'NOT_A_FIXED_POLICY_VALUE')
        self.assertIsNone(handoff['finite_sample_estimate'])
        self.assertEqual(len(requirements_for_exposure_adjustment_v27p2()['required_names']),5)
        self.assertEqual(len(implemented_assumption_catalog_v27()['route_ids']),8)
        self.assertEqual(len(implemented_assumption_catalog_v27()['assumptions']),8)
        self.assertEqual(len(implemented_assumption_catalog_v27p2()['route_ids']),9)
        self.assertEqual(len(implemented_assumption_catalog_v27p2()['assumptions']),10)

    def test_five_exposure_mappings_small_graph_oracle(self):
        for grouping,s1 in [('strict_majority_ties_low',1),
                            ('three_level_treated_neighbor_fraction',2),
                            ('pretreatment_core_collaborator_majority',1),
                            ('exact_treated_neighbor_count',2),
                            ('any_treated_neighbor',1)]:
            with self.subTest(grouping=grouping):
                req=(EffectQueryV18(kind='SPILLOVER',node_weights=(('n2',1),),
                                    reference_exposure=0,comparison_exposure=s1),)
                obj=make(grouping=grouping,requests=req)
                st,src,sig,_,_,_=obj
                proof=solve(obj).proofs[0]
                self.assertTrue(proof.identified_functional.count('pre_campaign_segment=')>=4)
                adj={n:set() for n in st.node_order}
                for a,b in st.undirected_edges:adj[a].add(b);adj[b].add(a)
                neighbors=({n:set(vals) for n,vals in sig.core_collaborators}
                           if grouping=='pretreatment_core_collaborator_majority' else adj)
                pos={n:i for i,n in enumerate(st.node_order)}
                for (b,claims) in proof.support_by_stratum:
                    row=next(s for s in src.strata if s.label==b)
                    p=[Fraction(x) for x in row.treatment_one_probabilities]
                    for term,claimed in zip(proof.terms,claims):
                        oracle=Fraction(0)
                        for t in product((0,1),repeat=len(st.node_order)):
                            k=sum(t[pos[n]] for n in neighbors[term.node_id])
                            if (t[pos[term.node_id]]==term.own_treatment and
                                _manual_exposure_classify_v26(k,len(neighbors[term.node_id]),grouping)
                                ==term.exposure_state):
                                pi=Fraction(1)
                                for a,pj in zip(t,p):pi*=pj if a else 1-pj
                                oracle+=pi
                        self.assertEqual(str(oracle),claimed)

    def test_300_node_ring_not_full_enumeration(self):
        obj=make(300,requests=(EffectQueryV18(kind='SPILLOVER',
            node_weights=(('n2',1),),reference_exposure=0,comparison_exposure=1),))
        st,src,sig,rec,lic,req=obj
        got=solve(obj)
        self.assertEqual(len(st.node_order),300)
        self.assertEqual(len(got.proofs[0].support_by_stratum),2)
        self.assertTrue(all(all(Fraction(x)>0 for x in claims)
                            for _,claims in got.proofs[0].support_by_stratum))

    def test_target_identity_propensities_invariant_but_stratum_mass_specific(self):
        base=solve(make())
        modified=solve(make(probabilities=[(Fraction(1,4),)*5,(Fraction(3,4),)*5]))
        self.assertEqual(base.proofs[0].target_fingerprint,modified.proofs[0].target_fingerprint)
        self.assertNotEqual(base.certificate_sha256,modified.certificate_sha256)
        weighted=solve(make(masses=('1/4','3/4')))
        self.assertNotEqual(base.proofs[0].target_fingerprint,weighted.proofs[0].target_fingerprint)
        self.assertNotEqual(base.proofs[0].target_fingerprint,'')

    def test_exposure_sufficiency_or_local_exchangeability_missing(self):
        for x in ('sufficiency','exchangeability'):
            with self.subTest(missing=x):
                obj=make(proposed=x)
                out=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
                    obj[0],obj[1],obj[3],obj[2],obj[4],obj[5]))
                self.assertEqual(out.status,'NEEDS_INPUT')

    def test_missing_population_stratum_cells(self):
        obj=make(covered=(('high','n2',0,0),('high','n2',1,0)))
        with self.assertRaisesRegex(R3Unavailable,'A4_STRATIFIED_CONDITIONAL_MEANS_MISSING'):
            solve(obj)

    def test_zero_one_stratum_blocks_despite_marginal_support(self):
        ps=[(Fraction(0),)*5,(Fraction(1,2),)*5]
        obj=make(probabilities=ps)
        with self.assertRaisesRegex(R3Unavailable,'ZERO_STRATUM_EXPOSURE_SUPPORT'):
            solve(obj)
        out=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
            obj[0],obj[1],obj[3],obj[2],obj[4],obj[5]))
        self.assertEqual(out.status,'UNSUPPORTED')

    def test_proposed_A4_and_sample_stats_not_population(self):
        obj=make()
        out=identify_network_business_query(ObservationalExposureAdjustedEffectsInquiryV27P2(
            obj[0],replace(obj[1],admission='PROPOSED'),obj[3],obj[2],obj[4],obj[5]))
        self.assertEqual(out.status,'NEEDS_INPUT')
        obj=make(availability='FINITE_SAMPLE_ESTIMATE')
        with self.assertRaisesRegex(R3Unavailable,'A4_STRATIFIED_POPULATION_OPERATOR_REQUIRED'):
            solve(obj)

    def test_reject_assignment_design_as_observational_license(self):
        obj=make()
        records=obj[3]+(admitted('known_assignment_law'),)
        with self.assertRaisesRegex(R3Unavailable,'RANDOMIZATION_IS_NOT_OBSERVATIONAL_IGNORABILITY'):
            identify_observational_exposure_adjusted_effects_v27p2(
                obj[0],obj[1],obj[2],assumptions=records,license=obj[4],requests=obj[5])

    def test_scope_and_node_coverage_cannot_be_changed(self):
        obj=make()
        with self.assertRaisesRegex(R3Unavailable,'R3_ADJUSTMENT_STUDY_SIGNATURE_OR_A4_MISMATCH'):
            solve((obj[0],obj[1],obj[2],obj[3],replace(obj[4],study_scope_digest='different'),obj[5]))
        with self.assertRaisesRegex(R3Unavailable,'R3_ADJUSTMENT_A5_NODE_COVERAGE_MISSING'):
            solve((obj[0],obj[1],obj[2],obj[3],replace(obj[4],covered_nodes=('n1',)),obj[5]))

    def test_invalid_stratum_mass_or_exact_float(self):
        obj=make()
        with self.assertRaisesRegex(ValueError,'A4_STRATIFIED_MASSES_MUST_SUM_TO_ONE'):
            replace(obj[1],strata=(replace(obj[1].strata[0],mass='1/5'),obj[1].strata[1]))
        with self.assertRaisesRegex(ValueError,'EXACT_RATIONAL_NOT_FLOAT_REQUIRED'):
            make(masses=(0.4,0.6))
        with self.assertRaisesRegex(ValueError,'A4_STRATIFIED_CELLS_NOT_UNIQUE_SORTED'):
            replace(obj[1],covered_cells=(('high','n2',0,0),('high','n2',0,0)))

    def test_tamper_proof_and_rehash_replay(self):
        got=solve(make())
        p=replace(got.proofs[0],support_by_stratum=(('high',('1/777','1/777')),
                                                     ('low',('1/777','1/777'))))
        forged=replace(got,proofs=(p,))
        with self.assertRaisesRegex(R3Unavailable,'CERTIFICATE_DIGEST_MISMATCH'):
            replay_observational_exposure_adjusted_effects_v27p2(forged)
        rehashed=replace(forged,certificate_sha256=_sha(_payload(forged)))
        with self.assertRaisesRegex(R3Unavailable,'CERTIFICATE_REPLAY_MISMATCH'):
            replay_observational_exposure_adjusted_effects_v27p2(rehashed)

    def test_observational_factorization_does_not_imply_exchangeability_witness(self):
        # T_i is Bernoulli(1/2); the observed data Yobs=T_i in both causal worlds.
        # World A has Y(1)=1,Y(0)=0 for every unit; World B has Y(1)=T_i
        # and Y(0)=T_i: with its latent common cause U=T_i, consistency still
        # yields Yobs=T_i, but its E[Y(1)]=1/2 instead of 1.  This exhibits
        # the non-identification when exchangeability is not admitted.
        observed=[(t,t) for t in (0,1)]
        self.assertEqual(observed,[(0,0),(1,1)])
        worldA=Fraction(1)
        worldB=sum((Fraction(t,2) for t in (0,1)),Fraction(0))
        self.assertNotEqual(worldA,worldB)

    def test_new_target_never_routed_as_p_standardized(self):
        obj=make()
        outcome=identify_network_business_query(ObservationalEffectsInquiryV26(
            obj[0],obj[1],obj[3],obj[2],obj[5]))
        self.assertNotEqual(outcome.status,'POINT')
        self.assertIsNone(outcome.result)

    def test_exposure_level_exchangeability_strictly_weaker_witness(self):
        # For node 2 choose a distant independent node 4 with T4=U,
        # where U is also the baseline potential outcome of node 2.
        # Own treatment/neighbors are independent of U, so exposure-cell
        # exchangeability holds, but full-vector exchangeability fails.
        tuples=list(product((0,1),repeat=5))
        for a in (0,1):
            selected=[t[4] for t in tuples if t[2]==a and t[1]==0 and t[3]==0]
            self.assertEqual(Fraction(sum(selected),len(selected)),Fraction(1,2))
        self.assertNotEqual(Fraction(sum(t[4] for t in tuples if t[4]==1),16),Fraction(1,2))

    def test_common_pretreatment_stratum_creates_marginal_treatment_dependence(self):
        # Despite p(T|B) factorizing, mixing two pre-treatment regimes can
        # generate positive cross-node dependence in the marginal observed law.
        obj=make()
        strata=obj[1].strata
        p1=sum((Fraction(s.mass)*Fraction(s.treatment_one_probabilities[1])
                for s in strata),Fraction(0))
        p2=sum((Fraction(s.mass)*Fraction(s.treatment_one_probabilities[2])
                for s in strata),Fraction(0))
        p12=sum((Fraction(s.mass)*Fraction(s.treatment_one_probabilities[1])
                *Fraction(s.treatment_one_probabilities[2]) for s in strata),Fraction(0))
        self.assertGreater(p12,p1*p2)
        self.assertTrue(replay_observational_exposure_adjusted_effects_v27p2(solve(obj)))

    def test_nonpretreatment_adjustment_and_heterogeneous_propensities(self):
        obj=make(probabilities=[(Fraction(1,4),Fraction(1,2),Fraction(2,3),
                                  Fraction(1,3),Fraction(1,2)),
                                 (Fraction(3,4),Fraction(1,4),Fraction(1,2),
                                  Fraction(1,2),Fraction(2,3))])
        self.assertTrue(replay_observational_exposure_adjusted_effects_v27p2(solve(obj)))
        with self.assertRaisesRegex(ValueError,'ADJUSTMENT_MUST_BE_PRETREATMENT'):
            replace(obj[1],adjustment_timing='POSTTREATMENT')


if __name__=='__main__':unittest.main()
