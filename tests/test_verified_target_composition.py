"""R1a exact population mean contrasts and groups; no PFN or simulator truth in ID."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline import (make_heterogeneous_bernoulli_arm_task,
                          make_complete_randomization_arm_task,
                          make_two_group_quota_arm_task)
from pfn_pipeline.identification_batch import identify_randomized_network_batch
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_composition import (
    ArmLinearTerm, CompositionUnavailable, identify_verified_linear_target,
    identify_verified_node_effect, identify_verified_group_effect,
    replay_verified_composition, EffectQueryV18,
    identify_verified_effect_bundle, replay_verified_effect_bundle,
)
from pfn_pipeline._internal.identification.schemas import (IdentificationSpec,
                                                            NetworkExposureSpec)
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec


STAR = NetworkExposureSpec(network_id='composition-star5',
    node_ids=['0','1','2','3','4'],
    undirected_edges=[('0','1'),('0','2'),('0','3'),('0','4')])
SIX = NetworkExposureSpec(network_id='composition-six',
    node_ids=['a','b','c','d','e','f'],
    undirected_edges=[('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),
                      ('f','a'),('a','d'),('b','e'),('c','f')])


def batch(design='D1', grouping='strict_majority', network=STAR, **kw):
    args=dict(node_id=network.node_ids[0],own_treatment_value=0, exposure_value=0,
              source='signed population study protocol', evidence='explicit verified randomized experiment',
              synthetic=True, admitted=True, query_authority='TRUSTED_FIXTURE',
              exposure_definition=grouping)
    if grouping == 'pretreatment_core_collaborator_majority':
        edges={node:set() for node in network.node_ids}
        for u,v in network.undirected_edges:
            edges[u].add(v); edges[v].add(u)
        args['core_collaborators']={n: (sorted(ns)[0],) for n,ns in edges.items()}
    if design == 'D1':
        args.update(propensities={node:str(Fraction(j+2, len(network.node_ids)+4))
                                   for j,node in enumerate(network.node_ids)})
        maker = make_heterogeneous_bernoulli_arm_task
    elif design == 'D2':
        args['m'] = 2 if len(network.node_ids) == 5 else 3
        maker = make_complete_randomization_arm_task
    else:
        cutoff=3 if len(network.node_ids)==6 else 2
        args['groups']=(tuple(network.node_ids[:cutoff]),tuple(network.node_ids[cutoff:]))
        args['treated_quotas']=(1,1)
        maker = make_two_group_quota_arm_task
    if design == 'D2' and grouping == 'three_level_treated_neighbor_fraction' and network is SIX:
        args['exposure_value'] = 1  # supported anchor under m=3 on degree-three node
    args.update(kw)
    return identify_randomized_network_batch(maker(network, **args))


def a4_source(b, *, operator='NODE_ARM_MEANS', availability='SYMBOLIC_POPULATION_OPERATOR',
              admission='ADMITTED', cells=None, nodes=None, regime='experimental'):
    if cells is None:
        cells=tuple((node,a,s) for node in b.node_ids for a in (0,1) for s in b.exposure_states
                    if b.cell(node,a,s)['status']=='POINT')
    return declare_a4_source(b.template, source_id='explicit-reviewed:'+operator,
        operator=operator, provenance='study-expert-approved A4 population operator',
        admission=admission, availability=availability, regime=regime,
        outcome_nodes=tuple(b.node_ids if nodes is None else nodes),
        node_order=b.node_ids, arm_cells=tuple(cells) if operator=='NODE_ARM_MEANS' else ())


def oracle_arm_mean(b, node, a, s):
    """Independent fixed potential-outcome *table* for tests only.

    Outcomes intentionally depend on the full assignment beyond the exposure.
    ID production code has no access to this table.
    """
    spec=IdentificationSpec.model_validate(b.template.identification_spec)
    graph=spec.network_exposure
    theorem=spec.randomized_network_arm_theorem_contract
    exposure=ExposureSpec(theorem.grouping, theorem.core_collaborators)
    design=AssignmentSpec(theorem.design)
    idx=graph.node_ids.index(node)
    neighs={n:set() for n in graph.node_ids}
    for u,v in graph.undirected_edges:
        neighs[u].add(v); neighs[v].add(u)
    if theorem.core_collaborators is not None:
        neighs={n:set(theorem.core_collaborators[n]) for n in graph.node_ids}
    numerator=Fraction(0); mass=Fraction(0)
    for values in product((0,1),repeat=len(graph.node_ids)):
        assignment=dict(zip(graph.node_ids,values))
        if assignment[node]!=a:
            continue
        treated=sum(assignment[j] for j in neighs[node])
        if theorem.grouping=='three_level_treated_neighbor_fraction' and not neighs[node]:
            continue
        if exposure.classify(treated,len(neighs[node]))!=s:
            continue
        q=design.full_assignment_probability(graph,assignment)
        # Neither locality nor exposure sufficiency is assumed.
        y=Fraction(7*idx+3*values[idx]+2*sum(values)
                    +11*values[(idx+1)%len(values)]
                    +5*values[(idx+2)%len(values)]*values[(idx+3)%len(values)],3)
        numerator+=q*y
        mass+=q
    if not mass:
        return None
    return numerator/mass


class R1aCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = batch()
        cls.a4 = a4_source(cls.b)

    def test_single_node_direct_spillover_total_are_exact_and_replayed(self):
        b=self.b; source=self.a4
        for kind,expected in {
            'DIRECT':((1,0,Fraction(1)),(0,0,Fraction(-1))),
            'SPILLOVER':((1,1,Fraction(1)),(1,0,Fraction(-1))),
            'TOTAL':((1,1,Fraction(1)),(0,0,Fraction(-1))),
        }.items():
            with self.subTest(kind=kind):
                result=identify_verified_node_effect(b,source,node_id='0',kind=kind,
                                                     reference_exposure=0,comparison_exposure=0 if kind=='DIRECT' else 1)
                self.assertEqual(result.status,'POINT')
                self.assertEqual(result.verification_status,'VERIFIED')
                self.assertIsNone(result.estimation_request)
                self.assertEqual(sum(t.coefficient*oracle_arm_mean(b,*t.coordinates)
                                     for t in result.terms),
                                 sum(coeff*oracle_arm_mean(b,'0',a,s) for a,s,coeff in expected))
                self.assertEqual(replay_verified_composition(result).certificate_sha256,
                                 result.certificate_sha256)
                self.assertTrue(result.identified_functional.startswith('E[') or result.identified_functional.startswith('-'))

    def test_public_summary_exposes_exact_support_not_effect_estimates(self):
        out=identify_verified_node_effect(self.b,self.a4,node_id='0',kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
        data=out.summary()
        self.assertEqual(len(data['constituent_arms']), 2)
        self.assertEqual({cell['node_id'] for cell in data['constituent_arms']}, {'0'})
        self.assertEqual(tuple(cell['joint_support'] for cell in data['constituent_arms']),
                         out.population_arm_support)
        self.assertTrue(all(Fraction(cell['joint_support']) > 0
                            for cell in data['constituent_arms']))
        self.assertTrue(all('arm_target_fingerprint' in cell
                            for cell in data['constituent_arms']))
        self.assertNotIn('estimated_effect', data)
        self.assertIsNone(data['estimation_request'])

    def test_arbitrary_group_exact_normalization(self):
        b=self.b; source=self.a4
        result=identify_verified_group_effect(b,source,kind='SPILLOVER',
            node_weights={'1':'2','2':'1','3':'0'},reference_exposure=0,
            comparison_exposure=1,cohort_authority='STUDY_PROTOCOL',
            cohort_evidence='group membership/weights declared before treatment')
        oracle=Fraction(2,3)*(oracle_arm_mean(b,'1',1,1)-oracle_arm_mean(b,'1',1,0))
        oracle+=Fraction(1,3)*(oracle_arm_mean(b,'2',1,1)-oracle_arm_mean(b,'2',1,0))
        self.assertEqual(sum(t.coefficient*oracle_arm_mean(b,*t.coordinates)
                             for t in result.terms),oracle)
        self.assertEqual(result.term_count,4)
        self.assertTrue(replay_verified_composition(result))
        self.assertNotIn('Y_3^obs', result.identified_functional)

    def test_all_nine_design_exposure_settings_with_supported_contrasts(self):
        for design in ('D1','D2','D3'):
            for exposure in ('strict_majority','three_level_treated_neighbor_fraction',
                             'pretreatment_core_collaborator_majority'):
                with self.subTest(design=design,exposure=exposure):
                    b=batch(design,exposure,SIX)
                    src=a4_source(b)
                    usable=None
                    for node in b.node_ids:
                        for s in b.exposure_states:
                            if b.cell(node,0,s)['status']=='POINT' and b.cell(node,1,s)['status']=='POINT':
                                usable=node,s
                                break
                        if usable: break
                    self.assertIsNotNone(usable)
                    node,s=usable
                    out=identify_verified_node_effect(b,src,node_id=node,kind='DIRECT',
                        reference_exposure=s,comparison_exposure=s)
                    self.assertEqual(out.term_count,2)
                    self.assertEqual(sum(t.coefficient*oracle_arm_mean(b,*t.coordinates)
                                         for t in out.terms),
                                     oracle_arm_mean(b,node,1,s)-oracle_arm_mean(b,node,0,s))
                    self.assertEqual(replay_verified_composition(out).target_fingerprint,out.target_fingerprint)

    def test_three_level_spillover_explicit_state_two(self):
        b=batch('D1','three_level_treated_neighbor_fraction',SIX)
        source=a4_source(b)
        out=identify_verified_node_effect(b,source,node_id='a',kind='SPILLOVER',
                                         reference_exposure=0,comparison_exposure=2)
        self.assertIn('S_a=2',out.identified_functional)
        self.assertEqual(out.term_count,2)

    def test_custom_linear_target_exact_merge_identity(self):
        b=self.b;src=self.a4
        direct=identify_verified_node_effect(b,src,node_id='0',kind='DIRECT',
                                           reference_exposure=0,comparison_exposure=0)
        custom=identify_verified_linear_target(b,src,(
            ArmLinearTerm('0',1,0,'1/2'), ArmLinearTerm('0',1,0,'1/2'),
            ArmLinearTerm('0',0,0,'-1'), ArmLinearTerm('1',0,0,0),
        ))
        self.assertEqual(custom.target_fingerprint,direct.target_fingerprint)
        self.assertNotEqual(custom.certificate_sha256,direct.certificate_sha256)
        self.assertEqual(custom.term_count,2)
        self.assertEqual(custom.terms,direct.terms)

    def test_scientific_target_identity_not_seed_query_or_provenance(self):
        b=self.b
        other=batch('D1','strict_majority',STAR,node_id='1',own_treatment_value=1,
                    exposure_value=1,source='second trusted experimental source',
                    evidence='different reviewer confirmation of same q and W')
        self.assertNotEqual(other.source_spec_sha256,b.source_spec_sha256)
        first=identify_verified_node_effect(b,self.a4,node_id='0',kind='DIRECT',
            reference_exposure=0,comparison_exposure=0)
        second=identify_verified_node_effect(other,a4_source(other),node_id='0',kind='DIRECT',
            reference_exposure=0,comparison_exposure=0)
        self.assertEqual(first.target_fingerprint,second.target_fingerprint)
        self.assertNotEqual(first.certificate_sha256,second.certificate_sha256)

    def test_fixture_group_claim_rejected_for_non_synthetic_study(self):
        b=batch('D1','strict_majority',STAR,synthetic=False,
                query_authority='HUMAN_CONFIRMED', admitted=True)
        src=a4_source(b)
        with self.assertRaises(CompositionUnavailable) as caught:
            identify_verified_group_effect(b,src,kind='TOTAL',node_weights={'0':1,'1':1},
                reference_exposure=0,comparison_exposure=1,
                cohort_authority='TRUSTED_FIXTURE',cohort_evidence='pretend fixture')
        self.assertEqual(caught.exception.reason_code,'TRUSTED_FIXTURE_REQUIRES_SYNTHETIC_STUDY')

    def test_multi_query_bundle_single_batch_replay_and_independent_replay(self):
        b=self.b; src=self.a4
        requests=tuple(EffectQueryV18(kind=k,node_weights=(('0',1),),
                      reference_exposure=0,comparison_exposure=0 if k=='DIRECT' else 1)
                      for k in ('DIRECT','SPILLOVER','TOTAL'))
        bundle=identify_verified_effect_bundle(b,src,requests)
        self.assertEqual(len(bundle.results),3)
        self.assertEqual(bundle.verification_status,'VERIFIED')
        self.assertEqual(replay_verified_effect_bundle(bundle).bundle_sha256,bundle.bundle_sha256)
        singles=tuple(identify_verified_node_effect(b,src,node_id='0',kind=k,
                      reference_exposure=0,comparison_exposure=0 if k=='DIRECT' else 1)
                      for k in ('DIRECT','SPILLOVER','TOTAL'))
        self.assertEqual(tuple(x.certificate_sha256 for x in bundle.results),
                         tuple(x.certificate_sha256 for x in singles))
        for bad in (replace(bundle,bundle_sha256='tampered'),
                    replace(bundle,results=(replace(bundle.results[0],status='PARTIAL'),
                                            *bundle.results[1:]))):
            with self.assertRaises(CompositionUnavailable):
                replay_verified_effect_bundle(bad)

    def test_bundle_group_normalization_and_failure_is_all_or_nothing(self):
        b=self.b;src=self.a4
        q=EffectQueryV18(kind='TOTAL',node_weights=(('1','2'),('2','1')),
                         reference_exposure=0,comparison_exposure=1,
                         cohort_authority='STUDY_PROTOCOL',cohort_evidence='prespecified subgroup')
        out=identify_verified_effect_bundle(b,src,(q,)).results[0]
        self.assertEqual(out.term_count,4)
        self.assertEqual(set(t.coefficient for t in out.terms),{Fraction(-2,3),Fraction(2,3),Fraction(-1,3),Fraction(1,3)})
        with self.assertRaises(CompositionUnavailable):
            identify_verified_effect_bundle(b,src,(q,EffectQueryV18(
                kind='TOTAL',node_weights=(('missing',1),),
                reference_exposure=0,comparison_exposure=1)))

    def test_zero_arm_support_is_rejected_not_silently_dropped(self):
        b=batch('D2','strict_majority',STAR,m=0)
        src=a4_source(b)
        with self.assertRaises(CompositionUnavailable) as err:
            identify_verified_linear_target(b,src,(ArmLinearTerm('0',1,0,1),))
        self.assertEqual(err.exception.reason_code,'ZERO_ARM_SUPPORT')

    def test_undefined_exposure_is_rejected(self):
        isolated=NetworkExposureSpec(network_id='one-isolate',node_ids=['a','b','c','d'],
                                     undirected_edges=[('a','b'),('b','c')])
        b=batch('D1','three_level_treated_neighbor_fraction',isolated)
        src=a4_source(b)
        with self.assertRaises(CompositionUnavailable) as err:
            identify_verified_linear_target(b,src,(ArmLinearTerm('d',1,0,1),))
        self.assertEqual(err.exception.reason_code,'EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE')

    def test_a4_partial_coverage_and_pairwise_are_blocked(self):
        b=self.b
        source=a4_source(b,cells=(('0',0,0),))
        with self.assertRaises(CompositionUnavailable) as err:
            identify_verified_node_effect(b,source,node_id='0',kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
        self.assertEqual(err.exception.reason_code,'A4_ARM_COVERAGE_INCOMPLETE')
        pairwise=a4_source(b,operator='PAIRWISE_MARGINALS')
        with self.assertRaises(CompositionUnavailable) as err:
            identify_verified_node_effect(b,pairwise,node_id='0',kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
        self.assertEqual(err.exception.reason_code,'A4_OPERATOR_NOT_ENTAILED')

    def test_a4_full_law_allowed_but_not_sample_or_unreviewed(self):
        b=self.b
        for operator in ('NODE_FULL_LAW','FULL_JOINT_LAW'):
            result=identify_verified_node_effect(b,a4_source(b,operator=operator),
                node_id='0',kind='TOTAL',reference_exposure=0,comparison_exposure=1)
            self.assertIn('TO_ARM',result.a4_rule_id)
        for source in (a4_source(b,availability='FINITE_SAMPLE_ESTIMATE'),
                       a4_source(b,admission='PROPOSED')):
            with self.assertRaises(CompositionUnavailable):
                identify_verified_node_effect(b,source,node_id='0',kind='TOTAL',
                                              reference_exposure=0,comparison_exposure=1)

    def test_a4_scope_q_and_coordinate_mismatch_blocked(self):
        b=self.b; src=self.a4
        for changed in (replace(src,context='wrong W'),
                        replace(src,node_order=tuple(reversed(src.node_order))),
                        replace(src,assignment_law_fingerprint='0'*64),
                        replace(src,outcome='wrong_y'),
                        replace(src,exposure_fingerprint='0'*64),
                        replace(src,source_spec_fingerprint='0'*64)):
            with self.subTest(changed=changed):
                with self.assertRaises(CompositionUnavailable):
                    identify_verified_node_effect(b,changed,node_id='0',kind='DIRECT',
                                                  reference_exposure=0,comparison_exposure=0)

    def test_group_requires_pretreatment_evidence_and_exact_weights(self):
        b=self.b;src=self.a4
        base=dict(kind='DIRECT',node_weights={'0':1,'1':2},reference_exposure=0,
                  comparison_exposure=0,cohort_authority='STUDY_PROTOCOL',
                  cohort_evidence='prespecified protocol group')
        for field,value in (('cohort_authority','LLM_PROPOSED'),('cohort_evidence',''),
                            ('node_weights',{'0':1,'1':-2}),
                            ('node_weights',{'0':1,'1':0.3})):
            with self.subTest(field=field):
                kw=dict(base);kw[field]=value
                with self.assertRaises((CompositionUnavailable,TypeError)):
                    identify_verified_group_effect(b,src,**kw)
        with self.assertRaises(CompositionUnavailable):
            identify_verified_group_effect(b,src,**dict(base,node_weights={'missing':1,'0':1}))

    def test_named_effect_has_explicit_exposure_and_coefficient_rules(self):
        b=self.b;src=self.a4
        for kind in ('BAD_LABEL', 'SPILLOVER'):
            kw=dict(node_id='0',kind=kind,reference_exposure=0,
                    comparison_exposure=0)
            with self.assertRaises((ValueError,CompositionUnavailable)):
                identify_verified_node_effect(b,src,**kw)
        with self.assertRaises(CompositionUnavailable):
            identify_verified_linear_target(b,src,(ArmLinearTerm('0',1,0,1), ArmLinearTerm('0',1,0,-1)))
        with self.assertRaises(TypeError):
            ArmLinearTerm('0',1,0,0.5)

    def test_recomputed_source_digest_alone_cannot_forge_arm_support(self):
        from pfn_pipeline.identification_batch import _VERSION, _digest
        b=self.b
        data=[[list(arm) for arm in node] for node in b.population_joint_support]
        data[0][1][0] = '1/7'  # false for the known Bernoulli protocol
        corrupt=tuple(tuple(tuple(a) for a in node) for node in data)
        body=dict(version=_VERSION,source_spec_sha256=b.source_spec_sha256,
                  node_ids=b.node_ids,exposure_states=b.exposure_states,
                  joint_support=corrupt,arm_status=b.arm_status,
                  arm_reason=b.arm_reason,target_fingerprints=b.target_fingerprints)
        forged=replace(b,population_joint_support=corrupt,batch_sha256=_digest(body))
        with self.assertRaises(CompositionUnavailable) as caught:
            identify_verified_node_effect(forged,self.a4,node_id='0',kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
        self.assertEqual(caught.exception.reason_code,'SOURCE_ARM_SUPPORT_INDEPENDENT_REPLAY_MISMATCH')

    def test_source_batch_tamper_without_rehash_rejected(self):
        b=self.b
        corrupted=replace(b,batch_sha256='0'*64)
        with self.assertRaises(CompositionUnavailable) as caught:
            identify_verified_node_effect(corrupted,self.a4,node_id='0',kind='DIRECT',
                                          reference_exposure=0,comparison_exposure=0)
        self.assertEqual(caught.exception.reason_code,'SOURCE_BATCH_DIGEST_MISMATCH')

    def test_group_one_unsupported_arm_blocks_entire_composite(self):
        b=batch('D2','strict_majority',STAR,m=0)
        src=a4_source(b)
        with self.assertRaises(CompositionUnavailable):
            identify_verified_group_effect(b,src,kind='TOTAL',
                node_weights={'0':1,'1':1},reference_exposure=0,
                comparison_exposure=1,cohort_authority='STUDY_PROTOCOL',
                cohort_evidence='prespecified baseline population')

    def test_replay_tampering_detected(self):
        b=self.b;src=self.a4
        original=identify_verified_node_effect(b,src,node_id='0',kind='TOTAL',
                                               reference_exposure=0,comparison_exposure=1)
        for field,value in (('identified_functional','0'),('certificate_sha256','bad'),
                            ('population_arm_support',('0','0')),('status','PARTIAL'),
                            ('target_fingerprint','other'),('a4_rule_id','made-up')):
            with self.subTest(field=field):
                with self.assertRaises(CompositionUnavailable):
                    replay_verified_composition(replace(original,**{field:value}))
        with self.assertRaises(CompositionUnavailable):
            replay_verified_composition(replace(original,a4_source=replace(src,admission='PROPOSED')))

    def test_distinct_group_evidence_same_target_different_receipt(self):
        b=self.b;src=self.a4
        kwargs=dict(kind='DIRECT',node_weights={'1':'2','2':'1'},
                    reference_exposure=0,comparison_exposure=0,
                    cohort_authority='STUDY_PROTOCOL')
        a=identify_verified_group_effect(b,src,**kwargs,cohort_evidence='Protocol A')
        c=identify_verified_group_effect(b,src,**kwargs,cohort_evidence='Protocol B')
        self.assertEqual(a.target_fingerprint,c.target_fingerprint)
        self.assertNotEqual(a.certificate_sha256,c.certificate_sha256)

    def test_mean_is_not_fixed_policy_welfare(self):
        b=self.b;src=self.a4
        out=identify_verified_node_effect(b,src,node_id='0',kind='TOTAL',
                                         reference_exposure=0,comparison_exposure=1)
        self.assertNotIn('policy',out.summary())
        self.assertNotIn('policy',out.identified_functional.lower())
        self.assertIsNone(out.estimation_request)


if __name__ == '__main__':
    unittest.main()
