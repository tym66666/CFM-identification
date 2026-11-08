"""v2.7 D6 finite randomized-saturation design: real theorem, independent oracle, denial.

These tests verify exact design/support and *admitted* theorem premises, not the
empirical truth of any exclusion or exchangeability premise or a PFN estimate.
"""
from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from fractions import Fraction
from itertools import product
import unittest

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, TwoStageQuotaMixtureDesignV27,
    MultiGroupFixedQuotaDesignV25, Assumption,
)
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import neighbor_set
from pfn_pipeline._internal.identification.randomized_arm_family.two_stage_verifier import (
    original_integer_polynomial, original_assignment_mass, independent_joint_support,
)
from pfn_pipeline._internal.identification.randomized_arm_family.two_stage_a5 import (
    D6_EXCLUSION,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    _verifier_matches_exposure,
)
from pfn_pipeline.identification import (
    make_two_stage_quota_arm_task, identify, replay_population_identification,
)
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_composition import (
    identify_verified_node_effect, replay_verified_composition,
)
from pfn_pipeline.identification_batch import (
    identify_randomized_network_batch, replay_network_arm_batch,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context,
    declare_network_a4_source,
)
from pfn_pipeline.identification_policy_r1b import (
    identify_verified_fixed_policy, replay_verified_fixed_policy, R1bPolicyUnavailable,
)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source, identify_verified_signature_policy,
    replay_verified_signature_policy, R2PolicyUnavailable,
)
from pfn_pipeline.identification_support_diagnostics import (
    diagnose_policy_signature_support_v25, replay_policy_signature_support_v25,
)
from pfn_pipeline.identification_business import (
    ArmInquiryV21, FixedPolicyInquiryV21, identify_network_business_query,
    replay_verified_business_outcome,
)
from predevelopment.two_stage_exact_oracle import TwoStageQuotaMixtureDraft

NODES = tuple('abcdef')
GROUPS = (('a','b'),('c','d'),('e','f'))
PROFILES = ((1,1,1),(2,1,0))
PROBABILITIES = ('1/2','1/2')
EDGES = (('a','c'),('a','e'),('b','d'),('b','f'),('c','e'),('d','f'))
BASE_ASSUMPTIONS = ('known_assignment_law','full_vector_randomization','consistency',
                    'fixed_pretreatment_network','finite_conditional_first_moments')
MAPPINGS = (
    ('strict_majority','strict_majority_ties_low'),
    ('three_level_treated_neighbor_fraction','three_level_treated_neighbor_fraction'),
    ('pretreatment_core_collaborator_majority','pretreatment_core_collaborator_majority'),
    ('exact_treated_neighbor_count','exact_treated_neighbor_count'),
    ('any_treated_neighbor','any_treated_neighbor'),
)


def network(nodes=NODES, edges=EDGES):
    return NetworkExposureSpec(network_id='D6-shared-test-network',node_ids=list(nodes),
                               undirected_edges=list(edges))


def design(groups=GROUPS, profiles=PROFILES, probs=PROBABILITIES):
    return TwoStageQuotaMixtureDesignV27(groups=groups,quota_profiles=profiles,
                                          profile_probabilities=probs)


def draft(d=None):
    d=d or design()
    return TwoStageQuotaMixtureDraft(tuple(n for g in d.groups for n in g), d.groups,
                                      tuple(zip(d.quota_profiles,d.profile_probabilities)))


def core(net):
    return {n: (sorted(neighbor_set(net,n))[0],) for n in net.node_ids}


def task(*,net=None, d=None, exp='strict_majority', node='a', a=1, s=1,
         admit_exclusion=True):
    net=net or network();d=d or design()
    return make_two_stage_quota_arm_task(net,groups=d.groups,
        quota_profiles=d.quota_profiles,profile_probabilities=d.profile_probabilities,
        node_id=node,own_treatment_value=a,exposure_value=s,
        source='synthetic reviewed two-stage randomization protocol',
        evidence='controlled toy study with explicit scientific assumptions',
        exposure_definition=exp,
        core_collaborators=core(net) if exp=='pretreatment_core_collaborator_majority' else None,
        admitted=True,profile_exclusion_admitted=admit_exclusion,
        query_authority='TRUSTED_FIXTURE',synthetic=True)


