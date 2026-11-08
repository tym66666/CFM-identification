"""R2 independent theorem / failure / replay tests: no simulator truth in ID."""
from __future__ import annotations
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import product

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec
from pfn_pipeline.identification_policy_r2 import (
    R2PolicyUnavailable, SignatureSpecV20, MeanSignatureSufficiencyV20,
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source, identify_verified_signature_policy,
    replay_verified_signature_policy,
)
from pfn_pipeline.identification_policy_r1b import identify_verified_fixed_policy, R1bPolicyUnavailable
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, declare_network_a4_source, fixed_policy_target_from_context,
)

NODES=('a','b','c','d')
EDGES=tuple((NODES[i],NODES[j]) for i in range(4) for j in range(i+1,4))
NAMES=('known_assignment_law','full_vector_randomization','consistency',
       'fixed_pretreatment_network','finite_conditional_first_moments')


def study(design='D1',*, nodes=NODES, edges=EDGES, context='W:test', graph='DECLARED_PRETREATMENT_FIXED'):
    ds={
       'D1':{'kind':'heterogeneous_bernoulli_binary_v1',
             'propensities':{n: p for n,p in zip(nodes, ('1/3','1/2','3/4','2/5','2/3')[:len(nodes)])}},
       'D2':{'kind':'complete_randomization_binary_v1','m':3 if len(nodes)==4 else 4},
       'D3':{'kind':'two_group_fixed_quota_binary_v1',
             'groups':[list(nodes[:2]),list(nodes[2:])],
             'treated_quotas':[1,1]},
    }
    return declare_network_study(network_id='r2-test',node_order=nodes,undirected_edges=edges,
         treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
         context_reference=context,observation_regime='experimental',
         assignment_design=ds[design],protocol_provenance='reviewed synthetic design',
         network_provenance='reviewed fixed network',graph_timing_claim=graph)


def base_assumptions(*, omit=(), propose=(), rejected=()):
    return tuple(Assumption(name=n,source='demo_specification',confirmed=n not in propose and n not in rejected,
                            status=('NOT_ADMITTED' if n in rejected else None),
                            evidence=['reviewed DGP protocol']) for n in NAMES if n not in omit)


def mean_claim(st,sig,*, nodes=None, status='ADMITTED'):
    return admit_mean_signature_sufficiency(st,sig,
        assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
             status=status,confirmed=status in ('ADMITTED','CERTIFIED'),
             evidence=['domain expert explicitly reviewed all-assignment mean-response restriction']),
        covered_nodes=nodes or st.node_order)


def signature(st,g='strict_majority_ties_low'):
    if g=='pretreatment_core_collaborator_majority':
        cc={n:(next(x for x in st.node_order if x!=n and (n,x) in st.undirected_edges
                        or (x,n) in st.undirected_edges),) for n in st.node_order}
        return declare_policy_signature(st,grouping=g,core_collaborators=cc)
    return declare_policy_signature(st,grouping=g)


