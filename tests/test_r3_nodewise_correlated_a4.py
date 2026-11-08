"""Conditional correlated assignment A4 (NOT unconfoundedness) for original nodewise R3."""
from __future__ import annotations
from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from tests.test_r3_nodewise_neighbor_adjustment import make, routed, admitted, solve
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_observational_r3 import (
    R3Unavailable, _manual_exposure_classify_v26,
)
from pfn_pipeline.identification_observational_nodewise_adjustment import (
    CONDITIONAL_MIXTURE_LAW, NodewiseMixturePretreatmentProfileV28P2,
    replay_observational_nodewise_effects_v28,
)
from pfn_pipeline.identification_observational_nodewise_mixture_a4 import (
    declare_nodewise_correlated_arm_population_v28p2,
)
from pfn_pipeline.identification_business import replay_verified_business_outcome


def mixture_items(n=5,grouping='strict_majority_ties_low',requests=None,
                  *, component_shares=('1/3','2/3'),
                  sample=False,proposed=None,missing=False, same_as_old=False):
    st,orig,sig,records,lic,requests=make(n,grouping,requests,proposed=proposed,
                                         missing=missing)
    profiles=[]
    for idx,p in enumerate(orig.profiles):
        initial=p.treatment_one_probabilities
        if same_as_old:
            parts=(('1',initial),)
        else:
            # Within a given full X profile, a shared latent choice environment
            # makes T_j correlated (even though each component is Bernoulli product).
            alt=tuple('3/4' if j%2==0 else '1/4' for j in range(n))
            parts=((component_shares[0],initial),(component_shares[1],alt))
        profiles.append((p.label,p.mass,p.node_binary_features,parts))
    src=declare_nodewise_correlated_arm_population_v28p2(st,sig,
        source_id='synthetic-correlated-choice-A4',
        provenance='hypothetical exact P(X) and conditional mixture P(T|X), not observed fit',
        feature_name=orig.feature_name,profiles=tuple(profiles),
        covered_cells=orig.covered_cells,
        availability='FINITE_SAMPLE_ESTIMATE' if sample else 'SYMBOLIC_POPULATION_OPERATOR')
    return st,src,sig,records,lic,requests


