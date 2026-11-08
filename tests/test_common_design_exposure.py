"""v2.4 independent finite-allocation oracles, source gates and theorem replay.

For D4, enumeration is over the actual CLUSTER law, never a fictional
node-independent assignment. E4/E5 have explicit pre-treatment meaning.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
from random import Random
import unittest

from pfn_pipeline.identification import (
    identify, replay_population_identification,
    make_cluster_bernoulli_arm_task, make_complete_randomization_arm_task,
    make_two_group_quota_arm_task, make_heterogeneous_bernoulli_arm_task,
)
from pfn_pipeline.identification_batch import identify_randomized_network_batch, replay_network_arm_batch
from pfn_pipeline._internal.identification.schemas import (
    Assumption, NetworkExposureSpec, ClusterBernoulliDesignV24,
)
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import neighbor_set
from pfn_pipeline._internal.identification.randomized_network_arm import (
    PUBLIC_TO_GROUP, _verify_heterogeneous_joint_support_independently,
    _verify_two_group_joint_support_independently, _verify_joint_support_independently,
    _verifier_matches_exposure,
)
from pfn_pipeline._internal.identification.randomized_arm_family.cluster_verifier import verify_cluster_joint_support
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context, declare_network_a4_source,
)
from pfn_pipeline.identification_policy_r1b import identify_verified_fixed_policy, R1bPolicyUnavailable
from pfn_pipeline.identification_policy_r2 import (
    R2PolicyUnavailable, declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source, identify_verified_signature_policy,
    replay_verified_signature_policy,
)

NODES=('a','b','c','d','e')
EDGES=(('a','b'),('b','c'),('c','d'),('d','e'))
D4={'clusters':(('a','b'),('c','d'),('e',)), 'cluster_probabilities':('1/2','2/3','1/4')}
D4_JSON={'kind':'cluster_bernoulli_binary_v2_4',**D4}
E_MAP={
    'strict_majority':'strict_majority_ties_low',
    'three_level_treated_neighbor_fraction':'three_level_treated_neighbor_fraction',
    'pretreatment_core_collaborator_majority':'pretreatment_core_collaborator_majority',
    'exact_treated_neighbor_count':'exact_treated_neighbor_count',
    'any_treated_neighbor':'any_treated_neighbor',
}
A5_NAMES=('known_assignment_law','full_vector_randomization','consistency',
          'fixed_pretreatment_network','finite_conditional_first_moments')

def a5():
    return tuple(Assumption(name=n,source='demo_specification',confirmed=True,
            evidence=['reviewed synthetic assignment']) for n in A5_NAMES)

def graph(edges=EDGES,nodes=NODES):
    return NetworkExposureSpec(network_id='v24-graph', node_ids=list(nodes),
                               undirected_edges=list(edges))

def study(design=D4_JSON,edges=EDGES,nodes=NODES):
    return declare_network_study(network_id='v24-graph',node_order=tuple(nodes),
        undirected_edges=tuple(edges),treatment_variable='AI',outcome_variable='sales',
        outcome_kind='continuous',context_reference='W:synthetic',
        observation_regime='experimental',assignment_design=design,
        protocol_provenance='synthetic documented design',
        network_provenance='fixed pretreatment network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')

def get_design(name):
    if name=='D1':
        return make_heterogeneous_bernoulli_arm_task, dict(propensities={n:p for n,p in zip(NODES,('1/2','1/3','2/3','3/4','1/4'))})
    if name=='D2':
        return make_complete_randomization_arm_task, dict(m=3)
    if name=='D3':
        return make_two_group_quota_arm_task, dict(groups=(NODES[:3],NODES[3:]),treated_quotas=(2,1))
    return make_cluster_bernoulli_arm_task, D4

def task(net, d='D4',exp='any_treated_neighbor',node='b',a=1,s=1,authority='TRUSTED_FIXTURE',admitted=True):
    maker,opts=get_design(d)
    core={n:(sorted(neighbor_set(net,n))[0],) for n in net.node_ids} if exp=='pretreatment_core_collaborator_majority' else None
    return maker(net,**opts,node_id=node,own_treatment_value=a,exposure_value=s,
        exposure_definition=exp,core_collaborators=core,source='reviewed synthetic protocol',
        evidence='finite allocation enumeration',admitted=admitted,
        query_authority=authority,synthetic=True)

def exhaustive_arm(net, design, grouping, node, a, s, core=None):
    exposure=ExposureSpec(grouping,core)
    ref=exposure.reference_nodes(net,node)
    neighbors=ref if ref is not None else neighbor_set(net,node)
    q=AssignmentSpec(design)
    total=Fraction(0)
    for bits in product((0,1),repeat=len(net.node_ids)):
        z=dict(zip(net.node_ids,bits))
        if z[node]!=a:
            continue
        if exposure.classify(sum(z[j] for j in neighbors),len(neighbors))!=s:
            continue
        total+=q.full_assignment_probability(net,z)
    return total

class TestD4E4E5(unittest.TestCase):
    def test_all_design_exposure_combinations_independent_exact_oracle(self):
        net=graph()
        for d in ('D1','D2','D3','D4'):
            for exp,g in E_MAP.items():
                with self.subTest(design=d, exposure=exp):
                    seed=task(net,d,exp,node='b',s=0)
                    spec=seed.identification_spec
                    from pfn_pipeline._internal.identification.schemas import IdentificationSpec
                    ss=IdentificationSpec.model_validate(spec)
                    design=ss.randomized_network_arm_theorem_contract.design
                    core=ss.randomized_network_arm_theorem_contract.core_collaborators
                    for node in net.node_ids:
                        reference=ExposureSpec(g,core).reference_nodes(net,node)
                        degree=len(reference) if reference is not None else net.degree_map()[node]
                        for a in (0,1):
                            for s in ExposureSpec(g,core).states_for_degree(degree):
                                oracle=exhaustive_arm(net,design,g,node,a,s,core)
                                proposer=SupportEngine.evaluate(network=net,assignment=AssignmentSpec(design),
                                    exposure=ExposureSpec(g,core),node_id=node,
                                    own_treatment_value=a,exposure_value=s).joint_probability
                                self.assertEqual(oracle,proposer,(d,exp,node,a,s))
                                if d=='D4':
                                    verifier=verify_cluster_joint_support(net,design,node,a,s,g,
                                        _verifier_matches_exposure,reference_nodes=reference)
                                    self.assertEqual(verifier,oracle)
                    # End-to-end: select a positive arm and replay the real theorem.
                    chosen=next((node,a,s) for node in net.node_ids for a in (0,1)
                        for s in ExposureSpec(g,core).states_for_degree(
                          len(core[node]) if core is not None else net.degree_map()[node])
                        if exhaustive_arm(net,design,g,node,a,s,core)>0)
                    r=identify(task(net,d,exp,*chosen))
                    self.assertEqual(r.status,'POINT')
                    self.assertEqual(r.verification_status,'VERIFIED')
                    self.assertTrue(replay_population_identification(r))

    def test_same_cluster_exposure_is_not_independent_bernoulli(self):
        net=graph(edges=(('a','b'),('b','c')),nodes=('a','b','c'))
        d=ClusterBernoulliDesignV24(clusters=(('a','b'),('c',)),cluster_probabilities=('1/2','1/2'))
        v=SupportEngine.evaluate(network=net,assignment=AssignmentSpec(d),
            exposure=ExposureSpec('any_treated_neighbor'),node_id='a',
            own_treatment_value=1,exposure_value=0).joint_probability
        self.assertEqual(v,0)  # its only neighbor b shares T_a always
        ok=identify(make_cluster_bernoulli_arm_task(net,clusters=d.clusters,
            cluster_probabilities=d.cluster_probabilities,node_id='a',
            own_treatment_value=1,exposure_value=0,
            exposure_definition='any_treated_neighbor',source='protocol',evidence='cluster-law oracle',
            synthetic=True,admitted=True,query_authority='TRUSTED_FIXTURE'))
        self.assertEqual(ok.result.get('reason_code'),'ZERO_ARM_SUPPORT')

    def test_cluster_partition_and_probability_malformed_rejected(self):
        with self.assertRaises(ValueError):ClusterBernoulliDesignV24(clusters=(('a','b'),('b','c')),cluster_probabilities=('1/2','1/3'))
        with self.assertRaises(ValueError):ClusterBernoulliDesignV24(clusters=(('a','b'),),cluster_probabilities=('-1/2',))
        with self.assertRaises(ValueError):
            AssignmentSpec(ClusterBernoulliDesignV24(
                clusters=(('a','b'),('c',)), cluster_probabilities=('1/2','1/2')
            ))._validate_network(graph())
        with self.assertRaises(ValueError):ClusterBernoulliDesignV24(clusters=(('a',),),cluster_probabilities=('nan',))

    def test_dynamic_exact_count_states_and_isolates(self):
        net=graph(edges=(('a','b'),),nodes=('a','b','c'))
        r=identify(make_complete_randomization_arm_task(net,m=1,node_id='c',own_treatment_value=0,
            exposure_value=0,exposure_definition='exact_treated_neighbor_count',
            source='synthetic',evidence='isolate protocol',admitted=True,
            query_authority='TRUSTED_FIXTURE',synthetic=True))
        self.assertEqual(r.status,'POINT');self.assertTrue(replay_population_identification(r))
        with self.assertRaises(ValueError): make_complete_randomization_arm_task(net,m=1,node_id='c',
            own_treatment_value=1,exposure_value=1,exposure_definition='exact_treated_neighbor_count',
            source='x',evidence='y',admitted=True,query_authority='TRUSTED_FIXTURE',synthetic=True)
        for exp in ('any_treated_neighbor',):
            r=identify(make_complete_randomization_arm_task(net,m=1,node_id='c',own_treatment_value=1,
              exposure_value=0,exposure_definition=exp,source='x',evidence='y',admitted=True,
              query_authority='TRUSTED_FIXTURE',synthetic=True))
            self.assertEqual(r.status,'POINT')

    def test_batch_d4_e4_rectangular_padding_and_replay(self):
        net=graph()
        for exp in ('strict_majority','any_treated_neighbor','exact_treated_neighbor_count'):
            # Seed node with a clearly positive cell, no assumption of all arms supported.
            b=identify_randomized_network_batch(task(net,'D4',exp,node='b',a=1,s=1))
            self.assertEqual(b.shape[0],5)
            self.assertEqual(b.shape[2],3 if exp=='exact_treated_neighbor_count' else 2)
            self.assertEqual(replay_network_arm_batch(b).batch_sha256,b.batch_sha256)
            if exp=='exact_treated_neighbor_count':
                self.assertEqual(b.cell('a',0,2)['reason_code'],'EXPOSURE_STATE_OUTSIDE_NODE_DEGREE')

    def test_r1b_full_cluster_policy_and_mixed_cluster_zero_support(self):
        st=study(); aa=a5();
        src=declare_network_a4_source(st,source_id='full',operator='NODE_FULL_LAW',
          provenance='reviewed conditional full law',admission='ADMITTED',
          availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES)
        good=fixed_policy_target_from_context(st,(1,1,0,0,1),authority='TRUSTED_FIXTURE')
        identified=identify_verified_fixed_policy(st,good,(src,),assumptions=aa)
        self.assertEqual(identified.assignment_probability,str(Fraction(1,2)*Fraction(1,3)*Fraction(1,4)))
        bad=fixed_policy_target_from_context(st,(1,0,0,0,1),authority='TRUSTED_FIXTURE')
        with self.assertRaises(R1bPolicyUnavailable):identify_verified_fixed_policy(st,bad,(src,),assumptions=aa)

    def test_r2_policy_d4_by_e4_e5_with_exact_oracle(self):
        st=study();target=fixed_policy_target_from_context(st,(1,1,0,0,1),authority='TRUSTED_FIXTURE')
        net=st.network();design=st.design()
        for g in ('exact_treated_neighbor_count','any_treated_neighbor'):
            with self.subTest(signature=g):
                sig=declare_policy_signature(st,grouping=g)
                suf=admit_mean_signature_sufficiency(st,sig,
                    assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
                      confirmed=True,evidence=['explicit reviewed mean restriction']),covered_nodes=NODES)
                src=declare_signature_population_source(st,sig,source_id='signed',operator='NODE_FULL_LAW',
                    outcome_nodes=NODES,admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
                    provenance='reviewed synthetic full law')
                r=identify_verified_signature_policy(st,target,sig,(src,),assumptions=a5(),sufficiency=suf)
                self.assertEqual(r.status,'POINT');self.assertTrue(replay_verified_signature_policy(r))
                for node,a,s,pi in zip((x[0] for x in r.policy_node_classes),
                    (x[1] for x in r.policy_node_classes),(x[2] for x in r.policy_node_classes),r.node_class_support):
                    self.assertEqual(Fraction(pi),exhaustive_arm(net,design,g,node,a,s))
                denied=replace(suf,assumption=Assumption(name='mean_signature_sufficiency',
                    source='human_confirmation',confirmed=False,evidence=['unconfirmed']))
                with self.assertRaises(R2PolicyUnavailable):
                    identify_verified_signature_policy(st,target,sig,(src,),assumptions=a5(),sufficiency=denied)

    def test_d4_canonical_cluster_permutation_same_study_identity(self):
        net=graph()
        original=ClusterBernoulliDesignV24(**D4)
        permuted=ClusterBernoulliDesignV24(
            clusters=(('e',),('d','c'),('b','a')),
            cluster_probabilities=('1/4','2/3','1/2'))
        self.assertEqual(original.model_dump(),permuted.model_dump())
        self.assertEqual(AssignmentSpec(original).full_assignment_probability(net,
            dict(zip(NODES,(1,1,0,0,1)))),Fraction(1,24))

    def test_e4_exact_count_can_exceed_two(self):
        nodes=('a','b','c','d');net=graph(edges=tuple(('a',n) for n in nodes[1:]),nodes=nodes)
        r=identify(make_complete_randomization_arm_task(net,m=4,node_id='a',
            own_treatment_value=1,exposure_value=3,
            exposure_definition='exact_treated_neighbor_count',
            source='reviewed protocol',evidence='all treated',admitted=True,
            synthetic=True,query_authority='TRUSTED_FIXTURE'))
        self.assertEqual(r.status,'POINT');self.assertEqual(r.result['certificate']['query_arm'],[1,3])
        self.assertTrue(replay_population_identification(r))

    def test_r2_e4_typed_signature_source_cells_and_dynamic_guard(self):
        st=study();target=fixed_policy_target_from_context(st,(1,1,0,0,1),authority='TRUSTED_FIXTURE')
        sig=declare_policy_signature(st,grouping='exact_treated_neighbor_count')
        suff=admit_mean_signature_sufficiency(st,sig,
                assumption=Assumption(name='mean_signature_sufficiency',
                    source='human_confirmation',confirmed=True,
                    evidence=['explicit reviewed mean restriction']),covered_nodes=NODES)
        full=declare_signature_population_source(st,sig,source_id='node-full',operator='NODE_FULL_LAW',
                 outcome_nodes=NODES,admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
                 provenance='reviewed source')
        reference=identify_verified_signature_policy(st,target,sig,(full,),assumptions=a5(),sufficiency=suff)
        cells=reference.policy_node_classes
        source=declare_signature_population_source(st,sig,source_id='exact-classes',
            operator='NODE_SIGNATURE_MEANS',outcome_nodes=NODES,signature_cells=cells,
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='reviewed exact cells')
        r=identify_verified_signature_policy(st,target,sig,(source,),assumptions=a5(),sufficiency=suff)
        self.assertEqual(r.policy_node_classes,cells)
        self.assertTrue(replay_verified_signature_policy(r))
        bad_source=declare_signature_population_source(st,sig,source_id='bad-classes',
            operator='NODE_SIGNATURE_MEANS',outcome_nodes=NODES,
            signature_cells=cells+(('a',1,2),),
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='invalid degree-1 node exposure')
        with self.assertRaises(R2PolicyUnavailable) as err:
            identify_verified_signature_policy(st,target,sig,(bad_source,),assumptions=a5(),sufficiency=suff)
        self.assertEqual(err.exception.reason_code,'A4_SIGNATURE_INFORMATION_INSUFFICIENT')

    def test_non_er_ring300_d4_e4_e5_verified(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from examples.run_large_ring_cluster import run
        with TemporaryDirectory() as directory:
            data=run(Path(directory))
            self.assertEqual(data['n_nodes'],300)
            self.assertEqual(data['cluster_count'],150)
            self.assertEqual([(x['exposure'],x['joint_support']) for x in data['entries']],
                [('exact_treated_neighbor_count','1/4'),
                 ('any_treated_neighbor','1/2'),('strict_majority','1/4')])
            self.assertTrue(all(x['verification']=='VERIFIED' for x in data['entries']))

    def test_180_cross_topology_demo_is_executed_and_conservative(self):
        from examples.run_common_design_exposure import run_matrix, star_support_demo
        matrix=run_matrix();self.assertEqual(matrix['combination_count'],180)
        self.assertEqual(matrix['status_counts'],{
            'INVALID_GLOBAL_MAPPING':4,'POINT_ARM_VERIFIED':172,'POINT_ON_ELIGIBLE_NODE':4})
        self.assertEqual({v['design'] for v in matrix['entries']},{'D1','D2','D3','D4'})
        star=star_support_demo()
        self.assertEqual([(v['exposure'],v['status'],v['signature_support']['0']) for v in star['entries']],
            [('E1','UNSUPPORTED','0'),('E4','UNSUPPORTED','0'),('E5','POINT','3/7')])

    def test_e4_dynamic_batch_supports_verified_linear_composition(self):
        from pfn_pipeline.identification_a4_shadow import declare_a4_source
        from pfn_pipeline.identification_composition import (
            ArmLinearTerm, identify_verified_linear_target, replay_verified_composition,
        )
        net=graph()
        b=identify_randomized_network_batch(task(net,'D4','exact_treated_neighbor_count',
                                                   node='b',a=1,s=1))
        self.assertEqual(b.exposure_states,(0,1,2))
        # Both cells are substantively supported and have unequal exposure counts.
        positive=[s for s in b.exposure_states if b.cell('b',1,s)['status']=='POINT']
        self.assertGreaterEqual(len(positive),2)
        source=declare_a4_source(b.template,source_id='explicit-population-operator',
            operator='NODE_FULL_LAW',provenance='reviewed synthetic experiment',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=b.node_ids,node_order=b.node_ids)
        out=identify_verified_linear_target(b,source,(
            ArmLinearTerm('b',1,positive[0],-1),ArmLinearTerm('b',1,positive[-1],1)
        ))
        self.assertEqual(out.status,'POINT')
        self.assertEqual(replay_verified_composition(out).certificate_sha256,out.certificate_sha256)

    def test_seeded_small_graph_random_d4_oracle_including_boundary_probabilities(self):
        """D4 proposer/independent polynomial vs full allocation, even with p=0 or 1."""
        rng=Random(24017)
        for iteration in range(12):
            nodes=tuple(f'x{i}' for i in range(5))
            edges=tuple((u,v) for i,u in enumerate(nodes) for v in nodes[i+1:]
                        if rng.random()<.4)
            net=NetworkExposureSpec(network_id=f'v24-random-{iteration}',
                node_ids=list(nodes),undirected_edges=list(edges))
            clusters=[]
            ix=0
            while ix<len(nodes):
                k=rng.randint(1, min(3,len(nodes)-ix))
                clusters.append(nodes[ix:ix+k]);ix+=k
            probs=tuple(rng.choice(('0','1','1/2','1/3','2/3')) for _ in clusters)
            d=ClusterBernoulliDesignV24(clusters=tuple(clusters),cluster_probabilities=probs)
            for grouping in ('exact_treated_neighbor_count','any_treated_neighbor',
                             'strict_majority_ties_low'):
                for node in nodes:
                    degree=net.degree_map()[node]
                    for a in (0,1):
                        for state in ExposureSpec(grouping).states_for_degree(degree):
                            expected=exhaustive_arm(net,d,grouping,node,a,state)
                            got=SupportEngine.evaluate(network=net, assignment=AssignmentSpec(d),
                                exposure=ExposureSpec(grouping),node_id=node,
                                own_treatment_value=a,exposure_value=state).joint_probability
                            verifier=verify_cluster_joint_support(net,d,node,a,state,grouping,
                                _verifier_matches_exposure)
                            self.assertEqual((got,verifier),(expected,expected),
                                (iteration,grouping,node,a,state,probs))

    def test_star_7_signature_support_remedy_does_not_prove_sufficiency(self):
        nodes=('h','u1','u2','u3','u4','u5','u6')
        edges=tuple(('h',x) for x in nodes[1:])
        net=graph(edges,nodes)
        d={'kind':'complete_randomization_binary_v1','m':3}
        st=study(d,edges,nodes)
        t=fixed_policy_target_from_context(st,(1,)*7,authority='TRUSTED_FIXTURE')
        for g,expected in [('strict_majority_ties_low',False),
                           ('exact_treated_neighbor_count',False),
                           ('any_treated_neighbor',True)]:
            sig=declare_policy_signature(st,grouping=g)
            suf=admit_mean_signature_sufficiency(st,sig,
                assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
                    confirmed=True,evidence=['synthetic accepted response model']),covered_nodes=nodes)
            src=declare_signature_population_source(st,sig,source_id='known',operator='NODE_FULL_LAW',
                outcome_nodes=nodes,admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
                provenance='declared synthetic total population')
            if expected:
                r=identify_verified_signature_policy(st,t,sig,(src,),assumptions=a5(),sufficiency=suf)
                self.assertEqual(r.policy_assignment_probability,'0')
                self.assertEqual(len(r.policy_node_classes),7)
            else:
                with self.assertRaises(R2PolicyUnavailable) as error:
                    identify_verified_signature_policy(st,t,sig,(src,),assumptions=a5(),sufficiency=suf)
                self.assertEqual(error.exception.reason_code,'ZERO_POLICY_SIGNATURE_SUPPORT')

if __name__=='__main__': unittest.main()
