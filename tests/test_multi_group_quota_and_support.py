"""D5 x E1..E5 oracle + R1a/R1b/R2/Batch + v2.5 A6 negative controls."""
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import product
from random import Random

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec,MultiGroupFixedQuotaDesignV25,CompleteRandomizationDesignV1,Assumption)
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec,ExposureSpec,SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import neighbor_set
from pfn_pipeline._internal.identification.randomized_network_arm import (
    _verify_multi_group_joint_support_independently,_verifier_matches_exposure)
from pfn_pipeline.identification import make_multi_group_quota_arm_task,identify,replay_population_identification
from pfn_pipeline.identification_batch import identify_randomized_network_batch,replay_network_arm_batch
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study,fixed_policy_target_from_context,declare_network_a4_source)
from pfn_pipeline.identification_policy_r1b import (
    identify_verified_fixed_policy,replay_verified_fixed_policy,R1bPolicyUnavailable)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature,admit_mean_signature_sufficiency,
    declare_signature_population_source,identify_verified_signature_policy,
    replay_verified_signature_policy,R2PolicyUnavailable)
from pfn_pipeline.identification_support_diagnostics import (
    diagnose_policy_signature_support_v25,replay_policy_signature_support_v25)

NODES=('a','b','c','d','e','f')
GROUPS=(('a','b'),('c','d'),('e','f'))
QUOTAS=(1,1,1)
EDGES=(('a','c'),('b','d'),('c','e'),('d','f'),('e','a'),('f','b'))
EXP={
 'strict_majority':'strict_majority_ties_low',
 'three_level_treated_neighbor_fraction':'three_level_treated_neighbor_fraction',
 'pretreatment_core_collaborator_majority':'pretreatment_core_collaborator_majority',
 'exact_treated_neighbor_count':'exact_treated_neighbor_count',
 'any_treated_neighbor':'any_treated_neighbor',
}
ASSUMPTIONS=('known_assignment_law','full_vector_randomization','consistency',
             'fixed_pretreatment_network','finite_conditional_first_moments')

def network(edges=EDGES,nodes=NODES):
    return NetworkExposureSpec(network_id='multi-group-v25',node_ids=list(nodes),undirected_edges=list(edges))

def assignment():
    return MultiGroupFixedQuotaDesignV25(groups=GROUPS,treated_quotas=QUOTAS)

def task(exp='any_treated_neighbor',node='a',a=1,s=1,design=None,net=None):
    net=net or network();design=design or assignment()
    core={n:(sorted(neighbor_set(net,n))[0],) for n in net.node_ids} if exp=='pretreatment_core_collaborator_majority' else None
    return make_multi_group_quota_arm_task(net,groups=design.groups,treated_quotas=design.treated_quotas,
        node_id=node,own_treatment_value=a,exposure_value=s,exposure_definition=exp,
        core_collaborators=core,source='documented synthetic assignment',
        evidence='explicit finite allocation oracle',admitted=True,
        query_authority='TRUSTED_FIXTURE',synthetic=True)