def a4(st,sig,*,op='NODE_SIGNATURE_MEANS',cells=None,nodes=None,
       admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR'):
    if cells is None:
        cells=tuple((n,a,s) for n in st.node_order for a in (0,1)
                    for s in ((0,1,2) if sig.grouping=='three_level_treated_neighbor_fraction' else (0,1)))
    return declare_signature_population_source(st,sig,source_id='A4 reviewed',
        operator=op,outcome_nodes=nodes or st.node_order,signature_cells=cells if op=='NODE_SIGNATURE_MEANS' else (),
        admission=admission,availability=availability,provenance='independently reviewed symbolic population object')


def get(st=None,z=None,g='strict_majority_ties_low',op='NODE_SIGNATURE_MEANS',
        *,assumptions=None,claim=None,source=None,weights=None):
    st=st or study()
    sig=signature(st,g)
    z=z if z is not None else (1,)*len(st.node_order)
    target=fixed_policy_target_from_context(st,tuple(z),authority='TRUSTED_FIXTURE',
              unit_weights=weights)
    su=claim or mean_claim(st,sig)
    src=source or a4(st,sig,op=op)
    return identify_verified_signature_policy(st,target,sig,(src,),
        assumptions=assumptions if assumptions is not None else base_assumptions(),sufficiency=su)


def independent_oracle(st,sig,z):
    """Exact direct enumeration of q plus a structural h_i(a,s)."""
    net=st.network(); qlaw=AssignmentSpec(st.design())
    grp=ExposureSpec(sig.grouping,dict(sig.core_collaborators) if sig.core_collaborators else None)
    obs={}; den={}; num={}
    for n in st.node_order:
        for a in (0,1):
            for s in grp.states:
                den[(n,a,s)]=Fraction(0);num[(n,a,s)]=Fraction(0)
    def sigval(n,alloc):
        ref=grp.reference_nodes(net,n)
        neighbors=ref if ref is not None else {other for e in net.undirected_edges for other in e if n in e and other!=n}
        return grp.classify(sum(alloc[other] for other in neighbors),len(neighbors))
    h=lambda n,a,s: Fraction(3*(st.node_order.index(n)+1)+2*a+5*s,17)
    for vals in product((0,1), repeat=len(st.node_order)):
        alloc=dict(zip(st.node_order,vals))
        q=qlaw.full_assignment_probability(net,alloc)
        if not q: continue
        for n in st.node_order:
            k=(n,alloc[n],sigval(n,alloc))
            den[k]+=q
            num[k]+=q*h(*k)
    for k in den:
        if den[k]: obs[k]=num[k]/den[k]
    oracle=sum(Fraction(1,len(st.node_order))*h(n,z[j],sigval(n,dict(zip(st.node_order,z))))
               for j,n in enumerate(st.node_order))
    return oracle,obs,den


class R2TheoremAndAudits(unittest.TestCase):
    def test_d1_d2_d3_by_e1_e2_e3_and_independent_oracle(self):
        for d in ('D1','D2','D3'):
            for g in ('strict_majority_ties_low','three_level_treated_neighbor_fraction',
                      'pretreatment_core_collaborator_majority'):
                with self.subTest(d=d,g=g):
                    st=study(d);z=(1,0,1,0) if d=='D3' else (1,1,1,1)
                    r=get(st,z,g)
                    self.assertEqual((r.status,r.verification_status),('POINT','VERIFIED'))
                    self.assertTrue(replay_verified_signature_policy(r))
                    oracle,obs,den=independent_oracle(st,r.signature,z)
                    computed=sum(Fraction(w)*obs[cell] for cell,w in zip(r.policy_node_classes,r.node_weights))
                    self.assertEqual(computed,oracle)
                    self.assertEqual([Fraction(s) for s in r.node_class_support],
                                     [den[cell] for cell in r.policy_node_classes])
                    self.assertIsNone(r.estimation_request)

    def test_star_off_support_majority_succeeds(self):
        nd=('hub','l1','l2','l3','l4');edges=tuple(('hub',n) for n in nd[1:])
        st=study('D2',nodes=nd,edges=edges);r=get(st,(1,)*5)
        self.assertEqual(r.policy_assignment_probability,'0')
        self.assertEqual(r.node_class_support[0],'4/5')
        self.assertEqual(r.node_class_support[1:],('3/5',)*4)
        self.assertTrue(replay_verified_signature_policy(r))
        oracle,obs,_=independent_oracle(st,r.signature,(1,)*5)
        self.assertEqual(sum(Fraction(w)*obs[c] for c,w in zip(r.policy_node_classes,r.node_weights)),oracle)
        # R1b must not certify this off-support policy, despite full assignment-level A4.
        target=fixed_policy_target_from_context(st,(1,)*5,authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(st,source_id='full',operator='NODE_FULL_LAW',
            provenance='synthetic full law',admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=st.node_order)
        with self.assertRaises(R1bPolicyUnavailable):
            identify_verified_fixed_policy(st,target,(src,),assumptions=base_assumptions())

    def test_center_exact_count_and_local_not_pretended_sufficient(self):
        nd=('hub','l1','l2','l3','l4');edges=tuple(('hub',n) for n in nd[1:])
        st=study('D2',nodes=nd,edges=edges)
        # Three-level exposure is coarser than exact treated neighbor count.
        self.assertEqual(get(st,(1,)*5,'three_level_treated_neighbor_fraction').policy_assignment_probability,'0')
        # Unaccepted mean sufficiency must be explicitly rejected.
        sig=signature(st)
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,(1,)*5,claim=mean_claim(st,sig,status='PROPOSED'))
        self.assertEqual(err.exception.reason_code,'NEEDS_INPUT')

    def test_critical_zero_signature_class_support(self):
        st=study('D2');z=(1,1,1,1)
        # Four node complete graph D2 quota3: E1 high arm 1,1 is supported;
        # no problem. Instead fixed quota 0 makes all treated locally impossible.
        st=declare_network_study(network_id='zero',node_order=NODES,undirected_edges=EDGES,
             treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
             context_reference='W:test',observation_regime='experimental',
             assignment_design={'kind':'complete_randomization_binary_v1','m':0},
             protocol_provenance='design',network_provenance='network',
             graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,z)
        self.assertEqual(err.exception.reason_code,'ZERO_POLICY_SIGNATURE_SUPPORT')

    def test_no_exposure_sufficiency_by_default(self):
        st=study();sig=signature(st);z=(1,)*4
        tg=fixed_policy_target_from_context(st,z,authority='TRUSTED_FIXTURE')
        with self.assertRaises(R2PolicyUnavailable) as err:
            identify_verified_signature_policy(st,tg,sig,(a4(st,sig),),
                 assumptions=base_assumptions(),sufficiency=mean_claim(st,sig,status='UNRESOLVED'))
        self.assertEqual(err.exception.reason_code,'NEEDS_INPUT')

    def test_assumptions_missing_and_denied(self):
        for aa,code in ((base_assumptions(omit=('full_vector_randomization',)),'NEEDS_INPUT'),
                        (base_assumptions(rejected=('consistency',)),'ASSUMPTIONS_NOT_ADMITTED')):
            with self.subTest(code=code):
                with self.assertRaises(R2PolicyUnavailable) as err: get(assumptions=aa)
                self.assertEqual(err.exception.reason_code,code)

    def test_only_complete_reviewed_a4_operator_entails_policy(self):
        st=study();sig=signature(st)
        r=get(st,g=sig.grouping)
        for op in ('NODE_FULL_LAW','FULL_JOINT_LAW'):
            with self.subTest(op=op):
                self.assertTrue(replay_verified_signature_policy(get(st,op=op)))
        source=a4(st,sig,cells=(('a',1,1),))
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,source=source)
        self.assertEqual(err.exception.reason_code,'A4_SIGNATURE_INFORMATION_INSUFFICIENT')
        src=replace(a4(st,sig),signature_fingerprint='not-that-g')
        with self.assertRaises(R2PolicyUnavailable):get(st,source=src)
        for kw in (dict(admission='PROPOSED'),dict(availability='FINITE_SAMPLE_ESTIMATE')):
            with self.subTest(kw=kw):
                with self.assertRaises(R2PolicyUnavailable): get(st,source=a4(st,sig,**kw))

    def test_no_cross_study_source_or_sufficiency(self):
        st=study();sig=signature(st);new=study('D2')
        with self.assertRaises(R2PolicyUnavailable):get(new,source=a4(st,sig))
        # Structural mean-sufficiency is a scientific scope claim: it is independent
        # of q, so the same reviewed claim MAY transfer across designs.
        cross_sig=signature(new)
        self.assertEqual(cross_sig.signature_fingerprint,sig.signature_fingerprint)
        self.assertTrue(get(new,claim=mean_claim(st,sig)).verification_status=='VERIFIED')
        different_scope=study(context='W:changed')
        with self.assertRaises(R2PolicyUnavailable):get(different_scope,claim=mean_claim(st,sig))

    def test_sufficiency_must_not_be_derived_from_design(self):
        st=study();sig=signature(st)
        bad=Assumption(name='mean_signature_sufficiency',source='deterministic_derivation',
                       status='DERIVED',confirmed=True,evidence=['exposure computed'])
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,claim=admit_mean_signature_sufficiency(st,sig,assumption=bad,
                                                         covered_nodes=st.node_order))
        self.assertEqual(err.exception.reason_code,'NEEDS_INPUT')
        empty=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
                         status='ADMITTED',confirmed=True,evidence=[])
        with self.assertRaises(R2PolicyUnavailable):
            get(st,claim=admit_mean_signature_sufficiency(st,sig,assumption=empty,
                                                         covered_nodes=st.node_order))
        double=base_assumptions()+(mean_claim(st,sig).assumption,)
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,assumptions=double)
        self.assertEqual(err.exception.reason_code,'SUFFICIENCY_MUST_USE_SCOPED_A5_CLAIM')

    def test_target_scientific_identity_matches_r1b(self):
        st=study('D1');r=get(st)
        t=fixed_policy_target_from_context(st,(1,)*4,authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(st,source_id='verified full',operator='NODE_FULL_LAW',
            provenance='full law operator',admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=st.node_order)
        fixed=identify_verified_fixed_policy(st,t,(src,),assumptions=base_assumptions())
        self.assertEqual(r.target_fingerprint,fixed.target_fingerprint)
        self.assertNotEqual(r.certificate_sha256,fixed.certificate_sha256)
        self.assertEqual(r.target.target_digest,fixed.target.target_digest)

    def test_source_and_certificate_tampering_even_forged_digest(self):
        r=get()
        for item in (replace(r,identified_functional='0'),
                     replace(r,node_class_support=('1',)+r.node_class_support[1:]),
                     replace(r,a4_selected_digest='bad'),
                     replace(r,certificate_sha256='x'*64),
                     replace(r,sufficiency=replace(r.sufficiency,covered_nodes=('a',)))):
            with self.subTest(item=item.certificate_sha256[:6]):
                with self.assertRaises(R2PolicyUnavailable):replay_verified_signature_policy(item)
        forged=replace(r,identified_functional='1',certificate_sha256='0'*64)
        from pfn_pipeline.identification_a4_shadow import _sha
        from pfn_pipeline.identification_policy_r2 import _payload
        forged=replace(forged,certificate_sha256=_sha(_payload(forged)))
        with self.assertRaises(R2PolicyUnavailable) as err: replay_verified_signature_policy(forged)
        self.assertEqual(err.exception.reason_code,'R2_CERTIFICATE_REPLAY_MISMATCH')

    def test_policy_zero_weight_exempt_from_support(self):
        st=study('D3');sig=signature(st)
        # all-treated has incompatible own-treatment quota for a few nodes, but
        # a zero-weight node must not be part of the theorem's requirements.
        z=(1,0,1,0)
        r=get(st,z,weights=('1','0','0','0'))
        self.assertEqual(len(r.policy_node_classes),1)

    def test_e2_isolate_not_silent(self):
        st=study('D1',edges=(('a','b'),('b','c')))
        with self.assertRaises(R2PolicyUnavailable) as err:
            get(st,g='three_level_treated_neighbor_fraction')
        self.assertEqual(err.exception.reason_code,'UNDEFINED_EXPOSURE_FOR_POLICY_NODE')

    def test_e3_invalid_core_rejected(self):
        st=study()
        with self.assertRaises(ValueError):
            declare_policy_signature(st,grouping='pretreatment_core_collaborator_majority',
                                     core_collaborators={n:('fake',) for n in st.node_order})

    def test_study_and_treatment_mismatch(self):
        r=get();alt=study(context='W:other')
        with self.assertRaises(R2PolicyUnavailable):
            identify_verified_signature_policy(alt,r.target,r.signature,r.sources,
                assumptions=r.assumptions,sufficiency=r.sufficiency)

    def test_signature_receipt_identity_canonical(self):
        st=study();sig=signature(st)
        self.assertEqual(sig.signature_fingerprint,signature(st).signature_fingerprint)
        with self.assertRaises(ValueError):replace(sig,signature_fingerprint='bad')

    def test_return_is_symbolic_not_outcome_numeric(self):
        r=get()
        self.assertNotIn('estimated_value',r.summary())
        self.assertIn('E[Y_',r.identified_functional)
        self.assertIsNone(r.estimation_request)

    def test_offsupport_not_partial(self):
        st=study('D2');r=get(st,(1,)*4)
        self.assertEqual(r.status,'POINT')
        self.assertEqual(r.policy_assignment_probability,'0')
        # Status is about target with extra A5, not R1b q-full support.


if __name__=='__main__': unittest.main()