class NodewiseCorrelatedA4(unittest.TestCase):
    def test_true_correlated_assignments_given_complete_x(self):
        st,source,*_=mixture_items()
        p=source.profiles[0]
        r0=Fraction(p.components[0].treatment_one_probabilities[0]);r1=Fraction(p.components[1].treatment_one_probabilities[0])
        s0=Fraction(p.components[0].treatment_one_probabilities[1]);s1=Fraction(p.components[1].treatment_one_probabilities[1])
        a=Fraction(p.components[0].weight);b=Fraction(p.components[1].weight)
        joint=a*r0*s0+b*r1*s1
        self.assertNotEqual(joint,(a*r0+b*r1)*(a*s0+b*s1))
        self.assertEqual(source.factorization_kind,CONDITIONAL_MIXTURE_LAW)

    def test_independent_full_assignment_oracle_all_five_exposures(self):
        for grouping,s in [('strict_majority_ties_low',1),
                           ('three_level_treated_neighbor_fraction',2),
                           ('pretreatment_core_collaborator_majority',1),
                           ('exact_treated_neighbor_count',2),
                           ('any_treated_neighbor',1)]:
            with self.subTest(grouping=grouping):
                req=(EffectQueryV18(kind='SPILLOVER',node_weights=(('n2',1),),
                    reference_exposure=0,comparison_exposure=s),)
                items=mixture_items(grouping=grouping,requests=req)
                result=solve(items)
                self.assertTrue(replay_observational_nodewise_effects_v28(result))
                st,src,sig,*_=items
                adj={v:set() for v in st.node_order}
                for u,v in st.undirected_edges:
                    adj[u].add(v);adj[v].add(u)
                ref={n:set(xs) for n,xs in sig.core_collaborators} if grouping=='pretreatment_core_collaborator_majority' else adj
                indices={n:j for j,n in enumerate(st.node_order)}
                for node,a,exposure,rows in result.proofs[0].support_by_term:
                    local_mass={};support={}
                    for profile in src.profiles:
                        c=(profile.node_binary_features[indices[node]],
                           sum(profile.node_binary_features[indices[j]] for j in adj[node]))
                        local_mass[c]=local_mass.get(c,Fraction(0))+Fraction(profile.mass)
                        for component in profile.components:
                            probs=tuple(Fraction(q) for q in component.treatment_one_probabilities)
                            for vector in product((0,1),repeat=len(st.node_order)):
                                cnt=sum(vector[indices[j]] for j in ref[node])
                                if (vector[indices[node]]==a and
                                    _manual_exposure_classify_v26(cnt,len(ref[node]),grouping)==exposure):
                                    q=Fraction(profile.mass)*Fraction(component.weight)
                                    for t,prob in zip(vector,probs):q*=prob if t else 1-prob
                                    support[c]=support.get(c,Fraction(0))+q
                    expected=tuple((x,k,str(m),str(support.get((x,k),Fraction(0))/m))
                                   for (x,k),m in sorted(local_mass.items()))
                    self.assertEqual(expected,rows)

    def test_business_route_handoff_and_300_nodes(self):
        from pfn_pipeline.identification_business_handoff import inspect_verified_business_handoff_v27
        req=(EffectQueryV18(kind='TOTAL',node_weights=(('n2','1/2'),('n3','1/2')),
            reference_exposure=0,comparison_exposure=1,
            cohort_authority='TRUSTED_FIXTURE',cohort_evidence='Pretreatment team list'),)
        out=routed(mixture_items(300,requests=req))
        self.assertEqual((out.status,out.route),('POINT','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'))
        self.assertTrue(replay_verified_business_outcome(out))
        self.assertEqual(len(out.result.study.node_order),300)
        self.assertEqual(inspect_verified_business_handoff_v27(out)['estimation']['status'],'NO_ADAPTER')
        self.assertEqual(out.result.source.factorization_kind,CONDITIONAL_MIXTURE_LAW)

    def test_same_target_identity_if_observational_propensities_change(self):
        baseline=solve(make())
        mix=solve(mixture_items())
        self.assertEqual(baseline.proofs[0].target_fingerprint,mix.proofs[0].target_fingerprint)
        self.assertEqual(baseline.proofs[0].identified_functional,mix.proofs[0].identified_functional)
        self.assertNotEqual(baseline.source.observational_law_fingerprint,mix.source.observational_law_fingerprint)
        self.assertNotEqual(baseline.certificate_sha256,mix.certificate_sha256)

    def test_single_component_is_old_nodewise_arithmetic(self):
        old=solve(make())
        equivalent=solve(mixture_items(same_as_old=True))
        self.assertEqual(old.proofs[0].support_by_term,equivalent.proofs[0].support_by_term)
        self.assertEqual(old.proofs[0].target_fingerprint,equivalent.proofs[0].target_fingerprint)

    def test_non_admitted_science_never_point(self):
        for missing in ('sufficiency','exchangeability'):
            with self.subTest(missing=missing):
                out=routed(mixture_items(proposed=missing))
                self.assertEqual(out.status,'NEEDS_INPUT')
                self.assertIsNone(out.result)

    def test_sample_only_and_missing_A4_cells_block(self):
        self.assertEqual(routed(mixture_items(sample=True)).status,'NEEDS_INPUT')
        self.assertEqual(routed(mixture_items(missing=True)).status,'NEEDS_INPUT')

    def test_zero_support_in_positive_population_covariate_layer_blocks(self):
        items=list(mixture_items())
        src=items[1]
        rows=list(src.profiles)
        # p2 uniquely provides C_n2=(1,2); both components force T_n2=0.
        p=rows[2]
        new_components=[]
        for component in p.components:
            props=list(component.treatment_one_probabilities);props[2]='0'
            new_components.append(replace(component,treatment_one_probabilities=tuple(props)))
        rows[2]=replace(p,components=tuple(sorted(new_components,key=lambda c:c.treatment_one_probabilities)))
        items[1]=replace(src,profiles=tuple(rows))
        out=routed(tuple(items))
        self.assertEqual((out.status,out.reason_code),
                         ('UNSUPPORTED','ZERO_NODEWISE_COVARIATE_STRATUM_SUPPORT'))

    def test_one_component_can_be_zero_if_conditional_mixture_has_support(self):
        items=list(mixture_items())
        src=items[1];rows=list(src.profiles)
        p=rows[0];first=p.components[0]
        props=list(first.treatment_one_probabilities);props[2]='0'
        rows[0]=replace(p,components=tuple(sorted((replace(first,treatment_one_probabilities=tuple(props)),p.components[1]),
                                                  key=lambda c:c.treatment_one_probabilities)))
        items[1]=replace(src,profiles=tuple(rows))
        self.assertEqual(routed(tuple(items)).status,'POINT')

    def test_malformed_components_rejected_on_declaration_or_replay(self):
        items=mixture_items();st,src,sig,*_=items
        with self.assertRaisesRegex(ValueError,'COMPONENT_MASS'):
            bad=src.profiles[0]
            replace(bad,components=(replace(bad.components[0],weight='1/2'),bad.components[1]))
        with self.assertRaisesRegex(ValueError,'UNIQUE_SORTED'):
            bad=src.profiles[0];replace(bad,components=(replace(bad.components[0],weight='1/2'),replace(bad.components[0],weight='1/2')))
        with self.assertRaisesRegex(ValueError,'PROFILE_TYPE'):
            old=make()[1]
            replace(src,profiles=old.profiles)
        with self.assertRaisesRegex(ValueError,'UNKNOWN_OPERATOR'):
            replace(src,operator='FAKE')
        with self.assertRaisesRegex(ValueError,'COMPONENT'):
            bad=src.profiles[0]
            replace(bad,components=bad.components*9)
        with self.assertRaisesRegex(ValueError,'POSTTREATMENT'):
            replace(src,covariate_timing='POSTTREATMENT')

    def test_corrupt_certificate_and_business_envelope_rejected(self):
        from pfn_pipeline.identification_observational_nodewise_adjustment import replay_observational_nodewise_effects_v28
        out=routed(mixture_items())
        with self.assertRaises(R3Unavailable):
            replay_observational_nodewise_effects_v28(replace(out.result,certificate_sha256='forged'))
        with self.assertRaises(ValueError):
            replay_verified_business_outcome(replace(out,query_type='OBSERVATIONAL_EFFECTS'))

    def test_profile_specific_mixture_weights_and_effect_support(self):
        items=list(mixture_items())
        src=items[1];rows=list(src.profiles)
        p=rows[1]
        rows[1]=replace(p,components=tuple(sorted((
            replace(p.components[0],weight='1/4'),replace(p.components[1],weight='3/4')),
            key=lambda c:c.treatment_one_probabilities)))
        items[1]=replace(src,profiles=tuple(rows))
        self.assertEqual(routed(tuple(items)).status,'POINT')
        self.assertNotEqual(solve(tuple(items)).certificate_sha256,solve(mixture_items()).certificate_sha256)

    def test_a4_cannot_claim_nonpopulation_covariate_cell(self):
        items=list(mixture_items());src=items[1]
        # Synthetic n2 adjustment has no X_2=0 and zero neighbor-X-count stratum.
        forbidden=('n2',0,0,0,0)
        cells=tuple(sorted((*src.covered_cells,forbidden),
            key=lambda c:(src.node_order.index(c[0]),*c[1:])))
        items[1]=replace(src,covered_cells=cells)
        out=routed(tuple(items))
        self.assertEqual((out.status,out.reason_code),
                         ('NEEDS_INPUT','A4_NODEWISE_NONPOPULATION_COVARIATE_CELL'))

    def test_showcase_all_cases_from_verified_business_api(self):
        from examples.run_r3_nodewise_correlated import generate,page
        data=generate()
        self.assertEqual((len(data['cases']),data['statuses']),
                         (11,{'POINT':6,'NEEDS_INPUT':4,'UNSUPPORTED':1}))
        self.assertTrue(all(x['verified'] for x in data['cases'] if x['status']=='POINT'))
        self.assertTrue(all(x['mathematical_result'] is None for x in data['cases']
                            if x['status']!='POINT'))
        self.assertEqual(page(data),page(generate()))

    def test_source_id_and_provenance_do_not_make_a4_true(self):
        st,src,sig,assumptions,lic,requests=mixture_items()
        self.assertIn('hypothetical',src.provenance)
        self.assertNotIn('scientifically proven',str(src))
        # An accepted A4 declaration and scientific A5 are separate typed objects.
        self.assertNotIn('exchangeability',src.factorization_kind.lower())
        self.assertEqual(tuple(a.name for a in assumptions),
                         ('consistency','fixed_pretreatment_network','finite_conditional_first_moments'))

if __name__=='__main__': unittest.main()