def study(net=None,design=None):
    net=net or network();design=design or assignment()
    return declare_network_study(network_id=net.network_id,node_order=tuple(net.node_ids),
        undirected_edges=tuple(tuple(e) for e in net.undirected_edges),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W:synthetic',observation_regime='experimental',
        assignment_design=design.model_dump(mode='json'),
        protocol_provenance='documented synthetic independent multi-stratum allocation',
        network_provenance='fixed baseline graph',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')

def a5():
    return tuple(Assumption(name=n,source='demo_specification',confirmed=True,
      evidence=['documented synthetic assignment protocol']) for n in ASSUMPTIONS)

def oracle(net,design,grouping,node,a,s,core=None):
    refs=(set(core[node]) if core is not None else neighbor_set(net,node))
    exp=ExposureSpec(grouping,core)
    res=Fraction(0)
    for bits in product((0,1),repeat=len(net.node_ids)):
        alloc=dict(zip(net.node_ids,bits))
        if alloc[node]!=a:continue
        if exp.classify(sum(alloc[j] for j in refs),len(refs))==s:
            res+=AssignmentSpec(design).full_assignment_probability(net,alloc)
    return res

class TestMultiQuotaD5(unittest.TestCase):
    def test_all_five_exposure_mappings_independent_full_allocation_oracle(self):
        net=network();d=assignment()
        for name,grouping in EXP.items():
            core={n:(sorted(neighbor_set(net,n))[0],) for n in net.node_ids} if name=='pretreatment_core_collaborator_majority' else None
            e=ExposureSpec(grouping,core)
            for node in net.node_ids:
                reference=e.reference_nodes(net,node)
                degree=len(reference) if reference is not None else net.degree_map()[node]
                for a in (0,1):
                    for s in e.states_for_degree(degree):
                        with self.subTest(name=name,node=node,a=a,s=s):
                            expected=oracle(net,d,grouping,node,a,s,core)
                            actual=SupportEngine.evaluate(network=net,assignment=AssignmentSpec(d),exposure=e,
                                node_id=node,own_treatment_value=a,exposure_value=s).joint_probability
                            other=_verify_multi_group_joint_support_independently(net,d,node,a,s,grouping,
                                reference_nodes=frozenset(reference) if reference is not None else None)
                            self.assertEqual(expected,actual)
                            self.assertEqual(expected,other)
            # Full theorem must replay for an actually supported arm.
            positive=next((node,a,s) for node in net.node_ids for a in (0,1)
                for s in e.states_for_degree(len(core[node]) if core else net.degree_map()[node])
                if oracle(net,d,grouping,node,a,s,core)>0)
            r=identify(task(name,*positive));self.assertEqual(r.status,'POINT');
            self.assertEqual(r.verification_status,'VERIFIED')
            self.assertTrue(replay_population_identification(r))

    def test_canonical_group_permutation_and_invalid_partition(self):
        d=MultiGroupFixedQuotaDesignV25(groups=GROUPS,treated_quotas=QUOTAS)
        perm=MultiGroupFixedQuotaDesignV25(groups=(('f','e'),('d','c'),('b','a')),treated_quotas=(1,1,1))
        self.assertEqual(d.model_dump(),perm.model_dump())
        self.assertEqual(task(design=d).target_fingerprint,task(design=perm).target_fingerprint)
        with self.assertRaises(ValueError):MultiGroupFixedQuotaDesignV25(groups=(('a','b'),('b','c'),('e','f')),treated_quotas=QUOTAS)
        with self.assertRaises(ValueError):MultiGroupFixedQuotaDesignV25(groups=GROUPS,treated_quotas=(3,1,1))
        with self.assertRaises(ValueError):MultiGroupFixedQuotaDesignV25(groups=GROUPS[:2],treated_quotas=(1,1))
        with self.assertRaises(ValueError):AssignmentSpec(MultiGroupFixedQuotaDesignV25(groups=GROUPS,
            treated_quotas=QUOTAS))._validate_network(network(nodes=NODES+('extra',)))

    def test_full_policy_probability_and_verified_r1b(self):
        st=study();z=(1,0,1,0,1,0)
        t=fixed_policy_target_from_context(st,z,authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(st,source_id='full-synthetic-operator',operator='NODE_FULL_LAW',
          provenance='documented symbolic population operator',admission='ADMITTED',
          availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES)
        res=identify_verified_fixed_policy(st,t,(src,),assumptions=a5())
        self.assertEqual(res.assignment_probability,'1/8')
        self.assertTrue(replay_verified_fixed_policy(res))
        bad=fixed_policy_target_from_context(st,(1,1,1,1,1,1),authority='TRUSTED_FIXTURE')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(st,bad,(src,),assumptions=a5())

    def test_off_support_all_treated_can_use_e5_if_mean_sufficiency_admitted(self):
        st=study();t=fixed_policy_target_from_context(st,(1,)*6,authority='TRUSTED_FIXTURE')
        s=declare_policy_signature(st,grouping='any_treated_neighbor')
        su=admit_mean_signature_sufficiency(st,s,
            assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
                confirmed=True,evidence=['explicit hypothetical reviewed mean restriction']),covered_nodes=NODES)
        src=declare_signature_population_source(st,s,source_id='signature-node-law',operator='NODE_FULL_LAW',
             outcome_nodes=NODES,admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
             provenance='reviewed hypothetical population operator')
        r=identify_verified_signature_policy(st,t,s,(src,),assumptions=a5(),sufficiency=su)
        self.assertEqual(r.policy_assignment_probability,'0')
        self.assertTrue(all(Fraction(v)>0 for v in r.node_class_support))
        self.assertTrue(replay_verified_signature_policy(r))
        invalid=replace(su,assumption=Assumption(name='mean_signature_sufficiency',
            source='human_confirmation',confirmed=False,evidence=['unconfirmed']))
        with self.assertRaises(R2PolicyUnavailable):
            identify_verified_signature_policy(st,t,s,(src,),assumptions=a5(),sufficiency=invalid)

    def test_d5_batch_replay_and_zero_arms(self):
        b=identify_randomized_network_batch(task('exact_treated_neighbor_count',node='a',a=1,s=1))
        self.assertEqual(b.shape,(6,2,3))
        self.assertTrue(all(x=='POINT' for node in b.arm_status for own in node for x in own))
        self.assertEqual(replay_network_arm_batch(b).batch_sha256,b.batch_sha256)
        tampered=replace(b,batch_sha256='0'*64)
        with self.assertRaises(ValueError):replay_network_arm_batch(tampered)

    def test_seeded_random_networks_with_three_to_five_strata(self):
        rng=Random(25017)
        for i in range(9):
            n=rng.choice((6,7,8));nodes=tuple(f'x{j}' for j in range(n))
            edges=tuple((x,y) for j,x in enumerate(nodes) for y in nodes[j+1:] if rng.random()<.38)
            net=NetworkExposureSpec(network_id=f'rng25-{i}',node_ids=list(nodes),undirected_edges=list(edges))
            parts=[tuple(nodes[k:k+2]) for k in range(0,n,2)]
            quotas=tuple(rng.randint(0,len(g)) for g in parts)
            design=MultiGroupFixedQuotaDesignV25(groups=tuple(parts),treated_quotas=quotas)
            for grouping in ('strict_majority_ties_low','exact_treated_neighbor_count','any_treated_neighbor'):
                for node in nodes:
                    for a in (0,1):
                        for s in ExposureSpec(grouping).states_for_degree(net.degree_map()[node]):
                            calc=SupportEngine.evaluate(network=net,assignment=AssignmentSpec(design),
                                exposure=ExposureSpec(grouping),node_id=node,
                                own_treatment_value=a,exposure_value=s).joint_probability
                            self.assertEqual(calc,oracle(net,design,grouping,node,a,s))
                            self.assertEqual(calc,_verify_multi_group_joint_support_independently(
                                net,design,node,a,s,grouping))

class TestSupportDiagnosticsV25(unittest.TestCase):
    def test_star_zero_support_and_counterfactual_D2_quota(self):
        nodes=tuple(str(x) for x in range(7));edges=tuple(('0',x) for x in nodes[1:])
        net=network(edges=edges,nodes=nodes);st=study(net,CompleteRandomizationDesignV1(m=3))
        target=fixed_policy_target_from_context(st,(1,)*7,authority='TRUSTED_FIXTURE')
        for grouping,expected in [('strict_majority_ties_low',1),('exact_treated_neighbor_count',1),('any_treated_neighbor',0)]:
            s=declare_policy_signature(st,grouping=grouping)
            r=diagnose_policy_signature_support_v25(st,target,s)
            self.assertEqual(r.unsupported_weighted_nodes,expected)
            self.assertEqual(r.full_assignment_probability,'0')
            self.assertEqual(replay_policy_signature_support_v25(r,st,target,s),r)
            if grouping=='strict_majority_ties_low':
                center=next(x for x in r.nodes if x.node_id=='0')
                self.assertEqual(center.signature_probability,'0')
                self.assertEqual(center.feasible_reference_neighbor_counts,(2,))
                self.assertEqual(center.reason_code,'TARGET_EXPOSURE_UNREACHABLE')
                self.assertIn(5,r.counterfactual_d2_quotas_with_full_support)
                self.assertNotIn(3,r.counterfactual_d2_quotas_with_full_support)
            tampered=replace(r,evidence_digest='0'*64)
            with self.assertRaises(ValueError):replay_policy_signature_support_v25(tampered,st,target,s)

    def test_D5_explanation_and_no_automatic_causal_licence(self):
        star=network(edges=tuple(('a',j) for j in NODES[1:]))
        st=study(star)
        target=fixed_policy_target_from_context(st,(1,)*6,authority='TRUSTED_FIXTURE',
             unit_weights=('1','0','0','0','0','0'))
        e4=declare_policy_signature(st,grouping='exact_treated_neighbor_count')
        e5=declare_policy_signature(st,grouping='any_treated_neighbor')
        blocked=diagnose_policy_signature_support_v25(st,target,e4)
        allowed=diagnose_policy_signature_support_v25(st,target,e5)
        self.assertGreater(blocked.unsupported_weighted_nodes,0)
        self.assertEqual(allowed.unsupported_weighted_nodes,0)
        self.assertIsNone(allowed.counterfactual_d2_quotas_with_full_support)
        self.assertTrue(any(row.by_stratum_constraints for row in allowed.nodes))
        self.assertIn('NOT establish',allowed.disclaimer)
        self.assertEqual(replay_policy_signature_support_v25(allowed,st,target,e5),allowed)
        with self.assertRaises(ValueError):
            diagnose_policy_signature_support_v25(st,target,declare_policy_signature(study(network(edges=(('a','b'),))),grouping='any_treated_neighbor'))


class TestV25Showcase(unittest.TestCase):
    def test_45_cross_topology_and_ring300_real_proofs(self):
        from examples.run_multi_group_and_diagnostics import (
            run_matrix,run_support_comparison,run_large_ring)
        matrix=run_matrix()
        self.assertEqual(matrix['cases'],45)
        self.assertEqual(matrix['status_counts'],{
            'POINT_ARM_VERIFIED':43,'POINT_ON_VALID_NODE':1,
            'INVALID_GLOBAL_MAPPING':1})
        self.assertEqual({x['graph'] for x in matrix['rows']},
                         {'path','ring','star','complete','bipartite','community',
                          'small_world_like','hub_scale_free_like','disconnected_with_isolate'})
        star=run_support_comparison()
        self.assertEqual([next(n['signature_probability'] for n in x['nodes'] if n['node_id']=='0')
                         for x in star['comparisons']],['0','0','3/7'])
        ring=run_large_ring()
        self.assertEqual(ring['nodes'],300)
        self.assertEqual(ring['groups'],60)
        self.assertEqual([x['joint_support'] for x in ring['rows']],['2/5','1/5','1/5'])
        self.assertTrue(all(x['verification']=='VERIFIED' for x in ring['rows']))

    def test_d4_reachable_signature_count_has_gap_not_interval(self):
        from pfn_pipeline._internal.identification.schemas import ClusterBernoulliDesignV24
        net=network(edges=(('a','c'),('a','d')),nodes=('a','b','c','d'))
        d=ClusterBernoulliDesignV24(clusters=(('a','b'),('c','d')),
                                   cluster_probabilities=('1/2','1/2'))
        st=study(net,d)
        target=fixed_policy_target_from_context(st,(1,1,1,0),authority='TRUSTED_FIXTURE',
                                                unit_weights=('1','0','0','0'))
        sig=declare_policy_signature(st,grouping='exact_treated_neighbor_count')
        diagnostic=diagnose_policy_signature_support_v25(st,target,sig)
        self.assertEqual(diagnostic.unsupported_weighted_nodes,1)
        self.assertEqual(diagnostic.nodes[0].feasible_reference_neighbor_counts,(0,2))
        self.assertEqual(diagnostic.nodes[0].policy_treated_reference_neighbors,1)
        self.assertEqual(diagnostic.nodes[0].signature_probability,'0')
        self.assertEqual(diagnostic.nodes[0].reason_code,'TARGET_EXPOSURE_UNREACHABLE')

class TestD5Compatibility(unittest.TestCase):
    def test_d5_e4_composition_uses_verified_batch(self):
        from pfn_pipeline.identification_a4_shadow import declare_a4_source
        from pfn_pipeline.identification_composition import (
            ArmLinearTerm, identify_verified_linear_target, replay_verified_composition)
        b=identify_randomized_network_batch(task('exact_treated_neighbor_count',node='a',a=1,s=1))
        self.assertEqual(b.cell('a',1,0)['status'],'POINT')
        self.assertEqual(b.cell('a',1,1)['status'],'POINT')
        source=declare_a4_source(b.template,source_id='v25-composition-population-operator',
            operator='NODE_FULL_LAW',provenance='synthetic population operator',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=b.node_ids,node_order=b.node_ids)
        result=identify_verified_linear_target(b,source,(
            ArmLinearTerm('a',1,1,1),ArmLinearTerm('a',1,0,-1)))
        self.assertEqual(result.status,'POINT')
        self.assertEqual(replay_verified_composition(result).certificate_sha256,
                         result.certificate_sha256)

    def test_d5_business_route_keeps_separate_theorem_receipts(self):
        from pfn_pipeline.identification_business import (
            ArmInquiryV21,FixedPolicyInquiryV21,identify_network_business_query,
            replay_verified_business_outcome)
        arm=identify_network_business_query(ArmInquiryV21(task()))
        self.assertEqual((arm.status,arm.route),('POINT','R1A_RANDOMIZED_ARM'))
        self.assertTrue(replay_verified_business_outcome(arm))
        st=study()
        t=fixed_policy_target_from_context(st,(1,0,1,0,1,0),authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(st,source_id='v25-business-full',operator='NODE_FULL_LAW',
            provenance='synthetic operator',admission='ADMITTED',
            availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES)
        pol=identify_network_business_query(FixedPolicyInquiryV21(st,t,a5(),(src,)))
        self.assertEqual((pol.status,pol.route),('POINT','R1B_FULL_ASSIGNMENT'))
        self.assertTrue(replay_verified_business_outcome(pol))
