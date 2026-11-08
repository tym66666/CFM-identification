"""v2.8 independent arithmetic, scoped A4/A5, target identity, route/handoff attacks."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_composition import EffectQueryV18, compile_effect_query_terms
from pfn_pipeline.identification_observational_r3 import R3Unavailable, _manual_exposure_classify_v26
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study
from pfn_pipeline.identification_observational_nodewise_adjustment import (
    NodewisePretreatmentProfileV28, NodewiseLocalArmPopulationV28,
    declare_nodewise_local_arm_population_v28, admit_nodewise_adjustment_a5_v28,
    identify_observational_nodewise_effects_v28, replay_observational_nodewise_effects_v28,
    requirements_for_nodewise_adjustment_v28, implemented_assumption_catalog_v28,
)
from pfn_pipeline.identification_business import (
    ObservationalNodewiseAdjustedEffectsInquiryV28, VerifiedBusinessOutcomeV21,
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27


def study(n=5):
    ids=tuple(f'n{i}' for i in range(n))
    edges=(tuple((ids[i],ids[(i+1)%n]) for i in range(n)) if n>=9
           else tuple((ids[i],ids[i+1]) for i in range(n-1)))
    return declare_network_study(network_id=f'v28-nodewise-{n}',node_order=ids,
        undirected_edges=edges,treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W=w0',observation_regime='observational',
        assignment_design=None,protocol_provenance='synthetic observational protocol',
        network_provenance='fixed pretreatment graph',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def admitted(name,proposed=False):
    return Assumption(name=name,source='llm_candidate' if proposed else 'demo_specification',
        confirmed=not proposed,evidence=['Synthetic scientific stipulation; NOT real-world evidence'])


def vectors(n):
    if n==5:
        xs=((0,1,0,0,0),(1,1,0,0,0),(0,1,1,1,0))
    else:
        xs=(tuple(i%2 for i in range(n)),
            tuple((i%2 if i!=n-1 else 1-(i%2)) for i in range(n)),
            tuple(1 for _ in range(n)))
    return xs


def make(n=5,grouping='strict_majority_ties_low', requests=None,
         *, proposed=None, masses=('1/5','2/5','2/5'), probabilities=None,
         missing=False,sample=False, profile_zero=False,license_nodes=None):
    st=study(n)
    kwargs={}
    if grouping=='pretreatment_core_collaborator_majority':
        adj={i:set() for i in st.node_order}
        for a,b in st.undirected_edges:
            adj[a].add(b);adj[b].add(a)
        kwargs['core_collaborators']={i:(sorted(adj[i])[0],) for i in st.node_order}
    sig=declare_policy_signature(st,grouping=grouping,**kwargs)
    if requests is None:
        requests=(EffectQueryV18(kind='DIRECT',node_weights=(('n2',1),),
                                 reference_exposure=0,comparison_exposure=0),)
    xs=vectors(n)
    ps=probabilities or ((Fraction(1,3),)*n,(Fraction(2,3),)*n,(Fraction(1,2),)*n)
    if profile_zero:
        ps=(tuple(Fraction(0) if j==2 else Fraction(1,3) for j in range(n)),*ps[1:])
    profiles=tuple((f'p{k}',m,x,p) for k,(m,x,p) in enumerate(zip(masses,xs,ps)))
    neighbors={i:set() for i in st.node_order}
    for a,b in st.undirected_edges:
        neighbors[a].add(b);neighbors[b].add(a)
    arms={term.coordinates for q in requests for term in compile_effect_query_terms(q)}
    cells={(n, x[st.node_order.index(n)],sum(x[st.node_order.index(j)] for j in neighbors[n]),a,s)
        for _,_,x,_ in profiles for n,a,s in arms}
    if missing:
        cells={c for c in cells if not (c[0]=='n2' and c[3]==1)}
    source=declare_nodewise_local_arm_population_v28(st,sig,
        source_id='v28-typed-symbolic-population',
        provenance='synthetic P(X),P(T|X),E[Yobs|Ti,Si,Ci,W] symbolic operators',
        feature_name='employee_pre_AI_skill', profiles=profiles,covered_cells=cells,
        availability='FINITE_SAMPLE_ESTIMATE' if sample else 'SYMBOLIC_POPULATION_OPERATOR')
    required_nodes=license_nodes or tuple(sorted({n for n,_,_ in arms}))
    lic=admit_nodewise_adjustment_a5_v28(st,sig,feature_name='employee_pre_AI_skill',
        covered_nodes=required_nodes,
        potential_outcome_exposure_sufficiency=admitted('potential_outcome_exposure_sufficiency',
            proposed=proposed=='sufficiency'),
        local_covariate_exposure_mean_exchangeability=admitted('local_covariate_exposure_mean_exchangeability',
            proposed=proposed=='exchangeability'))
    records=tuple(admitted(x) for x in ('consistency','fixed_pretreatment_network',
                                        'finite_conditional_first_moments'))
    return st,source,sig,records,lic,requests


def solve(items):
    st,src,sig,assumptions,license,requests=items
    return identify_observational_nodewise_effects_v28(st,src,sig,
        assumptions=assumptions,license=license,requests=requests)


def routed(items):
    st,src,sig,assumptions,license,requests=items
    return identify_network_business_query(ObservationalNodewiseAdjustedEffectsInquiryV28(
        st,src,assumptions,sig,license,requests))


class NodewiseV28Tests(unittest.TestCase):
    def test_replay_and_business_handoff_no_numeric_estimator(self):
        result=routed(make())
        self.assertEqual((result.status,result.route),
            ('POINT','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'))
        self.assertTrue(replay_verified_business_outcome(result))
        self.assertTrue(replay_observational_nodewise_effects_v28(result.result))
        h=inspect_verified_business_handoff_v27(result)
        self.assertEqual(h['estimation']['status'],'NO_ADAPTER')
        self.assertEqual(h['policy']['status'],'NOT_A_FIXED_POLICY_VALUE')
        self.assertIsNone(h['finite_sample_estimate'])
        self.assertEqual(len(requirements_for_nodewise_adjustment_v28()['required_names']),5)
        self.assertEqual((len(implemented_assumption_catalog_v28()['route_ids']),
                          len(implemented_assumption_catalog_v28()['assumptions'])),(10,11))
        self.assertIn('neighbor_positive',result.result.proofs[0].identified_functional)

    def test_five_exposure_rules_with_full_vector_independent_oracle(self):
        for grouping,target_s in [('strict_majority_ties_low',1),
                                  ('three_level_treated_neighbor_fraction',2),
                                  ('pretreatment_core_collaborator_majority',1),
                                  ('exact_treated_neighbor_count',2),
                                  ('any_treated_neighbor',1)]:
            with self.subTest(grouping=grouping):
                req=(EffectQueryV18(kind='SPILLOVER',node_weights=(('n2',1),),
                    reference_exposure=0,comparison_exposure=target_s),)
                st,src,sig,assumptions,lic,r=make(grouping=grouping,requests=req)
                proof=solve((st,src,sig,assumptions,lic,r)).proofs[0]
                adj={node:set() for node in st.node_order}
                for a,b in st.undirected_edges:adj[a].add(b);adj[b].add(a)
                refs=({node:set(ns) for node,ns in sig.core_collaborators}
                    if grouping=='pretreatment_core_collaborator_majority' else adj)
                ids={node:i for i,node in enumerate(st.node_order)}
                for n,a,s,rows in proof.support_by_term:
                    masses={};joint={}
                    for profile in src.profiles:
                        cov=(profile.node_binary_features[ids[n]],
                             sum(profile.node_binary_features[ids[j]] for j in adj[n]))
                        masses[cov]=masses.get(cov,Fraction(0))+Fraction(profile.mass)
                        p=[Fraction(x) for x in profile.treatment_one_probabilities]
                        for alloc in product((0,1),repeat=len(st.node_order)):
                            k=sum(alloc[ids[j]] for j in refs[n])
                            if (alloc[ids[n]]==a and
                                _manual_exposure_classify_v26(k,len(refs[n]),grouping)==s):
                                w=Fraction(profile.mass)
                                for t,pj in zip(alloc,p):w*=pj if t else 1-pj
                                joint[cov]=joint.get(cov,Fraction(0))+w
                    self.assertEqual(rows,tuple((x,k,str(masses[(x,k)]),
                        str(joint.get((x,k),Fraction(0))/masses[(x,k)]))
                        for x,k in sorted(masses)))

    def test_300_node_graph_and_different_node_adjustment_cells(self):
        req=(EffectQueryV18(kind='TOTAL',node_weights=(('n2','1/2'),('n3','1/2')),
            reference_exposure=0,comparison_exposure=1,
            cohort_authority='TRUSTED_FIXTURE',cohort_evidence='Synthetic registered team, before treatment'),)
        result=solve(make(300,requests=req,license_nodes=('n2','n3')))
        self.assertEqual(len(result.study.node_order),300)
        self.assertTrue(replay_observational_nodewise_effects_v28(result))
        self.assertEqual(len(result.proofs[0].terms),4)
        self.assertEqual({n for n,_,_,_ in result.proofs[0].support_by_term},{'n2','n3'})

    def test_target_identity_propensity_invariant_population_specific(self):
        default=solve(make())
        changed=solve(make(probabilities=((Fraction(1,4),)*5,
                                           (Fraction(3,4),)*5,(Fraction(2,5),)*5)))
        self.assertEqual(default.proofs[0].target_fingerprint,changed.proofs[0].target_fingerprint)
        self.assertNotEqual(default.certificate_sha256,changed.certificate_sha256)
        shifted=solve(make(masses=('1/3','1/3','1/3')))
        self.assertNotEqual(default.proofs[0].target_fingerprint,shifted.proofs[0].target_fingerprint)

    def test_support_positivity_is_local_mixture_not_each_profile(self):
        # p0 and p1 have identical local C_n2, but p0 gives P(T_n2=1)=0.
        # p1 contributes positive mass to the same local stratum: admissible.
        result=solve(make(profile_zero=True))
        rows=result.proofs[0].support_by_term
        self.assertTrue(all(Fraction(p)>0 for _,_,_,local in rows for *_,p in local))

    def test_distinct_nodewise_adjustments_and_shared_covariate_marginal_dependence(self):
        st,src,_,_,_,_=make()
        p0,p1,p2=src.profiles
        self.assertEqual((p0.node_binary_features[2],p0.node_binary_features[1]+p0.node_binary_features[3]),(0,1))
        self.assertNotEqual((p0.node_binary_features[1],p0.node_binary_features[0]+p0.node_binary_features[2]),
                            (p0.node_binary_features[2],p0.node_binary_features[1]+p0.node_binary_features[3]))
        # T_0 and T_1 can correlate marginally through shared pre-treatment X profile.
        marginal=sum(Fraction(p.mass)*Fraction(p.treatment_one_probabilities[0]) for p in src.profiles)
        pair=sum(Fraction(p.mass)*Fraction(p.treatment_one_probabilities[0])*Fraction(p.treatment_one_probabilities[1]) for p in src.profiles)
        self.assertNotEqual(pair,marginal*marginal)

    def test_missing_science_licenses_rejected(self):
        for name in ('sufficiency','exchangeability'):
            with self.subTest(missing=name):
                out=routed(make(proposed=name))
                self.assertEqual(out.status,'NEEDS_INPUT')
                self.assertIsNone(out.result)

    def test_sample_only_and_missing_population_cell_rejected(self):
        self.assertEqual(routed(make(sample=True)).status,'NEEDS_INPUT')
        self.assertEqual(routed(make(missing=True)).status,'NEEDS_INPUT')

    def test_local_covariate_zero_support_blocks_even_with_global_support(self):
        items=list(make())
        source=items[1]
        # p2 is sole profile with n2 own-X=1. If its own treatment is always 0,
        # local stratum C=(1,2) has no T_i=1 support despite global positive support.
        profiles=list(source.profiles)
        p=profiles[2]
        r=list(p.treatment_one_probabilities);r[2]='0'
        profiles[2]=replace(p,treatment_one_probabilities=tuple(r))
        items[1]=replace(source,profiles=tuple(profiles))
        out=routed(tuple(items))
        self.assertEqual(out.status,'UNSUPPORTED')
        self.assertEqual(out.reason_code,'ZERO_NODEWISE_COVARIATE_STRATUM_SUPPORT')

    def test_source_posttreatment_rejected(self):
        _,src,*_=make()
        with self.assertRaisesRegex(ValueError,'POSTTREATMENT'):
            replace(src,covariate_timing='OBSERVED_AFTER_TREATMENT')

    def test_invalid_profile_coverage_and_duplicate_vectors_rejected(self):
        items=make();src=items[1]
        with self.assertRaisesRegex(ValueError,'UNIQUE'):
            replace(src,profiles=(src.profiles[0],
                replace(src.profiles[1],node_binary_features=src.profiles[0].node_binary_features),
                src.profiles[2]))
        with self.assertRaises(ValueError):
            NodewisePretreatmentProfileV28('bad','1/2',(0,False,1),('1/2',)*3)
        with self.assertRaisesRegex(ValueError,'NORMALIZED'):
            replace(src,profiles=(replace(src.profiles[0],mass='1/2'),*src.profiles[1:]))

    def test_a4_must_not_declare_mean_for_impossible_local_covariate_layer(self):
        items=list(make())
        source=items[1]
        # In these profiles n2's C=(0,1) or (1,2), never (0,0).
        bad=tuple(sorted((*source.covered_cells,('n2',0,0,0,0)),
                         key=lambda c:(source.node_order.index(c[0]),*c[1:])))
        items[1]=replace(source,covered_cells=bad)
        out=routed(tuple(items))
        self.assertEqual(out.status,'NEEDS_INPUT')
        self.assertEqual(out.reason_code,'A4_NODEWISE_NONPOPULATION_COVARIATE_CELL')

    def test_wrong_scope_and_signature_license_rejected(self):
        items=list(make())
        items[4]=replace(items[4],covariate_schema_fingerprint='fake')
        self.assertEqual(routed(tuple(items)).status,'UNSUPPORTED')

    def test_randomization_name_cannot_supply_observational_license(self):
        items=list(make())
        items[3]+= (admitted('full_vector_randomization'),)
        self.assertEqual(routed(tuple(items)).status,'UNSUPPORTED')

    def test_no_declared_a5_node_coverage_is_blocked(self):
        req=(EffectQueryV18(kind='TOTAL',node_weights=(('n2',1),('n3',1)),
                            reference_exposure=0,comparison_exposure=1,
            cohort_authority='TRUSTED_FIXTURE',cohort_evidence='Synthetic registered team, before treatment'),)
        self.assertEqual(routed(make(requests=req,license_nodes=('n2',))).status,'UNSUPPORTED')

    def test_business_type_route_and_certificate_tampering_rejected(self):
        o=routed(make())
        with self.assertRaisesRegex(ValueError,'mismatch'):
            replay_verified_business_outcome(replace(o,query_type='OBSERVATIONAL_EFFECTS'))
        with self.assertRaises(R3Unavailable):
            replay_observational_nodewise_effects_v28(replace(o.result,certificate_sha256='bad'))
        with self.assertRaises(R3Unavailable):
            replay_observational_nodewise_effects_v28(replace(o.result,
                proofs=(replace(o.result.proofs[0],identified_functional='false claim'),)))

    def test_no_cross_route_result_substitution(self):
        o=routed(make())
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(replace(o,route='R3_EXPOSURE_ADJUSTED_EFFECTS'))
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(replace(o,result=None))

if __name__=='__main__': unittest.main()
