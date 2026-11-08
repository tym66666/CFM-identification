"""Independent R3 observational finite-law and D2/E1 signature A6 tests."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import combinations,product
from math import comb
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context
from pfn_pipeline.identification_policy_r2 import declare_policy_signature,admit_mean_signature_sufficiency
from pfn_pipeline.identification_observational_r3 import (
    R3Unavailable,ObservationalFinitePopulationV23,declare_observational_population_v23,
    identify_observational_policy_v23,replay_observational_policy_v23)
from pfn_pipeline.identification_signature_diagnostics import diagnose_majority_quota_policy_v23
from pfn_pipeline.identification_business import (
    ObservationalPolicyInquiryV23,identify_network_business_query,replay_verified_business_outcome)


def study(n=3,edges=(('n0','n1'),('n1','n2')),observational=True,design=None):
    return declare_network_study(network_id='r3-fixture',node_order=tuple(f'n{i}' for i in range(n)),
            undirected_edges=tuple(edges),treatment_variable='AI',outcome_variable='Sales',
            outcome_kind='continuous',context_reference='W=w0',
            observation_regime='observational' if observational else 'experimental',
            assignment_design=design,protocol_provenance='synthetic reviewed protocol',
            network_provenance='fixed pretreatment graph',
            graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def a5(*,missing=None,proposed=None,randomization=False):
    names=('full_vector_conditional_exchangeability','consistency',
           'fixed_pretreatment_network','finite_conditional_first_moments')
    output=[]
    for name in names:
        if name==missing:continue
        if name==proposed:
            output.append(Assumption(name=name,source='llm_candidate',confirmed=False,
                                     evidence=['unconfirmed language-model suggestion']))
        else:
            output.append(Assumption(name=name,source='demo_specification',confirmed=True,
                       evidence=['SYNTHETIC A5: explicitly posited for the fixture, not learned from data']))
    if randomization:
        output.append(Assumption(name='full_vector_randomization',source='demo_specification',
                 confirmed=True,evidence=['incorrectly added randomization']))
    return tuple(output)


def target(st,z):
    return fixed_policy_target_from_context(st,tuple(z),authority='TRUSTED_FIXTURE')


def population(st,assignments,*,nodes=None,availability='SYMBOLIC_POPULATION_OPERATOR',admission='ADMITTED'):
    return declare_observational_population_v23(st,source_id='reviewed-observational-population-fixture',
        provenance='synthetic complete observational population conditional operator, not sample data',
        assignment_masses=assignments,
        outcome_nodes=st.node_order if nodes is None else nodes,
        availability=availability,admission=admission)


def star5_obs():
    st=study(5,tuple(('n0',f'n{i}') for i in range(1,5)))
    masses=[]
    for removed in range(5):
        masses.append((tuple(0 if k==removed else 1 for k in range(5)),Fraction(1,5)))
    return st,population(st,masses),target(st,(1,)*5)


def with_suff(st):
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    suf=admit_mean_signature_sufficiency(st,sig,covered_nodes=st.node_order,
         assumption=Assumption(name='mean_signature_sufficiency',
             source='demo_specification',confirmed=True,
             evidence=['SYNTHETIC A5: mean outcome depends only on own treatment and majority exposure']))
    return sig,suf


class ObservationalR3Tests(unittest.TestCase):
    def test_full_observational_policy_success_and_replay(self):
        st=study(); src=population(st,[((0,0,0),Fraction(1,3)),((1,0,1),Fraction(2,3))])
        result=identify_observational_policy_v23(st,target(st,(1,0,1)),src,assumptions=a5())
        self.assertEqual(result.route,'R3_FULL_ASSIGNMENT')
        self.assertEqual(result.target_observational_probability,'2/3')
        self.assertTrue(replay_observational_policy_v23(result))
        self.assertNotIn('mean_signature_sufficiency',result.summary()['assumptions_used'])
        self.assertEqual(len(result.weighted_node_classes),3)

    def test_unneeded_proposed_sufficiency_does_not_block_full_route(self):
        st=study(); src=population(st,[((0,0,0),Fraction(1,3)),((1,0,1),Fraction(2,3))])
        sig,suf=with_suff(st)
        proposed=replace(suf,assumption=Assumption(name='mean_signature_sufficiency',
                    source='llm_candidate',evidence=['unadmitted proposal']))
        out=identify_observational_policy_v23(st,target(st,(1,0,1)),src,
                    assumptions=a5(),signature=sig,sufficiency=proposed)
        self.assertEqual(out.route,'R3_FULL_ASSIGNMENT')
        self.assertIsNone(out.sufficiency)
        self.assertTrue(replay_observational_policy_v23(out))

    def test_malformed_assumptions_and_provenance_are_blocked(self):
        st=study();src=population(st,[((0,0,0),1)])
        t=target(st,(0,0,0))
        # Even an otherwise admitted exchangeability claim cannot be treated
        # as a deterministic fact from observed allocation probabilities.
        assumptions=list(a5())
        assumptions[0]=Assumption(name='full_vector_conditional_exchangeability',
            source='deterministic_derivation',confirmed=True,
            evidence=['invalid: inferred from observed T'])
        with self.assertRaisesRegex(R3Unavailable,'NEEDS_INPUT'):
            identify_observational_policy_v23(st,t,src,assumptions=tuple(assumptions))
        with self.assertRaisesRegex(R3Unavailable,'DUPLICATE_ASSUMPTION_RECORD'):
            identify_observational_policy_v23(st,t,src,assumptions=a5()+a5()[:1])

    def test_conditional_scope_and_treatment_identity_remain_part_of_target(self):
        st=study();src=population(st,[((0,0,0),1)])
        tgt=target(st,(0,0,0))
        t2=replace(tgt,context='W=some_other_stratum',target_digest='')
        with self.assertRaisesRegex(R3Unavailable,'TARGET_STUDY_SCOPE_MISMATCH'):
            identify_observational_policy_v23(st,t2,src,assumptions=a5())

    def test_zero_full_support_without_sufficiency(self):
        st,src,tgt=star5_obs()
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT'):
            identify_observational_policy_v23(st,tgt,src,assumptions=a5())

    def test_signature_offsupport_policy_and_accurate_independent_oracle(self):
        st,src,tgt=star5_obs();sig,suf=with_suff(st)
        result=identify_observational_policy_v23(st,tgt,src,assumptions=a5(),signature=sig,sufficiency=suf)
        self.assertEqual(result.route,'R3_MEAN_SIGNATURE')
        self.assertEqual(result.target_observational_probability,'0')
        self.assertEqual(result.node_support,('4/5','3/5','3/5','3/5','3/5'))
        self.assertTrue(replay_observational_policy_v23(result))
        # Oracle: potential outcome mean Y_i(t)=t_i/4+g_i(t)/2, fixed
        # structural sufficiency; full-vector ignorability is posited.
        edges={k:set() for k in st.node_order}
        for a,b in st.undirected_edges:edges[a].add(b);edges[b].add(a)
        assign=dict(zip(st.node_order,tgt.policy_assignment))
        expected=Fraction(0)
        for node in st.node_order:
            degree=len(edges[node]);s=int(sum(assign[x] for x in edges[node])>degree//2)
            expected+=(Fraction(assign[node],4)+Fraction(s,2))/5
        recovered=Fraction(0)
        for i,node in enumerate(st.node_order):
            a=tgt.policy_assignment[i];s_target=result.weighted_node_classes[i][2]
            num=Fraction(0);den=Fraction(0)
            for t,p_str in src.assignment_masses:
                pr=Fraction(p_str); vec=dict(zip(st.node_order,t))
                deg=len(edges[node]);s=int(sum(vec[x] for x in edges[node])>deg//2)
                if vec[node]==a and s==s_target:
                    den+=pr;num+=pr*(Fraction(a,4)+Fraction(s,2))
            self.assertEqual(den,Fraction(result.node_support[i]))
            recovered+=Fraction(result.node_weights[i])*num/den
        self.assertEqual(recovered,expected)

    def test_independent_witness_why_observational_exchangeability_is_essential(self):
        # Explicit two-world witness. Each world has two equally probable
        # latent types (T, Y(0), Y(1)). Observed (T,Y(T)) is identical;
        # counterfactual all-treated mean differs because selection is allowed.
        world_a=((0,0,1),(1,0,1))
        world_b=((0,0,0),(1,0,1))
        observed=lambda world:tuple((t,(y1 if t else y0)) for t,y0,y1 in world)
        self.assertEqual(observed(world_a),observed(world_b))
        value=lambda world:sum((Fraction(y1,2) for _,_,y1 in world),Fraction(0))
        self.assertEqual(value(world_a),Fraction(1))
        self.assertEqual(value(world_b),Fraction(1,2))
        st=study(1,())
        src=population(st,[((0,),Fraction(1,2)),((1,),Fraction(1,2))])
        with self.assertRaisesRegex(R3Unavailable,'NEEDS_INPUT'):
            identify_observational_policy_v23(st,target(st,(1,)),src,
                assumptions=a5(missing='full_vector_conditional_exchangeability'))

    def test_observational_assumption_proposal_rejected(self):
        st=study();src=population(st,[((0,0,0),1)])
        with self.assertRaisesRegex(R3Unavailable,'NEEDS_INPUT'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),src,
                assumptions=a5(proposed='full_vector_conditional_exchangeability'))

    def test_extra_randomization_assumption_must_not_replace_observational_license(self):
        st=study();src=population(st,[((0,0,0),1)])
        with self.assertRaisesRegex(R3Unavailable,'RANDOMIZATION_IS_NOT_OBSERVATIONAL_IGNORABILITY'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),src,assumptions=a5(randomization=True))

    def test_unadmitted_sufficiency_cannot_extrapolate(self):
        st,src,tgt=star5_obs();sig,suf=with_suff(st)
        bad=replace(suf,assumption=Assumption(name='mean_signature_sufficiency',
             source='llm_candidate',evidence=['proposal']))
        with self.assertRaisesRegex(R3Unavailable,'MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED'):
            identify_observational_policy_v23(st,tgt,src,assumptions=a5(),signature=sig,sufficiency=bad)

    def test_signature_missing_positive_class(self):
        st=study(5,tuple(('n0',f'n{i}') for i in range(1,5)))
        # All untreated => high-signature not present in any population allocation.
        src=population(st,[((0,0,0,0,0),1)])
        sig,suf=with_suff(st)
        with self.assertRaisesRegex(R3Unavailable,'ZERO_OBSERVATIONAL_SIGNATURE_SUPPORT'):
            identify_observational_policy_v23(st,target(st,(1,)*5),src,assumptions=a5(),signature=sig,sufficiency=suf)

    def test_finite_sample_not_population_operator(self):
        st=study();src=population(st,[((0,0,0),1)],availability='FINITE_SAMPLE_ESTIMATE')
        with self.assertRaisesRegex(R3Unavailable,'A4_POPULATION_OPERATOR_REQUIRED'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),src,assumptions=a5())

    def test_proposed_A4_source_fails(self):
        st=study();src=population(st,[((0,0,0),1)],admission='PROPOSED')
        with self.assertRaisesRegex(R3Unavailable,'A4_SOURCE_NOT_ADMITTED'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),src,assumptions=a5())

    def test_missing_weighted_outcome_node(self):
        st=study();src=population(st,[((0,0,0),1)],nodes=('n0','n1'))
        with self.assertRaisesRegex(R3Unavailable,'A4_WEIGHTED_OUTCOME_NODES_MISSING'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),src,assumptions=a5())

    def test_wrong_population_scope_rejected(self):
        st=study();src=population(st,[((0,0,0),1)])
        bad=replace(src,protocol_digest='different-protocol')
        with self.assertRaisesRegex(R3Unavailable,'A4_STUDY_OR_PROTOCOL_MISMATCH'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),bad,assumptions=a5())

    def test_r3_no_known_randomization_q_in_observational_study(self):
        st=study(3,design=None);self.assertIsNone(st.design())
        src=population(st,[((0,0,0),1)])
        self.assertEqual(identify_observational_policy_v23(st,target(st,(0,0,0)),src,
                         assumptions=a5()).route,'R3_FULL_ASSIGNMENT')
        experimental=study(3,observational=False,design={'kind':'complete_randomization_binary_v1','m':1})
        with self.assertRaisesRegex(R3Unavailable,'OBSERVATIONAL_STUDY_REQUIRED'):
            identify_observational_policy_v23(experimental,target(experimental,(0,0,0)),
                                               src,assumptions=a5())

    def test_bad_probability_laws_rejected(self):
        st=study()
        for masses in [
                [((0,0,0),Fraction(1,2))],
                [((0,0,0),Fraction(-1,2)),((1,1,1),Fraction(3,2))],
                [((0,0,0),1),((0,0,0),1)],
                [((0,0,0),0)],
                [((0,0,0),1),((1,1,1),0)],
              ]:
            with self.subTest(masses=masses),self.assertRaises(ValueError):
                population(st,masses)

    def test_replay_catches_fingerprint_and_derived_formula_tampering(self):
        st=study();src=population(st,[((0,0,0),1)])
        original=identify_observational_policy_v23(st,target(st,(0,0,0)),src,assumptions=a5())
        for forged in [replace(original,node_support=('999',)*3),
                       replace(original,identified_functional='0'),
                       replace(original,route='R3_MEAN_SIGNATURE')]:
            with self.subTest(forged=forged.identified_functional),self.assertRaises(R3Unavailable):
                replay_observational_policy_v23(forged)
        # Re-hashing an altered derived result cannot fool re-derivation.
        from dataclasses import asdict
        from pfn_pipeline.identification_a4_shadow import _sha
        altered=replace(original,identified_functional='fake')
        payload=asdict(altered);payload.pop('certificate_sha256')
        altered=replace(altered,certificate_sha256=_sha(payload))
        with self.assertRaisesRegex(R3Unavailable,'R3_CERTIFICATE_REPLAY_MISMATCH'):
            replay_observational_policy_v23(altered)

    def test_unified_business_dispatch_and_replay(self):
        st,src,tgt=star5_obs();sig,suf=with_suff(st)
        r=identify_network_business_query(ObservationalPolicyInquiryV23(st,tgt,src,a5(),sig,suf))
        self.assertEqual(r.status,'POINT');self.assertEqual(r.route,'R3_MEAN_SIGNATURE')
        self.assertTrue(replay_verified_business_outcome(r))
        blocked=identify_network_business_query(ObservationalPolicyInquiryV23(st,tgt,src,a5()))
        self.assertEqual(blocked.status,'UNSUPPORTED')
        self.assertEqual(blocked.reason_code,'ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT')

    def test_study_alias_and_overlapping_nodes_fail_closed(self):
        st=study();src=population(st,[((0,0,0),1)])
        forged=replace(src,node_order=('n2','n1','n0'))
        with self.assertRaisesRegex(R3Unavailable,'A4_STUDY_OR_PROTOCOL_MISMATCH'):
            identify_observational_policy_v23(st,target(st,(0,0,0)),forged,assumptions=a5())

    def test_signature_claim_missing_context_fails(self):
        st,src,tgt=star5_obs();sig,suf=with_suff(st)
        bogus=replace(suf,study_scope_digest='wrong')
        with self.assertRaisesRegex(R3Unavailable,'SIGNATURE_SUFFICIENCY_STUDY_MISMATCH'):
            identify_observational_policy_v23(st,tgt,src,assumptions=a5(),signature=sig,sufficiency=bogus)

    def test_32_card_baseline_is_not_misreported_as_observational_direct_effect(self):
        from examples.run_business_coverage_delta import build_delta
        d=build_delta()
        self.assertEqual(d['baseline_cards'],32)
        self.assertEqual(d['additional_r3_cards'],5)
        self.assertEqual(d['baseline_B24_observational_direct_effect_status'],'NO_REGISTERED_THEOREM')
        self.assertEqual(d['additional_status_counts'].get('POINT_VERIFIED'),2)
        self.assertEqual(d['additional_status_counts'].get('NEEDS_INPUT'),2)
        self.assertEqual(d['additional_status_counts'].get('UNSUPPORTED'),1)

    def test_limit_explicit_not_er300_claim(self):
        st=study(13,())
        with self.assertRaisesRegex(ValueError,'FINITE_OBSERVATIONAL_SUPPORT_ENUMERATION_LIMIT'):
            population(st,[((0,)*13,1)])

    def test_direct_observational_support_enumeration_property(self):
        st=study(3)
        masses=[(t,Fraction(1,8)) for t in product((0,1),repeat=3)]
        src=population(st,masses)
        sig,suf=with_suff(st)
        for z in product((0,1),repeat=3):
            result=identify_observational_policy_v23(st,target(st,z),src,assumptions=a5(),signature=sig,sufficiency=suf)
            self.assertEqual(result.route,'R3_FULL_ASSIGNMENT')
            self.assertEqual(Fraction(result.target_observational_probability),Fraction(1,8))
            self.assertTrue(replay_observational_policy_v23(result))


class QuotaSignatureDiagnosticTests(unittest.TestCase):
    def graph_report(self,edges,n=7,m=3):
        st=study(n,edges,observational=False,design={'kind':'complete_randomization_binary_v1','m':m})
        return diagnose_majority_quota_policy_v23(st,target(st,(1,)*n))

    def test_star_hub_reason_is_insufficient_quota(self):
        r=self.graph_report(tuple(('n0',f'n{k}') for k in range(1,7)))
        self.assertEqual(r.target_full_assignment_probability,'0')
        self.assertEqual(r.unsupported_weighted_nodes,1)
        center=r.nodes[0]
        self.assertEqual(center.degree,6)
        self.assertEqual(center.minimum_required_treated_neighbors,4)
        self.assertEqual(center.maximum_feasible_treated_neighbors,2)
        self.assertEqual(center.signature_probability,'0')
        self.assertEqual(center.reason_code,'INSUFFICIENT_QUOTA_FOR_MAJORITY_SIGNATURE')

    def test_path_ring_complete_distinctions(self):
        path=tuple((f'n{k}',f'n{k+1}') for k in range(6))
        ring=path+(('n6','n0'),)
        complete=tuple((f'n{i}',f'n{j}') for i in range(7) for j in range(i+1,7))
        self.assertEqual(self.graph_report(path).unsupported_weighted_nodes,0)
        self.assertEqual(self.graph_report(ring).unsupported_weighted_nodes,0)
        self.assertEqual(self.graph_report(complete).unsupported_weighted_nodes,7)

    def test_isolate_e1_low_exposure_is_defined(self):
        r=self.graph_report((('n0','n1'),),n=7)
        self.assertEqual(r.unsupported_weighted_nodes,0)
        isolate=r.nodes[6]
        self.assertEqual(isolate.degree,0)
        self.assertEqual(isolate.policy_signature,0)
        self.assertGreater(Fraction(isolate.signature_probability),0)

    def test_exact_combinatorics_for_mixed_treatment_target(self):
        edges=(('n0','n1'),('n0','n2'),('n0','n3'),('n0','n4'))
        st=study(5,edges,observational=False,design={'kind':'complete_randomization_binary_v1','m':2})
        for z in product((0,1),repeat=5):
            r=diagnose_majority_quota_policy_v23(st,target(st,z))
            for i,node in enumerate(r.nodes):
                target_a=z[i];d=node.degree
                nbr=[int(x[1:]) for x in [e[1] if e[0]==node.node_id else e[0]
                     for e in edges if node.node_id in e]]
                target_s=int(sum(z[j] for j in nbr)>d//2)
                manual=Fraction(0)
                for inds in combinations(range(5),2):
                    t=tuple(int(j in inds) for j in range(5))
                    if t[i]==target_a and int(sum(t[j] for j in nbr)>d//2)==target_s:
                        manual+=Fraction(1,comb(5,2))
                self.assertEqual(Fraction(node.signature_probability),manual)


if __name__=='__main__':unittest.main()