def study(net=None,d=None):
    net=net or network();d=d or design()
    return declare_network_study(network_id=net.network_id,node_order=tuple(net.node_ids),
        undirected_edges=tuple(tuple(e) for e in net.undirected_edges),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W:synthetic',observation_regime='experimental',
        assignment_design=d.model_dump(mode='json'),
        protocol_provenance='documented explicit first-stage lottery and second-stage draws',
        network_provenance='fixed baseline collaboration graph',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def assumptions(admit_exclusion=True,source='human_confirmation'):
    base=tuple(Assumption(name=n,source='demo_specification',confirmed=True,
                     evidence=['reviewed synthetic known randomization']) for n in BASE_ASSUMPTIONS)
    extra=Assumption(name=D6_EXCLUSION,source=source,
            confirmed=admit_exclusion,evidence=['explicit no-direct-profile-effect scientific assumption'])
    return base+(extra,)


def population_a4(st):
    return declare_network_a4_source(st,source_id='D6-full-node-law',operator='NODE_FULL_LAW',
        provenance='declared synthetic symbolic population outcome operator',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=st.node_order)


def original_joint(net,d,exposure,node,a,s,ref):
    dr=draft(d); total=Fraction(0)
    for bits in product((0,1),repeat=len(net.node_ids)):
        z=dict(zip(net.node_ids,bits)); k=sum(z[v] for v in ref)
        if z[node]==a and exposure.classify(k,len(ref))==s:
            total+=dr.full_q(tuple(z[v] for v in dr.node_order))
    return total


class TestTwoStageD6(unittest.TestCase):
    def test_canonical_finite_exact_protocol_and_invalid_protocols(self):
        original=design()
        perm=design(groups=(('f','e'),('b','a'),('d','c')),
            profiles=((1,1,1),(0,2,1)),probs=('1/2','1/2'))
        self.assertEqual(original.model_dump(),perm.model_dump())
        self.assertEqual(task(d=original).identification_spec,task(d=perm).identification_spec)
        invalid=(
            dict(groups=(('a','b'),('b','c')),quota_profiles=((1,1),),profile_probabilities=('1',)),
            dict(groups=GROUPS,quota_profiles=((3,1,1),),profile_probabilities=('1',)),
            dict(groups=GROUPS,quota_profiles=((1,1,1),),profile_probabilities=('1/2',)),
            dict(groups=GROUPS,quota_profiles=((1,1,1),(1,1,1)),profile_probabilities=('1/2','1/2')),
            dict(groups=GROUPS,quota_profiles=PROFILES,profile_probabilities=('0','1')),
            dict(groups=GROUPS,quota_profiles=PROFILES,profile_probabilities=('0.3','0.6')),
            dict(groups=GROUPS,quota_profiles=PROFILES,profile_probabilities=('nan','1')),
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                TwoStageQuotaMixtureDesignV27(**kwargs)
        with self.assertRaises(ValueError):
            AssignmentSpec(original)._validate_network(network(nodes=NODES+('x',)))

    def test_independent_full_assignment_and_all_five_exposure_joint_support(self):
        net=network();d=design();assignment=AssignmentSpec(d)
        dr=draft(d)
        total=Fraction(0)
        for bits in product((0,1),repeat=len(NODES)):
            alloc=dict(zip(NODES,bits))
            q=assignment.full_assignment_probability(net,alloc)
            self.assertEqual(q,original_assignment_mass(NODES,d,bits))
            self.assertEqual(q,dr.full_q(bits))
            total+=q
        self.assertEqual(total,1)
        for name,grouping in MAPPINGS:
            cm=core(net) if name=='pretreatment_core_collaborator_majority' else None
            exposure=ExposureSpec(grouping,cm)
            for node in NODES:
                references=exposure.reference_nodes(net,node)
                ref=frozenset(references if references is not None else neighbor_set(net,node))
                for a in (0,1):
                    law=assignment.conditional_neighbor_count_law(net,node,a,ref)
                    independent=original_integer_polynomial(net,d,node,a,ref)
                    self.assertEqual(sum(independent),law.own_probability)
                    self.assertEqual(independent,tuple(law.own_probability*p for p in law.conditional_count_mass))
                    for s in exposure.states_for_degree(len(ref)):
                        with self.subTest(exposure=name,node=node,a=a,s=s):
                            expected=original_joint(net,d,exposure,node,a,s,ref)
                            proposer=SupportEngine.evaluate(network=net,assignment=assignment,
                                exposure=exposure,node_id=node,own_treatment_value=a,
                                exposure_value=s).joint_probability
                            verifier=independent_joint_support(net,d,node,a,s,grouping,
                                _verifier_matches_exposure,reference_nodes=ref)
                            self.assertEqual(expected,proposer)
                            self.assertEqual(expected,verifier)

    def test_posterior_stage_one_weights_not_unconditional(self):
        nd=('a','b','c','d'); gr=(('a','b'),('c','d'))
        d=design(gr,((0,1),(2,1)),('1/2','1/2'))
        net=network(nodes=nd,edges=(('a','b'),('a','c'),('b','d')))
        own=AssignmentSpec(d).conditional_neighbor_count_law(net,'a',1,frozenset(('b','c')))
        self.assertEqual(own.own_probability,Fraction(1,2))
        self.assertEqual(own.conditional_count_mass,(Fraction(0),Fraction(1,2),Fraction(1,2)))
        self.assertEqual(original_integer_polynomial(net,d,'a',1,frozenset(('b','c'))),
                         (Fraction(0),Fraction(1,4),Fraction(1,4)))
        # A full stage-one profile with no treated a must not trigger hypergeometric division by zero.
        only=design(gr,((0,1),),('1',))
        unsupported=AssignmentSpec(only).conditional_neighbor_count_law(net,'a',1)
        self.assertEqual(unsupported.own_probability,0)
        self.assertFalse(any(unsupported.conditional_count_mass))

    def test_r1a_formal_arm_all_exposures_and_A5_fail_closed(self):
        net=network();d=design()
        for name,grouping in MAPPINGS:
            exp=ExposureSpec(grouping,core(net) if name=='pretreatment_core_collaborator_majority' else None)
            node='a';ref=exp.reference_nodes(net,node)
            ref=frozenset(ref if ref is not None else neighbor_set(net,node))
            positive=next((a,s) for a in (0,1) for s in exp.states_for_degree(len(ref))
                     if original_joint(net,d,exp,node,a,s,ref)>0)
            r=identify(task(exp=name,node=node,a=positive[0],s=positive[1]))
            self.assertEqual((r.status.value,r.verification_status.value),('POINT','VERIFIED'))
            self.assertTrue(replay_population_identification(r))
        no=identify(task(admit_exclusion=False))
        self.assertNotEqual(no.status.value,'POINT')
        self.assertEqual(no.result.get('reason_code'),'D6_FIRST_STAGE_PROFILE_EXCLUSION_NOT_ADMITTED')
        self.assertEqual(no.diagnostics['workflow_status'],'NEEDS_INPUT')
        good=identify(task())
        tampered=replace(good,result=deepcopy(good.result))
        tampered.result['certificate']['joint_arm_support_probability']='999'
        with self.assertRaises(ValueError):replay_population_identification(tampered)
        waiting=identify_network_business_query(ArmInquiryV21(task(admit_exclusion=False)))
        self.assertEqual(waiting.status,'NEEDS_INPUT')
        wrapper=identify_network_business_query(ArmInquiryV21(task()))
        self.assertEqual(wrapper.status,'POINT')
        self.assertTrue(replay_verified_business_outcome(wrapper))

    def test_batch_and_independent_replay(self):
        batch=identify_randomized_network_batch(task(exp='any_treated_neighbor'))
        self.assertEqual(batch.shape,(6,2,2))
        self.assertTrue(any(item=='POINT' for row in batch.arm_status for arm in row for item in arm))
        self.assertTrue(replay_network_arm_batch(batch))
        with self.assertRaises(ValueError):
            replay_network_arm_batch(replace(batch,batch_sha256='0'*64))
        # No direct stage-one outcome effect -> no batch-level POINT.
        invalid=identify(task(admit_exclusion=False))
        self.assertNotEqual(invalid.status.value,'POINT')

    def test_d6_single_profile_reduces_to_d5_count_and_full_q(self):
        net=network(); quotas=(1,0,2)
        d6=design(profiles=(quotas,),probs=('1',))
        d5=MultiGroupFixedQuotaDesignV25(groups=GROUPS,treated_quotas=quotas)
        for bits in product((0,1),repeat=len(NODES)):
            z=dict(zip(NODES,bits))
            self.assertEqual(AssignmentSpec(d6).full_assignment_probability(net,z),
                             AssignmentSpec(d5).full_assignment_probability(net,z))
        for node in NODES:
            refs=frozenset(neighbor_set(net,node))
            for a in (0,1):
                one=AssignmentSpec(d6).conditional_neighbor_count_law(net,node,a,refs)
                two=AssignmentSpec(d5).conditional_neighbor_count_law(net,node,a,refs)
                self.assertEqual(one,two)

    def test_exclusion_contradicted_is_unsupported_not_needs_input(self):
        st=study();tg=fixed_policy_target_from_context(st,(1,0,1,0,1,0),authority='TRUSTED_FIXTURE')
        rejected=assumptions()[:-1]+(Assumption(name=D6_EXCLUSION,
            source='human_confirmation',status='CONTRADICTED',
            evidence=['confirmed stage-one quota announcement can change behavior']),)
        out=identify_network_business_query(FixedPolicyInquiryV21(st,tg,rejected,
                                                         r1b_sources=(population_a4(st),)))
        self.assertEqual(out.status,'UNSUPPORTED')
        self.assertEqual(out.reason_code,'D6_FIRST_STAGE_PROFILE_EXCLUSION_CONTRADICTED')
        self.assertNotEqual(identify(task(admit_exclusion=False)).status.value,'POINT')

    def test_lottery_identity_changes_arm_target_not_fixed_policy_target(self):
        d1=design();d2=design(probs=('1/3','2/3'))
        self.assertNotEqual(task(d=d1).target_fingerprint,task(d=d2).target_fingerprint)
        st1,st2=study(d=d1),study(d=d2)
        tg1=fixed_policy_target_from_context(st1,(1,0,1,0,1,0),authority='TRUSTED_FIXTURE')
        tg2=fixed_policy_target_from_context(st2,(1,0,1,0,1,0),authority='TRUSTED_FIXTURE')
        self.assertEqual(tg1.target_digest,tg2.target_digest)
        self.assertNotEqual(st1.study_digest,st2.study_digest)

    def test_verified_effect_composition_reuses_d6_support(self):
        b=identify_randomized_network_batch(task(exp='any_treated_neighbor'))
        cells=tuple((n,a,s) for n in b.node_ids for a in (0,1) for s in b.exposure_states
                    if b.cell(n,a,s)['status']=='POINT')
        a4=declare_a4_source(b.template,source_id='D6-all-arm-operator',
            operator='NODE_ARM_MEANS',provenance='declared synthetic population operator',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            regime='experimental',outcome_nodes=b.node_ids,node_order=b.node_ids,
            arm_cells=cells)
        node='a'
        allowed=next(s for s in b.exposure_states
                if b.cell(node,0,s)['status']=='POINT' and b.cell(node,1,s)['status']=='POINT')
        res=identify_verified_node_effect(b,a4,node_id=node,kind='DIRECT',
                        reference_exposure=allowed,comparison_exposure=allowed)
        self.assertEqual((res.status,res.verification_status),('POINT','VERIFIED'))
        self.assertTrue(replay_verified_composition(res))
        self.assertEqual(res.term_count,2)
        self.assertIsNone(res.estimation_request)

    def test_r1b_supported_full_assignment_and_denials(self):
        st=study();z=(1,0,1,0,1,0)
        tgt=fixed_policy_target_from_context(st,z,authority='TRUSTED_FIXTURE')
        src=population_a4(st)
        r=identify_verified_fixed_policy(st,tgt,(src,),assumptions=assumptions())
        self.assertEqual(r.assignment_probability,'1/16')
        self.assertTrue(replay_verified_fixed_policy(r))
        out=identify_network_business_query(FixedPolicyInquiryV21(st,tgt,assumptions(),r1b_sources=(src,)))
        self.assertEqual(out.route,'R1B_FULL_ASSIGNMENT')
        self.assertTrue(replay_verified_business_outcome(out))
        for invalid_a5 in (assumptions(False),assumptions(source='llm_candidate',admit_exclusion=False)):
            with self.assertRaises(R1bPolicyUnavailable):
                identify_verified_fixed_policy(st,tgt,(src,),assumptions=invalid_a5)
        unsup=fixed_policy_target_from_context(st,(1,)*6,authority='TRUSTED_FIXTURE')
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(st,unsup,(src,),assumptions=assumptions())
        # Same outcome quantity; changing lottery pi changes original q and the protocol fingerprint.
        st2=study(d=design(probs=('1/3','2/3')))
        tgt2=fixed_policy_target_from_context(st2,z,authority='TRUSTED_FIXTURE')
        self.assertEqual(tgt.target_digest,tgt2.target_digest)
        self.assertNotEqual(st.protocol_digest,st2.protocol_digest)

    def test_r2_off_support_policy_and_scoped_sufficiency(self):
        st=study();tgt=fixed_policy_target_from_context(st,(1,)*6,authority='TRUSTED_FIXTURE')
        sig=declare_policy_signature(st,grouping='any_treated_neighbor')
        enough=admit_mean_signature_sufficiency(st,sig,
            assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
                confirmed=True,evidence=['reviewed restriction in this synthetic experiment']),
            covered_nodes=st.node_order)
        source=declare_signature_population_source(st,sig,source_id='D6-signature-law',
            operator='NODE_FULL_LAW',outcome_nodes=st.node_order,
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            provenance='declared synthetic population operator')
        r=identify_verified_signature_policy(st,tgt,sig,(source,),
              assumptions=assumptions(),sufficiency=enough)
        self.assertEqual(r.policy_assignment_probability,'0')
        self.assertTrue(all(Fraction(p)>0 for p in r.node_class_support))
        self.assertTrue(replay_verified_signature_policy(r))
        diag=diagnose_policy_signature_support_v25(st,tgt,sig)
        self.assertTrue(replay_policy_signature_support_v25(diag,st,tgt,sig))
        self.assertTrue(any('profile[' in s for node in diag.nodes for s in node.by_stratum_constraints))
        with self.assertRaises(R2PolicyUnavailable):
            identify_verified_signature_policy(st,tgt,sig,(source,),
                assumptions=assumptions(False),sufficiency=enough)
        pending=replace(enough,assumption=Assumption(name='mean_signature_sufficiency',
                      source='human_confirmation',confirmed=False,evidence=['not accepted']))
        with self.assertRaises(R2PolicyUnavailable):
            identify_verified_signature_policy(st,tgt,sig,(source,),
                assumptions=assumptions(),sufficiency=pending)
        # Off-support R2 is used by the common business router only with explicit scoped A5.
        case=identify_network_business_query(FixedPolicyInquiryV21(st,tgt,assumptions(),r1b_sources=(population_a4(st),),
            r2_signature=sig,r2_sufficiency=enough,r2_sources=(source,)))
        self.assertEqual(case.route,'R2_MEAN_SIGNATURE')
        self.assertTrue(replay_verified_business_outcome(case))

if __name__=='__main__':
    unittest.main()
