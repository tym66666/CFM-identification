"""v2.2 executable *scope audit*, not a new identification theorem.

32 pre-declared mathematical / business test cards originally described in
CFM_ID_R1_R2_Business_Coverage_Audit_v1_0_ZH.md. Each card records L0 (typed
expression), L1 (candidate route), L2 (verified point / blocked / gap), L3
(estimation adapter, which is NEVER inferred from mathematical identification).

`LIVE_*` evidence is obtained by actually calling and replaying the published
v2.1 verified theorem APIs. `CONTRACT_GAP` is explicitly **not** an executed
backend verdict or a proof of non-identification. Synthetic population source
claims are fixtures and not measured data. The intentionally constructed cards
are not a statistical sample of the real-world business-question distribution.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import copy
from fractions import Fraction
from functools import lru_cache
from itertools import product

from . import (
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21,
    FinitePolicyInquiryV21, identify_network_business_query,
    identify_randomized_network_batch, make_complete_randomization_arm_task,
    make_two_group_quota_arm_task, make_heterogeneous_bernoulli_arm_task,
)
from .identification_composition import EffectQueryV18, ArmLinearTerm, identify_verified_linear_target, CompositionUnavailable
from .identification_a4_shadow import declare_a4_source
from .network_inquiry_shadow import (
    declare_network_study, declare_network_a4_source, fixed_policy_target_from_context,
    assess_nonarm_network_inquiry,
)
from .identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency,
)
from .network_inquiry_shadow import OBSERVATIONAL_CANDIDATE
from ._internal.identification.schemas import Assumption, NetworkExposureSpec
from ._internal.identification.randomized_network_arm import REQUIRED

VERSION = 'network-business-coverage-v2.2'
CARD_TITLES = (
    '本人AI且同事严格多数AI：员工平均结果',
    '固定m人处理、邻居处理比例中档的结果',
    '两组各固定处理名额、核心合作者多数处理',
    'ER300四臂完整批量识别',
    '本人AI设计标准化直接效应',
    '邻居多数AI带来的设计标准化溢出效应',
    '低暴露无AI至高暴露有AI的总效应',
    '预先指定部门平均Direct',
    '核心与非核心员工的平均Direct差',
    '预先指定的基准销售权重加权Direct',
    '把不同随机化设计的两个arm直接命名为同实验Direct',
    '随机化三人网络固定(1,1,0)政策价值',
    '同一个固定政策只有四臂means',
    '从0.5变为0.75的独立随机政策均值',
    '完整固定配额实验中受支持的特定名单',
    '两组各有处理quota的受支持名单',
    '五人固定处理四人、全员处理且无额外结构',
    '同样off-support政策加已接受mean-majority sufficiency',
    '同样off-support政策仅局部干扰',
    '同样off-support政策仅exact neighbor count sufficiency',
    'LLM提出但尚未接受的mean-sufficiency',
    'off-support政策所需节点signature类别零支持',
    '存在孤立节点时E2邻居比例',
    '观测网络自主选择AI的直接效应',
    '网络结构尚未确认',
    '销售结果95%分位数目标',
    '政策结果转移到另一张网络',
    'ER300某具体完整分配且q>0',
    '将majority proxy score冒充固定政策福利',
    '部分节点arm零支持仍求整体平均Direct',
    '局部充分性下的任意随机政策',
    '总体POINT但仅有样本统计无法报告真实数值',
)
assert len(CARD_TITLES) == 32

# Expected classifications are fixed *prior to running the fixtures*, so tests
# can detect a regression rather than silently changing the expected status.
_EXPECT = (
    'POINT','POINT','POINT','POINT_PREVIOUS_ER300','POINT','POINT','POINT',
    'POINT','POINT','POINT','RE_SPECIFY','POINT','NEEDS_INPUT',
    'POINT_FINITE_TOY_ONLY','POINT','POINT','NO_POINT_ROUTE','POINT',
    'NO_POINT_ROUTE','NO_POINT_ROUTE','NEEDS_INPUT','NO_POINT_ROUTE',
    'RE_SPECIFY','ROUTE_GAP','NEEDS_INPUT','ROUTE_GAP','ROUTE_GAP',
    'POINT_WITH_ESTIMATION_GAP','PROXY_ONLY','NO_POINT_ROUTE','ROUTE_GAP',
    'A4_SAMPLE_ONLY_BLOCKED',
)
assert len(_EXPECT)==32

# This is a *capability assessment*, distinct from experimental measurement.
# For example a test fixture can provide a mathematical population operator,
# but it cannot manufacture actual conditional means / an estimator.
@dataclass(frozen=True)
class CoverageVerdictV22:
    case_id: str
    business_question: str
    expected_class: str
    l0_target: str
    l1_route: str
    l2_identification: str
    l3_estimation: str
    observed_route: str | None
    observed_reason: str | None
    evidence_type: str
    evidence_note: str
    target_class: str
    a4_required_information: str
    a5_required_assumptions: str
    a6_support_and_validity: str
    existing_estimation_adapter: str
    synthetic: bool = True

    def as_json(self) -> dict:
        return asdict(self)


def _assumptions():
    return tuple(Assumption(name=n,source='demo_specification',confirmed=True,
                   evidence=['EXPLICIT synthetic population study fixture']) for n in REQUIRED)


def _net3():
    return NetworkExposureSpec(network_id='coverage-v22-toy3',node_ids=['0','1','2'],
                               undirected_edges=[('0','1'),('0','2')])


def _star5():
    return NetworkExposureSpec(network_id='coverage-v22-star5',
                               node_ids=['hub','l1','l2','l3','l4'],
                               undirected_edges=[('hub',f'l{i}') for i in range(1,5)])


def _ring6():
    nodes=[str(i) for i in range(6)]
    return NetworkExposureSpec(network_id='coverage-v22-ring6',node_ids=nodes,
                               undirected_edges=[(nodes[i],nodes[(i+1)%6]) for i in range(6)])


def _task_d1(net=None, *, exposure='strict_majority', node=None, a=0, s=0):
    net=net or _net3()
    return make_heterogeneous_bernoulli_arm_task(net,propensities={n:'1/2' for n in net.node_ids},
        node_id=node or net.node_ids[0],own_treatment_value=a,exposure_value=s,
        source='v2.2 synthetic fixture', evidence='independent Bernoulli and symbolic population law',
        admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE',
        exposure_definition={'strict_majority':'strict_majority', 'three_level':'three_level_treated_neighbor_fraction'}[exposure])


def _task_d2(*, exposure='strict_majority', net=None, node=None, a=0,s=0):
    net=net or _star5()
    return make_complete_randomization_arm_task(net,m=len(net.node_ids)-1,
        node_id=node or net.node_ids[1],own_treatment_value=a,exposure_value=s,
        source='v2.2 synthetic quota protocol',evidence='uniform quota and symbolic population law',
        admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE',
        exposure_definition={'strict_majority':'strict_majority', 'three_level':'three_level_treated_neighbor_fraction'}[exposure])


def _task_d3():
    net=_ring6(); ids=tuple(net.node_ids)
    core={n:(ids[(i+1)%len(ids)],) for i,n in enumerate(ids)}
    return make_two_group_quota_arm_task(net,groups=(ids[:3],ids[3:]),treated_quotas=(2,1),
        node_id='0',own_treatment_value=0,exposure_value=1,
        exposure_definition='pretreatment_core_collaborator_majority',core_collaborators=core,
        source='v2.2 declared pretreatment groups',evidence='uniform within-group quotas',
        admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')


@lru_cache(maxsize=1)
def _arm_bundle():
    task=_task_d1()
    batch=identify_randomized_network_batch(task)
    source=declare_a4_source(task,source_id='v22-explicit-node-full-law',
        operator='NODE_FULL_LAW',provenance='hypothetical symbolic population outcomes',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=batch.node_ids,node_order=batch.node_ids)
    return task,batch,source


def _study(kind='d1'):
    net={'d1':_net3,'d2':_star5,'d3':_ring6}[kind]()
    if kind=='d1':
        design={'kind':'heterogeneous_bernoulli_binary_v1',
                'propensities':{n:'1/2' for n in net.node_ids}}
    elif kind=='d2':
        design={'kind':'complete_randomization_binary_v1','m':4}
    else:
        ids=tuple(net.node_ids)
        design={'kind':'two_group_fixed_quota_binary_v1',
                'groups':(ids[:3],ids[3:]),'treated_quotas':(2,1)}
    return declare_network_study(network_id=net.network_id,
       node_order=tuple(net.node_ids), undirected_edges=tuple(net.undirected_edges),
       treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
       context_reference='W',observation_regime='experimental',assignment_design=design,
       protocol_provenance='HYPOTHETICAL network randomized experiment v2.2',
       network_provenance='fixed synthetic graph fixture',
       graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _full_source(study, *, operator='NODE_FULL_LAW'):
    return declare_network_a4_source(study,source_id='v22-exact-observable-'+operator,
       operator=operator,provenance='declared symbolic POPULATION information (not measured outcomes)',
       admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
       outcome_nodes=study.node_order,
       exposure_fingerprint='unrelated-synthetic-arm-mapping' if operator=='NODE_ARM_MEANS' else None)


def _fixed(kind='d1',z=None, *, operator='NODE_FULL_LAW', suff=False, proposed=False, signature_zero=False):
    study=_study(kind)
    if z is None: z=(1,)*len(study.node_order)
    target=fixed_policy_target_from_context(study,tuple(z),authority='TRUSTED_FIXTURE')
    if not suff and not proposed and not signature_zero:
        return identify_network_business_query(FixedPolicyInquiryV21(study,target,
            _assumptions(),r1b_sources=(_full_source(study,operator=operator),)))
    sig=declare_policy_signature(study,grouping='strict_majority_ties_low')
    net=study.network()
    neighbors={node:[] for node in study.node_order}
    for i,j in net.undirected_edges:
        neighbors[i].append(j);neighbors[j].append(i)
    treatment=dict(zip(study.node_order,z))
    cells=tuple((node,treatment[node],int(sum(treatment[n] for n in neighbors[node])>len(neighbors[node])//2))
                for node in study.node_order)
    source=declare_signature_population_source(study,sig,
        source_id='v22-reviewed-population-signatures',operator='NODE_SIGNATURE_MEANS',
        provenance='explicit hypothetical population signature means',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order,signature_cells=cells)
    state=('PROPOSED' if proposed else 'ADMITTED')
    assumption=Assumption(name='mean_signature_sufficiency',
          source='llm_candidate' if proposed else 'demo_specification',
          confirmed=not proposed,status=state,evidence=['Hypothetical mean-signature sufficiency; not inferred'])
    license=admit_mean_signature_sufficiency(study,sig,assumption=assumption,
                                            covered_nodes=study.node_order)
    return identify_network_business_query(FixedPolicyInquiryV21(study,target,
         _assumptions(),r1b_sources=(_full_source(study),),
         r2_signature=sig,r2_sufficiency=license,r2_sources=(source,)))


def _effect(kind='DIRECT', nodes=None, *, source=None, exposure0=0, exposure1=1):
    _,batch,a4=_arm_bundle()
    selected=tuple(nodes or ('0',))
    req=EffectQueryV18(kind=kind,node_weights=tuple((node,'1') for node in selected),
       reference_exposure=exposure0,comparison_exposure=exposure1,
       cohort_authority='TRUSTED_FIXTURE' if len(selected)>1 else None,
       cohort_evidence='Prespecified staff cohort in synthetic fixture' if len(selected)>1 else None)
    return identify_network_business_query(EffectsInquiryV21(batch,source or a4,(req,)))


def _live(obj, *, note='') -> tuple[str,str|None,str|None,str]:
    if not hasattr(obj,'status'):
        raise TypeError('Live evidence must be a theorem-backed v2.1 result')
    if obj.status=='POINT' and obj.result is not None:
        from .identification_business import replay_verified_business_outcome
        if not replay_verified_business_outcome(obj):
            raise AssertionError('Verification replay did not succeed')
        return 'POINT', obj.route, None, 'LIVE_THEOREM_REPLAY: '+note
    return 'BLOCKED', obj.route, obj.reason_code, 'LIVE_REJECTION: '+note


def _run_case(number: int) -> tuple[str,str|None,str|None,str,str]:
    """L2, route, reason, evidence type, concrete note; *not* a policy value."""
    if number==1:
        x=identify_network_business_query(ArmInquiryV21(_task_d1(a=1,s=1)))
        mode,route,reason,evidence=_live(x,note='R1a synthetic symbol; no numeric outcome')
        return mode,route,reason,evidence,'NODE_ARM_MEANS is a symbolic population operator, not a sample estimate'
    if number==32:
        task=_task_d1()
        # A sample estimate is NOT an admitted population conditional mean.
        raw=copy.deepcopy(task.identification_spec)
        raw['information_signature']['objects'][0]['randomized_arm_observable'][
            'availability']='FINITE_SAMPLE_ESTIMATE'
        observed=identify_network_business_query(ArmInquiryV21(replace(task,identification_spec=raw)))
        if observed.status=='POINT':
            raise AssertionError('FINITE_SAMPLE_ESTIMATE must not authenticate population A4')
        # Distinct admissible A4: hypothetical population information, not data
        # supplied in this card. Used to check the boundary, not to upgrade it.
        symbolic=identify_network_business_query(ArmInquiryV21(task))
        if symbolic.status!='POINT':
            raise AssertionError('Valid hypothetical population operator should be POINT')
        return ('BLOCKED',observed.route,observed.reason_code,
                'LIVE_SAMPLE_A4_REFUSAL_PLUS_SYMBOLIC_COUNTERFACTUAL',
                'Sample-only operator refused; DIFFERENT explicitly declared symbolic population source passes, not a numerical effect')
    if number == 2:
        net=_ring6()
        task=make_complete_randomization_arm_task(net,m=3,node_id='0',own_treatment_value=0,
            exposure_value=1,exposure_definition='three_level_treated_neighbor_fraction',
            source='v22 synthetic',evidence='valid D2 E2 fixture',admitted=True,synthetic=True,
            query_authority='TRUSTED_FIXTURE')
        return (*_live(identify_network_business_query(ArmInquiryV21(task))), 'D2×E2 actually executed')
    if number==3:
        return (*_live(identify_network_business_query(ArmInquiryV21(_task_d3()))), 'D3×E3 actually executed')
    if number == 4:
        _,batch,_=_arm_bundle()
        assert batch.verification_status=='VERIFIED'
        return 'POINT','R1A_BATCH',None,'LIVE_TOY_BATCH_AND_ARCHIVED_ER300',(
            f'Toy batch {batch.shape} independently verified; ER300 1200/1200 is an archived v2.1 release, not recomputed here')
    if number in (5,6,7,8,10):
        kind={5:'DIRECT',6:'SPILLOVER',7:'TOTAL',8:'DIRECT',10:'DIRECT'}[number]
        nodes=('0','1') if number in (8,10) else ('0',)
        if number==10:
            _,batch,source=_arm_bundle()
            req=EffectQueryV18(kind='DIRECT',node_weights=(('0','1/3'),('1','2/3')),
                reference_exposure=0,comparison_exposure=0,
                cohort_authority='TRUSTED_FIXTURE',
                cohort_evidence='prespecified baseline sales weights in synthetic protocol')
            r=identify_network_business_query(EffectsInquiryV21(batch,source,(req,)))
        else:
            r=_effect(kind,nodes=nodes,exposure0=0,exposure1=1 if number in (6,7) else 0)
        return (*_live(r), f'{kind} exact cohort/weights, R1a source batch')
    if number==9:
        _,batch,a4=_arm_bundle()
        # Predeclared hub versus the two leaves: (direct_hub - average(direct_leaf1, direct_leaf2))
        terms=(ArmLinearTerm('0',1,0,'1'),ArmLinearTerm('0',0,0,'-1'),
               ArmLinearTerm('1',1,0,'-1/2'),ArmLinearTerm('1',0,0,'1/2'),
               ArmLinearTerm('2',1,0,'-1/2'),ArmLinearTerm('2',0,0,'1/2'))
        out=identify_verified_linear_target(batch,a4,terms)
        from .identification_composition import replay_verified_composition
        replay_verified_composition(out)
        return 'POINT','R1A_CUSTOM_LINEAR',None,'LIVE_THEOREM_REPLAY', 'Hub versus predeclared leaf group custom linear POINT'
    if number==11:
        return 'RE_SPECIFY',None,'CROSS_DESIGN_ARM_NOT_A_SINGLE_DIRECT_EFFECT','CONTRACT_GAP',(
            'One R1a composition binds exactly one q/g/W; cross-design requires an explicitly new causal target')
    if number==12:
        return (*_live(_fixed('d1',(1,1,0))), '3-node supported full policy')
    if number==13:
        return (*_live(_fixed('d1',(1,1,0),operator='NODE_ARM_MEANS')), 'Arm-only A4 not full assignment')
    if number==14:
        # Literal 3-node independent Bernoulli(3/4) target policy kernel, expanded into all 2^3 atoms.
        study=_study('d1')
        source=_full_source(study)
        points=[];weights=[]
        for z in product((0,1),repeat=3):
            target=fixed_policy_target_from_context(study,tuple(z),authority='TRUSTED_FIXTURE')
            query=identify_network_business_query(FixedPolicyInquiryV21(
                  study,target,_assumptions(),r1b_sources=(source,)))
            assert query.status=='POINT'
            points.append(query.result)
            k=sum(z);weights.append(str(Fraction(3,4)**k*Fraction(1,4)**(3-k)))
        mixed=identify_network_business_query(FinitePolicyInquiryV21(tuple(points),tuple(weights)))
        return (*_live(mixed), '3-node finite 8-atom expansion ONLY; general N-node kernel remains unimplemented')
    if number==15:
        return (*_live(_fixed('d2',(0,1,1,1,1))), 'D2 legal m=4 assignment')
    if number==16:
        return (*_live(_fixed('d3',(1,1,0,1,0,0))), 'D3 group quotas (2,1)')
    if number in (17,19,20):
        blocked=_fixed('d2',(1,)*5)
        assert blocked.status!='POINT'
        if number==17:
            return (*_live(blocked), 'R1b off support; no A5 sufficiency')
        return 'ROUTE_GAP',None,'NO_EXACT_LOCAL_OR_COUNT_SIGNATURE_BACKEND','LIVE_R1B_REFUSAL_PLUS_CONTRACT_GAP',(
            f'Observed R1b={blocked.reason_code}; merely {"local" if number==19 else "exact count"} sufficiency does not yield the E1 majority route; required local/count class has no support in this star fixture')
    if number==18:
        return (*_live(_fixed('d2',(1,)*5,suff=True)), 'Majority R2, q(all treated)=0')
    if number==21:
        out=_fixed('d2',(1,)*5,proposed=True)
        if out.status=='POINT': raise AssertionError('Unaccepted R2 assumption must not pass')
        return ('NEEDS_INPUT',out.route,out.reason_code,'LIVE_REJECTION',
                'R2 proposed A5 must not be admitted')
    if number==22:
        return (*_live(_fixed('d2',(0,)*5,signature_zero=True)), 'R2 own-zero and exposure-low class has no support for leaves')
    if number==23:
        isolate=NetworkExposureSpec(network_id='coverage-isolate',node_ids=['0','1','2'],undirected_edges=[('0','1')])
        try:
            task=_task_d1(isolate,exposure='three_level',node='2',a=0,s=0)
            obj=identify_network_business_query(ArmInquiryV21(task))
        except (ValueError,TypeError) as exc:
            return 'RE_SPECIFY',None,'E2_UNDEFINED_FOR_ISOLATE','LIVE_INPUT_VALIDATION',repr(exc)
        if obj.status=='POINT':
            raise AssertionError('E2 isolated node must not be promoted to POINT')
        return 'RE_SPECIFY',obj.route,obj.reason_code,'LIVE_THEOREM_REJECTION','E2 isolated node invalid'
    if number==24:
        study=declare_network_study(network_id='coverage-v22-observational',
            node_order=('0','1','2'),undirected_edges=(('0','1'),('0','2')),
            treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
            context_reference='W',observation_regime='observational',
            assignment_design=None,protocol_provenance='self-selected use of AI',
            network_provenance='fixed hypothetical graph',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
        target=fixed_policy_target_from_context(study,(1,1,1),authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(study,source_id='observational-source',
            operator='NODE_FULL_LAW',provenance='hypothetical observational population',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=study.node_order)
        out=assess_nonarm_network_inquiry(study,target,(src,),family_id=OBSERVATIONAL_CANDIDATE,assumptions=())
        assert out.route_status=='THEOREM_BACKEND_UNAVAILABLE'
        return ('ROUTE_GAP',None,'NO_GENERAL_OBSERVATIONAL_NETWORK_POINT',
                'LIVE_OBSERVATIONAL_PRECHECK_ONLY','Observational non-arm fixed-policy classified; B24 direct-effect R3 is not executable')
    if number==25:
        return 'NEEDS_INPUT',None,'NETWORK_STRUCTURE_UNRESOLVED','CONTRACT_GAP',(
            'Known graph is an essential input; no automatic graph discovery / uncertain-graph ID theorem')
    if number==26:
        return 'ROUTE_GAP',None,'QUANTILE_TARGET_NOT_REGISTERED','CONTRACT_GAP',(
            'Existing theorem output is conditional mean, not a quantile of policy outcomes')
    if number==27:
        return 'ROUTE_GAP',None,'NETWORK_TRANSPORT_NOT_REGISTERED','CONTRACT_GAP',(
            'Target changes network/scientific population, requiring additional assumptions')
    if number==28:
        return (*_live(_fixed('d1',(1,)*3)),
                'Exact assignment q=1/8 for 3 nodes; ER300 2^-300 reviewed in archived v2.1')
    if number==29:
        return 'PROXY_ONLY',None,'PROXY_SCORE_NOT_TRUE_POLICY_VALUE','CONTRACT_GAP',(
            'Legacy majority_score aggregates design arms, not deterministic rollout welfare')
    if number==30:
        task=_task_d2(node='l1',a=0,s=1)
        batch=identify_randomized_network_batch(task)
        src=declare_a4_source(task,source_id='v22-quota-full-law',
            operator='NODE_FULL_LAW',provenance='hypothetical D2 population operator',
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=batch.node_ids,node_order=batch.node_ids)
        assert batch.cell('hub',1,0)['status']!='POINT'
        try:
            req=EffectQueryV18(kind='DIRECT',node_weights=(('hub','1'),),
                  reference_exposure=0,comparison_exposure=0)
            out=identify_network_business_query(EffectsInquiryV21(batch,src,(req,)))
        except (ValueError,TypeError,CompositionUnavailable) as exc:
            return ('BLOCKED',None,getattr(exc,'reason_code','ZERO_ARM_SUPPORT'),
                    'LIVE_THEOREM_REJECTION',repr(exc))
        if out.status=='POINT':
            raise AssertionError('Zero-support hub arm incorrectly combined')
        return (*_live(out), 'Zero support for hub own-treatment 1, low exposure under D2')
    if number==31:
        return 'ROUTE_GAP',None,'R2_STOCHASTIC_POLICY_KERNEL_UNIMPLEMENTED','CONTRACT_GAP',(
            'R2 verifies fixed policies; R1b finite mixer accepts only R1b verified components')
    raise AssertionError(f'No v2.2 coverage runner for B{number:02d}')


# Every card is traced back to its original B-number. A4/A5/A6 fields below
# are theorem REQUIREMENTS, not claims these conditions have been met in real
# experimental data. The live fixture audit tracks condition fulfillment.
def _scientific_contract(number: int) -> tuple[str,str,str,str,str]:
    if number in (1,2,3,4):
        return ('DESIGN_STANDARDIZED_NODE_ARM',
                'Admitted conditional node-arm population means or an entailing node/full joint population law',
                'Known q, full-vector randomization, consistency, fixed pre-treatment graph, finite first moments',
                'q(T_i=a, g_i(T)=s)>0; graph/exposure well defined for requested node',
                'LEGACY_PFN_BRIDGE_ONLY_D1_E1_SHARED_4_ARM' if number==4 else 'NO_MATCHING_ESTIMATOR_TESTED')
    if number in (5,6,7,8,9,10,30):
        return ('DESIGN_STANDARDIZED_ARM_LINEAR_CONTRAST_OR_AGGREGATE',
                'Admitted arm mean population operator for EVERY nonzero coefficient node-arm, all in same study',
                'All source arms satisfy R1a randomization; prespecified cohort and weights',
                'Every nonzero arm has positive support; identical q/g/W and same source study',
                'NO_MATCHING_ESTIMATOR_TESTED')
    if number==11:
        return ('AMBIGUOUS_CROSS_DESIGN_COMPARISON',
                'Both study-specific population arm laws would be needed after query is formally restated',
                'One coherent target q/g/W or explicitly defined transport/cross-design estimand',
                'Different q must not be combined as one R1a direct effect by default',
                'NOT_APPLICABLE')
    if number in (12,13,14,15,16,17,28):
        return ('FULL_ASSIGNMENT_FIXED_OR_FINITE_STOCHASTIC_POLICY_VALUE',
                'Admitted assignment-resolution conditional node outcome law or complete joint population law',
                'Known randomization q, consistency, fixed pre-treatment network, integrability',
                'q(z)>0 for EACH fixed policy atom; B14 is only explicitly enumerated 3-node finite kernel',
                'NO_POLICY_VALUE_ESTIMATOR_TESTED')
    if number in (18,19,20,21,22):
        return ('OFF_SUPPORT_SIGNATURE_SUFFICIENT_FIXED_POLICY_VALUE',
                'Admitted conditional node SIGNATURE-class population means for the required policy cells',
                'Known randomization and separately reviewed/accepted mean-signature sufficiency for chosen mapping',
                'Each policy-required node signature has q-positive class support; no extra assumptions inferred',
                'NO_POLICY_VALUE_ESTIMATOR_TESTED')
    if number==23:
        return ('EXPOSURE_TARGET_WITH_ISOLATED_NODE',
                'Neighbor fraction exposure definition needs a documented convention for degree zero',
                'Fixed known graph and a well-defined scientific target',
                'E2 fraction is undefined at degree zero under current formal domain',
                'NOT_APPLICABLE')
    if number==24:
        return ('OBSERVATIONAL_NETWORK_DIRECT_EFFECT',
                'Joint observational law over own/neighbor treatment, outcomes, measured confounders and graph',
                'Network conditional exchangeability, consistency, exposure sufficiency where required',
                'Conditional/joint positivity; a formally registered R3 theorem is currently absent',
                'NO_GENERAL_R3_ADAPTER')
    if number==25:
        return ('NETWORK_GRAPH_UNRESOLVED',
                'Validated pre-treatment network identity, node order and edges',
                'Accepted network structure and assignment provenance',
                'Graph cannot be supplied or deduced as a known fixed network',
                'NOT_APPLICABLE')
    if number==26:
        return ('QUANTILE_TARGET_UNREGISTERED',
                'Outcome conditional distribution, not just conditional means',
                'Potential-outcome distributional assumptions and valid source operator',
                'No registered quantile identification backend',
                'NOT_APPLICABLE')
    if number==27:
        return ('CROSS_NETWORK_TRANSPORT_VALUE',
                'Source and target network contexts and a population transport operator',
                'Explicit inter-network transportability/invariance assumptions',
                'Target graph/population differs from original experimental scope',
                'NOT_APPLICABLE')
    if number==29:
        return ('POLICY_PROXY_NOT_TARGET_WELFARE',
                'Proxy arm means are not the complete policy node-mean law',
                'Need valid policy-specific assignment or signature-sufficiency theorem',
                'Do not interpret majority_score as V(z)',
                'NO_POLICY_VALUE_ESTIMATOR_TESTED')
    if number==31:
        return ('SIGNATURE_SUFFICIENT_STOCHASTIC_POLICY_KERNEL',
                'All target policy-signature means and policy kernel required',
                'Accepted mean-signature sufficiency and randomized baseline',
                'Policy-induced signature probabilities must be computed; general R2 kernel unimplemented',
                'NO_STOCHASTIC_R2_ADAPTER')
    if number==32:
        return ('DESIGN_STANDARDIZED_ARM_VS_SAMPLE_ESTIMATE',
                'A4 currently offers a FINITE_SAMPLE_ESTIMATE, NOT an admitted population conditional operator',
                'Known randomized q and standard R1a assumptions only permit abstract POINT given population information',
                'Population identification theorem remains valid, but typed A4 gate must refuse sample-only proof',
                'NO_NUMERIC_EFFECT_CERTIFIED_FROM_SAMPLE_ONLY')
    raise AssertionError(f'Unexpected card B{number:02d}')


def _interpret(number:int, event) -> CoverageVerdictV22:
    mode,route,reason,evidence,note=event
    expected=_EXPECT[number-1]
    # Category and 'capability' remain separate: positive supported targets can
    # still lack an actual Estimation adapter / numerical effect value.
    formal_l0 = {11:'RE_SPECIFY',23:'RE_SPECIFY',25:'NEEDS_NETWORK',26:'FORMAL_ONLY',
                 27:'FORMAL_ONLY',29:'PROXY_NOT_POLICY',31:'FORMAL_ONLY'}
    l0=formal_l0.get(number,'TYPED_EXECUTABLE' if not evidence.startswith('CONTRACT_GAP') else 'FORMAL_ONLY')
    l1=route or ('NOT_REGISTERED' if mode in ('ROUTE_GAP','PROXY_ONLY','RE_SPECIFY') else 'BLOCKED_PRECONDITION')
    l2={
      'POINT':'POINT_VERIFIED', 'BLOCKED':'NOT_CERTIFIED',
      'RE_SPECIFY':'RE_SPECIFY', 'NEEDS_INPUT':'NEEDS_INPUT',
      'ROUTE_GAP':'NO_REGISTERED_THEOREM', 'PROXY_ONLY':'PROXY_NOT_POLICY',
    }[mode]
    if number==4: l2='POINT_TOY_LIVE_ER300_PREVIOUS_RELEASE'
    # All this fixture's successful targets are symbolic, never numerical.
    l3='NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT' if l2.startswith('POINT') else 'NOT_APPLICABLE_NO_POINT'
    target,a4,a5,a6,adapter=_scientific_contract(number)
    return CoverageVerdictV22(f'B{number:02d}',CARD_TITLES[number-1],expected,
        l0,l1,l2,l3,route,reason,evidence,note,target,a4,a5,a6,adapter)


def run_business_coverage_v22() -> dict:
    """Actual small-graph proof runs plus explicit unimplemented-route records.

    The output must NOT be reported as market coverage. For cards marked as
    `CONTRACT_GAP`, no model's POINT or non-ID result has been produced.
    """
    rows=[]
    for number in range(1,33):
        rows.append(_interpret(number,_run_case(number)))
    if len({row.case_id for row in rows})!=32:
        raise AssertionError('All 32 independent test-card IDs required')
    counts={}
    for row in rows: counts[row.l2_identification]=counts.get(row.l2_identification,0)+1
    return {'version':VERSION,'case_count':len(rows), 'counts':counts,
            'point_no_numeric_estimate':all('POINT' not in r.l2_identification or
                   r.l3_estimation=='NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT' for r in rows),
            'warning':('This is a deliberately selected synthetic adversarial test suite, NOT a market '
                        'coverage survey. Operator availability is explicitly hypothetical. '
                        'Archived ER300 proof is NOT rerun here. CONTRACT_GAP is no mathematical non-ID proof.'),
            'cards':[r.as_json() for r in rows]}
