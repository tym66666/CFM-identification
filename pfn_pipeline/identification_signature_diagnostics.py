"""v2.3 exact explanatory A6 diagnostics for D2/E1 policies.

This module does NOT add an identification theorem. It explains why R2's
policy-specific node signature has zero/positive experimental support.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from fractions import Fraction
from math import comb

from ._internal.identification.schemas import CompleteRandomizationDesignV1
from ._internal.identification.randomized_arm_family import AssignmentSpec,ExposureSpec,SupportEngine
from .network_inquiry_shadow import NetworkStudyContextV17
from .identification_route_shadow import TargetSemanticsV15


@dataclass(frozen=True)
class MajorityQuotaNodeDiagnosticV23:
    node_id:str
    degree:int
    policy_own_treatment:int
    policy_signature:int
    minimum_required_treated_neighbors:int
    maximum_feasible_treated_neighbors:int
    signature_probability:str
    reason_code:str


@dataclass(frozen=True)
class MajorityQuotaDiagnosticV23:
    experiment_quota:int
    node_count:int
    target_full_assignment_probability:str
    supported_weighted_nodes:int
    unsupported_weighted_nodes:int
    nodes:tuple[MajorityQuotaNodeDiagnosticV23,...]
    note:str='A6 support diagnostics, NOT a causal POINT theorem or proof that no alternate ID route exists'

    def summary(self):
        return asdict(self)


def diagnose_majority_quota_policy_v23(study:NetworkStudyContextV17,
                                        target:TargetSemanticsV15)->MajorityQuotaDiagnosticV23:
    if not isinstance(study,NetworkStudyContextV17) or not isinstance(target,TargetSemanticsV15):
        raise TypeError('Typed study and target required')
    design=study.design()
    if (study.observation_regime!='experimental' or
        not isinstance(design,CompleteRandomizationDesignV1)):
        raise ValueError('This diagnostic explicitly supports only D2 complete randomization')
    if (target.kind!='FIXED_FULL_ASSIGNMENT_POLICY_MEAN' or
        target.network_fingerprint!=study.network_fingerprint or
        target.node_order!=study.node_order or target.outcome!=study.outcome_variable or
        target.context!=study.context_reference):
        raise ValueError('Policy target and study scope mismatch')
    if study.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED':
        raise ValueError('Pretreatment fixed network required')
    n=len(study.node_order);m=design.m
    network=study.network()
    assignment=AssignmentSpec(design)
    exposure=ExposureSpec('strict_majority_ties_low')
    neigh={u:set() for u in study.node_order}
    for left,right in network.undirected_edges:
        neigh[left].add(right);neigh[right].add(left)
    policy=dict(zip(study.node_order,target.policy_assignment))
    q_full=assignment.full_assignment_probability(network,policy)
    nodes=[]
    for node,w in zip(study.node_order,target.unit_weights):
        if Fraction(w)==0:continue
        a=policy[node];d=len(neigh[node]);k=sum(policy[u] for u in neigh[node])
        s=exposure.classify(k,d)
        minimum_needed=d//2+1 if s==1 else 0
        feasible_max=min(d,m-a) if 0<=m-a<=n-1 else -1
        pi=SupportEngine.evaluate(network=network,assignment=assignment,
            exposure=exposure,node_id=node,own_treatment_value=a,exposure_value=s).joint_probability
        # Independent direct count of full allocations (not DP/support backend).
        numerator=sum(comb(d,r)*comb(n-1-d,m-a-r)
                      for r in range(d+1) if 0<=m-a-r<=n-1-d
                      and exposure.classify(r,d)==s)
        independent=Fraction(numerator,comb(n,m))
        if independent!=pi:
            raise ArithmeticError('Independent D2 majority-support disagreement')
        if pi>0:
            reason='POSITIVE_SIGNATURE_SUPPORT'
        elif m-a<0 or m-a>n-1:
            reason='OWN_TREATMENT_ZERO_SUPPORT'
        elif s==1 and feasible_max<minimum_needed:
            reason='INSUFFICIENT_QUOTA_FOR_MAJORITY_SIGNATURE'
        else:
            reason='SIGNATURE_FORBIDDEN_BY_QUOTA_AND_TOPOLOGY'
        nodes.append(MajorityQuotaNodeDiagnosticV23(node,d,a,s,minimum_needed,feasible_max,str(pi),reason))
    return MajorityQuotaDiagnosticV23(m,n,str(q_full),sum(Fraction(v.signature_probability)>0 for v in nodes),
                    sum(Fraction(v.signature_probability)==0 for v in nodes),tuple(nodes))
