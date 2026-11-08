"""Independent small-enumeration and negative safety oracle for mixture observational p.
All inputs are synthetic declared population operators, NOT measured causal data.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from fractions import Fraction as F
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_business import (
    ObservationalEffectsInquiryV26, identify_network_business_query,
    replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_observational_r3 import (
    declare_observational_population_v23, R3Unavailable,
)
from pfn_pipeline.identification_observational_effects import identify_observational_effects_v26
from pfn_pipeline.identification_observational_mixture_a4 import (
    ObservationalMixtureArmPopulationV28P1, _canonical_components,
    declare_observational_mixture_arm_population_v28p1,
    identify_observational_mixture_effects_v28p1,
    replay_observational_mixture_effects_v28p1,
)
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_r3_target_a4_audit import compare_r3_target_a4_v28p0
from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27
from pfn_pipeline.network_inquiry_shadow import declare_network_study


def study(n=5):
    ids=tuple(f'n{i}' for i in range(n))
    edges=tuple((ids[i],ids[(i+1)%n]) for i in range(n)) if n>6 else tuple((ids[i],ids[i+1]) for i in range(n-1))
    return declare_network_study(network_id=f'correlated-observational-{n}',node_order=ids,
        undirected_edges=edges,treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=w0',
        observation_regime='observational',assignment_design=None,
        protocol_provenance='pre-registered synthetic observational example',
        network_provenance='fixed pretreatment graph',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def assumptions(*, missing=None, proposed=None):
    return tuple(Assumption(name=x,source='llm_candidate' if x==proposed else 'demo_specification',
                            confirmed=x!=proposed,evidence=['hypothetical assumption; not empirically proven'])
                 for x in ('full_vector_conditional_exchangeability','consistency',
                           'fixed_pretreatment_network','finite_conditional_first_moments') if x!=missing)


def query(*,kind='DIRECT',s0=0,s1=0,node='n2'):
    return EffectQueryV18(kind=kind,node_weights=((node,1),),reference_exposure=s0,
                          comparison_exposure=s1)


def prepare(n=5,*,grouping='strict_majority_ties_low',mix=None,requests=None,admission='ADMITTED',
            availability='SYMBOLIC_POPULATION_OPERATOR',source_id='correlated-symbolic-population',
            covered=None,a5=None):
    st=study(n)
    kwargs = {}
    if grouping=='pretreatment_core_collaborator_majority':
        nbr={node:[] for node in st.node_order}
        for a,b in st.undirected_edges:
            nbr[a].append(b);nbr[b].append(a)
        kwargs['core_collaborators']={n:(nbr[n][0],) for n in st.node_order}
    sig=declare_policy_signature(st,grouping=grouping,**kwargs)
    if mix is None:
        mix=((F(1,3),(F(1,4),)*n),(F(2,3),(F(3,4),)*n))
    if requests is None:
        requests=(query(),)
    arms = covered if covered is not None else {
        t.coordinates for q in requests for t in compile_effect_query_terms(q)}
    src=declare_observational_mixture_arm_population_v28p1(
        st,sig,source_id=source_id,provenance='synthetic symbolic joint population (not sample)',
        components=mix,covered_arms=arms,admission=admission,availability=availability)
    return st,src,sig,assumptions() if a5 is None else a5,requests


def full_oracle(st,src):
    """Independent enumeration over all assignments, not local polynomial code."""
    rows=[]
    for allocation in product((0,1),repeat=len(st.node_order)):
        mass=F(0)
        for w,ps in src.components:
            val=F(w)
            for treated,p in zip(allocation,ps):
                val *= F(p) if treated else 1-F(p)
            mass += val
        if mass: rows.append((allocation,mass))
    return declare_observational_population_v23(st,source_id='exact-independent-vector-oracle',
        provenance='enumerated symbolic population law',assignment_masses=rows)


class R3CorrelatedObservationalMixtureTests(unittest.TestCase):
    def test_five_exposures_vs_full_assignment_independent_oracle(self):
        for grouping,upper in [('strict_majority_ties_low',1),
                               ('three_level_treated_neighbor_fraction',2),
                               ('pretreatment_core_collaborator_majority',1),
                               ('exact_treated_neighbor_count',2),
                               ('any_treated_neighbor',1)]:
            with self.subTest(grouping=grouping):
                a=prepare(grouping=grouping,requests=(query(kind='SPILLOVER',s1=upper),))
                value=identify_observational_mixture_effects_v28p1(
                    a[0],a[1],a[2],assumptions=a[3],requests=a[4])
                self.assertTrue(replay_observational_mixture_effects_v28p1(value))
                oracle=identify_observational_effects_v26(a[0],full_oracle(a[0],a[1]),a[2],
                    assumptions=a[3],requests=a[4])
                self.assertEqual(value.proofs[0].arm_support,oracle.proofs[0].arm_support)
                self.assertEqual(value.proofs[0].identified_functional,
                                 oracle.proofs[0].identified_functional)
                self.assertTrue(compare_r3_target_a4_v28p0(
                    identify_network_business_query(ObservationalEffectsInquiryV26(
                        a[0],a[1],a[3],a[2],a[4])),
                    identify_network_business_query(ObservationalEffectsInquiryV26(
                        a[0],full_oracle(a[0],a[1]),a[3],a[2],a[4]))
                    ).can_merge_as_one_symbolic_target)

    def test_300_node_correlated_ring_and_handoff_no_adapter(self):
        a=prepare(300,requests=(query(kind='SPILLOVER',node='n151',s1=1),))
        out=identify_network_business_query(ObservationalEffectsInquiryV26(
            a[0],a[1],a[3],a[2],a[4]))
        self.assertEqual(out.status,'POINT')
        self.assertTrue(replay_verified_business_outcome(out))
        self.assertEqual(out.result.summary()['node_count'],300)
        # own treated and two treated neighbors: 1/3*(1/4)^3 + 2/3*(3/4)^3 = 55/192
        self.assertEqual(out.result.proofs[0].arm_support[1],'55/192')
        self.assertEqual(inspect_verified_business_handoff_v27(out)['estimation']['status'],'NO_ADAPTER')
        self.assertFalse(out.result.summary()['exposure_sufficiency_required'])

    def test_mixture_creates_marginal_treatment_dependence(self):
        a=prepare()
        # p_i marginal= (1/3)(1/4) + (2/3)(3/4) = 7/12
        p=F(7,12)
        joint=F(1,3)*F(1,4)**2+F(2,3)*F(3,4)**2
        self.assertNotEqual(joint,p*p)
        self.assertEqual(joint,F(19,48))

    def test_components_canonical_permutation_and_duplicate_merge(self):
        base=prepare()[1]
        shuffled=prepare(mix=((F(2,3),(F(3,4),)*5),
                              (F(1,6),(F(1,4),)*5),(F(1,6),(F(1,4),)*5)))[1]
        self.assertEqual(base.components,shuffled.components)
        self.assertEqual(base.observational_law_fingerprint,
                         shuffled.observational_law_fingerprint)

    def test_source_invariance_and_law_changes_target(self):
        a=prepare();b=prepare(source_id='different-A4')
        va=identify_observational_mixture_effects_v28p1(a[0],a[1],a[2],assumptions=a[3],requests=a[4])
        vb=identify_observational_mixture_effects_v28p1(b[0],b[1],b[2],assumptions=b[3],requests=b[4])
        self.assertEqual(va.proofs[0].target_fingerprint,vb.proofs[0].target_fingerprint)
        self.assertNotEqual(va.certificate_sha256,vb.certificate_sha256)
        c=prepare(mix=((F(1,2),(F(1,4),)*5),(F(1,2),(F(3,4),)*5)))
        vc=identify_observational_mixture_effects_v28p1(c[0],c[1],c[2],assumptions=c[3],requests=c[4])
        self.assertNotEqual(va.proofs[0].target_fingerprint,vc.proofs[0].target_fingerprint)

    def test_missing_A5_safely_blocked(self):
        for missing in ('full_vector_conditional_exchangeability','consistency'):
            with self.subTest(missing=missing):
                a=prepare(a5=assumptions(missing=missing))
                out=identify_network_business_query(ObservationalEffectsInquiryV26(
                    a[0],a[1],a[3],a[2],a[4]))
                self.assertNotEqual(out.status,'POINT')
        a=prepare(a5=assumptions(proposed='full_vector_conditional_exchangeability'))
        out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        self.assertNotEqual(out.status,'POINT')

    def test_proposed_or_sample_A4_safely_blocked(self):
        for kw in ({'admission':'PROPOSED'},{'availability':'FINITE_SAMPLE_ESTIMATE'}):
            with self.subTest(kw=kw):
                a=prepare(**kw)
                out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
                self.assertEqual(out.status,'NEEDS_INPUT')

    def test_positive_arm_missing_symbolic_mean_rejected(self):
        a=prepare(covered={( 'n2',1,0)})
        out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        self.assertEqual(out.status,'NEEDS_INPUT')
        self.assertIn('A4_',out.reason_code)

    def test_zero_signature_support_rejected(self):
        a=prepare(mix=((F(1,2),(0,)*5),(F(1,2),(1,)*5)),
                  requests=(query(kind='SPILLOVER',s1=1),))
        out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        self.assertEqual(out.status,'UNSUPPORTED')
        self.assertEqual(out.reason_code,'ZERO_OBSERVATIONAL_ARM_SUPPORT')

    def test_non_normalized_float_and_resource_limits(self):
        for mix in (((F(1,4),(F(1,3),)*5),),
                    ((F(1,2),(0.5,)*5),(F(1,2),(F(1,4),)*5)),
                    ((F(1,2),(F(1,4),)*5),(F(1,2),(F(1,4),)*4))):
            with self.subTest(mix=mix):
                with self.assertRaises(ValueError):prepare(mix=mix)
        with self.assertRaises(ValueError):
            prepare(mix=tuple((F(1,17),(F(i,17),)*5) for i in range(17)))

    def test_undefined_even_unused_A4_arm_rejected(self):
        a=prepare(covered={('n2',1,0),('n2',0,0),('n2',1,1),('n2',0,1),('n0',0,777)})
        out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        self.assertNotEqual(out.status,'POINT')

    def test_tampered_certificate_and_business_wrapper_fail_closed(self):
        a=prepare()
        out=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        self.assertEqual(out.status,'POINT')
        for bad in (replace(out.result,certificate_sha256='0'*64),
                    replace(out.result,proofs=())):
            with self.assertRaises((R3Unavailable,ValueError)):
                replay_observational_mixture_effects_v28p1(bad)
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(replace(out,query_type='FIXED_POLICY'))

    def test_small_graph_other_mixture_representation_exact_audit(self):
        a=prepare()
        b=prepare(mix=((F(1,2),(F(1,2),)*5),(F(1,2),(F(1,2),)*5)))
        r1=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        r2=identify_network_business_query(ObservationalEffectsInquiryV26(b[0],b[1],b[3],b[2],b[4]))
        cmp=compare_r3_target_a4_v28p0(r1,r2)
        self.assertFalse(cmp.can_merge_as_one_symbolic_target)
        self.assertEqual(cmp.a4_consistency,'CONFLICTING_MARGINAL_TREATMENT_LAWS')

    def test_large_mixture_different_models_not_certified_same(self):
        a=prepare(300)
        b=prepare(300,mix=((F(1,2),(F(1,4),)*300),(F(1,2),(F(3,4),)*300)),source_id='different-source-id')
        ra=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        rb=identify_network_business_query(ObservationalEffectsInquiryV26(b[0],b[1],b[3],b[2],b[4]))
        cmp=compare_r3_target_a4_v28p0(ra,rb)
        self.assertFalse(cmp.can_merge_as_one_symbolic_target)
        self.assertEqual(cmp.a4_consistency,'MARGINAL_LAW_EQUIVALENCE_UNRESOLVED')

    def test_large_identical_declared_mixture_models_audited(self):
        a=prepare(300)
        b=prepare(300,source_id='an-independent-review')
        ra=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        rb=identify_network_business_query(ObservationalEffectsInquiryV26(b[0],b[1],b[3],b[2],b[4]))
        cmp=compare_r3_target_a4_v28p0(ra,rb)
        self.assertTrue(cmp.can_merge_as_one_symbolic_target)
        self.assertEqual(cmp.a4_consistency,'IDENTICAL_DECLARED_MODEL_NONENUMERATED')
        self.assertFalse(cmp.summary()['outcome_mean_operator_value_equivalence_proven'])

    def test_source_id_reuse_with_conflicting_law_is_blocked(self):
        a=prepare()
        b=prepare(mix=((F(1,2),(F(1,4),)*5),(F(1,2),(F(3,4),)*5)))
        ra=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        rb=identify_network_business_query(ObservationalEffectsInquiryV26(b[0],b[1],b[3],b[2],b[4]))
        audit=compare_r3_target_a4_v28p0(ra,rb)
        self.assertEqual(audit.relationship,'CONFLICTING_OR_UNRESOLVED_A4_SOURCE')

    def test_single_component_mixture_reduces_to_independent_law(self):
        from pfn_pipeline.identification_observational_factorized_a4 import (
            declare_observational_factorized_arm_population_v27p1)
        from pfn_pipeline.identification_r3_target_a4_audit import compare_r3_target_a4_v28p0
        a=prepare(mix=((F(1),(F(1,3),)*5),))
        old=declare_observational_factorized_arm_population_v27p1(
            a[0],a[2],source_id='factorized-independent',provenance='declared population',
            treatment_one_probabilities=(F(1,3),)*5,covered_arms=a[1].covered_arms)
        new=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],a[1],a[3],a[2],a[4]))
        prev=identify_network_business_query(ObservationalEffectsInquiryV26(a[0],old,a[3],a[2],a[4]))
        audit=compare_r3_target_a4_v28p0(new,prev)
        self.assertTrue(audit.can_merge_as_one_symbolic_target)

    def test_finite_mixture_has_immutable_and_canonical_population_cells(self):
        a=prepare()
        bad=asdict(a[1]);bad['components']=list(bad['components'])
        with self.assertRaises(ValueError):ObservationalMixtureArmPopulationV28P1(**bad)
        bad=asdict(a[1]);bad['covered_arms']=(('n2',0,0),('n2',0,0))
        with self.assertRaises(ValueError):ObservationalMixtureArmPopulationV28P1(**bad)



if __name__=='__main__':unittest.main()
