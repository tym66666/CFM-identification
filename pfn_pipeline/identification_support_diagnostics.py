"""v2.5 generic exact A6 support explanations for D1..D5 and E1..E5.

A support diagnosis is NOT an Identification theorem, an assumption license,
non-identification proof, estimator, or an alteration to the original design.
Never derive or admit mean-signature sufficiency from a positive probability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
from math import comb
import hashlib
import json

from ._internal.identification.schemas import (
    CompleteRandomizationDesignV1, TwoGroupFixedQuotaDesignV1,
    HeterogeneousBernoulliDesignV1, ClusterBernoulliDesignV24,
    MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from ._internal.identification.randomized_arm_family.two_stage_verifier import independent_joint_support as _verify_d6_joint_support
from ._internal.identification.randomized_arm_family.assignment import neighbor_set
from ._internal.identification.randomized_network_arm import (
    _verify_joint_support_independently, _verify_two_group_joint_support_independently,
    _verify_multi_group_joint_support_independently, _verify_heterogeneous_joint_support_independently,
    _verifier_matches_exposure,
)
from ._internal.identification.randomized_arm_family.cluster_verifier import verify_cluster_joint_support
from .network_inquiry_shadow import NetworkStudyContextV17
from .identification_route_shadow import TargetSemanticsV15
from .identification_policy_r2 import SignatureSpecV20

VERSION = 'a6-network-signature-support-diagnostic-v2.5'


def _digest(data):
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class SignatureNodeSupportV25:
    node_id: str
    reference_neighbor_count: int
    policy_own_treatment: int
    policy_treated_reference_neighbors: int
    policy_signature: int | None
    own_treatment_probability: str
    feasible_reference_neighbor_counts: tuple[int,...]
    feasible_signature_values: tuple[int,...]
    signature_probability: str
    status: str
    reason_code: str
    detail: str
    by_stratum_constraints: tuple[str,...] = ()


@dataclass(frozen=True)
class PolicySignatureSupportDiagnosticV25:
    version: str
    study_digest: str
    target_fingerprint: str
    signature_fingerprint: str
    design_kind: str
    grouping: str
    full_assignment_probability: str
    supported_weighted_nodes: int
    unsupported_weighted_nodes: int
    nodes: tuple[SignatureNodeSupportV25,...]
    # D2 only; these require a NEW experimental design and new data.
    counterfactual_d2_quotas_with_full_support: tuple[int,...] | None
    disclaimer: str
    evidence_digest: str

    def summary(self):
        return asdict(self)


def _crosscheck(net,design,grouping,node,a,s,refs):
    if isinstance(design,CompleteRandomizationDesignV1):
        return _verify_joint_support_independently(len(net.node_ids),design.m,len(refs),a,s,grouping)
    if isinstance(design,TwoGroupFixedQuotaDesignV1):
        return _verify_two_group_joint_support_independently(net,design,node,a,s,grouping,reference_nodes=frozenset(refs))
    if isinstance(design,TwoStageQuotaMixtureDesignV27):
        return _verify_d6_joint_support(net,design,node,a,s,grouping,
            _verifier_matches_exposure,reference_nodes=frozenset(refs))
    if isinstance(design,MultiGroupFixedQuotaDesignV25):
        return _verify_multi_group_joint_support_independently(net,design,node,a,s,grouping,reference_nodes=frozenset(refs))
    if isinstance(design,ClusterBernoulliDesignV24):
        return verify_cluster_joint_support(net,design,node,a,s,grouping,_verifier_matches_exposure,reference_nodes=frozenset(refs))
    if isinstance(design,HeterogeneousBernoulliDesignV1):
        return _verify_heterogeneous_joint_support_independently(net,design,node,a,s,grouping,reference_nodes=frozenset(refs))
    raise ValueError('Unsupported experimental design for A6 support diagnostic')


def _stratum_constraints(design,node,refs,a):
    """Design diagnostics only: local feasible intervals, not causal permission.

    D6 profiles are shown separately, because treating their union as one
    interval could report non-existent values as reachable (cf. D4 {0,2}).
    """
    if isinstance(design, TwoStageQuotaMixtureDesignV27):
        lines=[]
        for j,(quota,weight) in enumerate(zip(design.quota_profiles,
                                               design.profile_probabilities)):
            own_idx=next(i for i,g in enumerate(design.groups) if node in g)
            own_n=len(design.groups[own_idx]); own_m=quota[own_idx]
            if not (0 <= own_m-a <= own_n-1):
                lines.append(f'profile[{j}] pi={weight}: T_i={a} impossible; excluded after conditioning')
                continue
            pieces=[]
            for h,(group,m) in enumerate(zip(design.groups,quota)):
                owns=int(node in group)
                seen=len(refs.intersection(group))
                remain=m-a*owns
                available=len(group)-owns-seen
                lo=max(0,remain-available)
                hi=min(seen,remain)
                pieces.append(f'g{h}: neighbors={seen}, treated range={lo}..{hi}')
            lines.append(f'profile[{j}] pi={weight}; '+ '; '.join(pieces))
        return tuple(lines)
    if not isinstance(design,(TwoGroupFixedQuotaDesignV1,MultiGroupFixedQuotaDesignV25)):
        return ()
    out=[]
    for j,(group,quota) in enumerate(zip(design.groups,design.treated_quotas)):
        own=int(node in group)
        c=len(refs.intersection(group))
        residual=quota-a*own
        other=len(group)-own-c
        lo=max(0,residual-other)
        hi=min(c,residual)
        out.append(f'group[{j}]: neighbors={c}; remaining quota={residual}; feasible treated neighbors={lo}..{hi}')
    return tuple(out)


def diagnose_policy_signature_support_v25(
    study:NetworkStudyContextV17,target:TargetSemanticsV15,
    signature:SignatureSpecV20,
)->PolicySignatureSupportDiagnosticV25:
    """Exact policy-signature positivity plus node-level explanations; no A5 claim.

    Unlike the old D2/E1-only helper, this works for D1..D6 x E1..E5.
    The verifier independently computes each TARGET signature probability.
    A4/A5 are neither supplied nor silently admitted by this diagnostic.
    """
    if not isinstance(study,NetworkStudyContextV17) or not isinstance(target,TargetSemanticsV15) or not isinstance(signature,SignatureSpecV20):
        raise TypeError('Typed study, fixed-policy target, and R2 signature are required')
    if (study.observation_regime!='experimental' or study.design() is None
        or study.graph_timing_claim!='DECLARED_PRETREATMENT_FIXED'):
        raise ValueError('Known experimental law and fixed pretreatment network required')
    if (target.kind!='FIXED_FULL_ASSIGNMENT_POLICY_MEAN'
        or target.network_fingerprint!=study.network_fingerprint
        or target.node_order!=study.node_order
        or target.outcome!=study.outcome_variable
        or target.context!=study.context_reference
        or signature.study_scope_digest!=study.shared_scope_digest
        or signature.network_fingerprint!=study.network_fingerprint
        or signature.treatment_variable!=study.treatment_variable):
        raise ValueError('Study/target/signature scientific coordinates are inconsistent')
    net=study.network();design=study.design();assignment=AssignmentSpec(design)
    assignment._validate_network(net)
    if len(study.node_order)>4096 or net.max_degree()>4096:
        raise ValueError('A6 diagnostic outside software resource domain')
    core=dict(signature.core_collaborators) if signature.core_collaborators else None
    exposure=ExposureSpec(signature.grouping,core)
    policy=dict(zip(study.node_order,target.policy_assignment))
    full=assignment.full_assignment_probability(net,policy)
    nodes=[]
    for node,weight in zip(study.node_order,target.unit_weights):
        if Fraction(weight)==0:continue
        refs=exposure.reference_nodes(net,node)
        refs=set(refs if refs is not None else neighbor_set(net,node))
        d=len(refs);a=policy[node];k=sum(policy[j] for j in refs)
        ownlaw=assignment.conditional_neighbor_count_law(net,node,a,reference_nodes=frozenset(refs))
        reachable=tuple(j for j,mass in enumerate(ownlaw.conditional_count_mass) if mass>0)
        feasible_signatures=tuple(sorted({exposure.classify(j,d) for j in reachable})) if not (
            signature.grouping=='three_level_treated_neighbor_fraction' and d==0) else ()
        constraints=_stratum_constraints(design,node,refs,a)
        if signature.grouping=='three_level_treated_neighbor_fraction' and d==0:
            s=None;pi=Fraction(0)
            code='EXPOSURE_UNDEFINED_FOR_ISOLATE';detail='E2 neighbor fraction is undefined for degree zero'
        else:
            s=exposure.classify(k,d)
            pi=SupportEngine.from_count_law(ownlaw,exposure,s).joint_probability
            independent=_crosscheck(net,design,signature.grouping,node,a,s,refs)
            if independent!=pi:
                raise ArithmeticError(f'Independent signature support disagreement at {node}')
            if pi:
                code='POSITIVE_SIGNATURE_SUPPORT'
                detail='Target signature has strictly positive probability under declared original design'
            elif ownlaw.own_probability==0:
                code='OWN_TREATMENT_ZERO_SUPPORT'
                detail=f'T_i={a} is impossible under the original randomization law'
            elif not any(exposure.classify(x,d)==s for x in reachable):
                code='TARGET_EXPOSURE_UNREACHABLE'
                detail=f'Target requires K={k} mapped to S={s}; feasible treated-neighbor counts conditional on T_i={a}: {reachable}'
            else:
                # Should never occur if the conditional law and classify agree.
                raise ArithmeticError('Proposer support inconsistent with feasible count states')
        nodes.append(SignatureNodeSupportV25(node,d,a,k,s,str(ownlaw.own_probability),
            reachable,feasible_signatures,str(pi),'SUPPORTED' if pi>0 else 'UNSUPPORTED',
            code,detail,constraints))
    alt=None
    if isinstance(design,CompleteRandomizationDesignV1) and len(study.node_order)<=24:
        # Logical support exploration ONLY, not an automatic assumption change.
        feasible=[]
        for m in range(len(study.node_order)+1):
            alt_design=CompleteRandomizationDesignV1(m=m)
            q=AssignmentSpec(alt_design)
            good=True
            for item in nodes:
                if item.policy_signature is None:
                    good=False;break
                refs=exposure.reference_nodes(net,item.node_id)
                mass=SupportEngine.evaluate(network=net,assignment=q,exposure=exposure,
                    node_id=item.node_id,own_treatment_value=item.policy_own_treatment,
                    exposure_value=item.policy_signature).joint_probability
                if not mass:
                    good=False;break
            if good:feasible.append(m)
        alt=tuple(feasible)
    disclaimer=('A6 support-only computation under the declared design. Does NOT establish '
        'mean-signature sufficiency, conditional randomization in reality, A4 information, '
        'POINT identification, empirical estimability or non-identification by other routes. '
        'D2 alternative quotas would require a NEW documented experiment and corresponding data.')
    raw=dict(version=VERSION,study_digest=study.study_digest,
        target_fingerprint=target.target_digest,
        signature_fingerprint=signature.signature_fingerprint,
        design_kind=design.kind,grouping=signature.grouping,
        full_assignment_probability=str(full),
        supported_weighted_nodes=sum(x.status=='SUPPORTED' for x in nodes),
        unsupported_weighted_nodes=sum(x.status=='UNSUPPORTED' for x in nodes),
        nodes=tuple(nodes),counterfactual_d2_quotas_with_full_support=alt,
        disclaimer=disclaimer)
    return PolicySignatureSupportDiagnosticV25(**raw,evidence_digest=_digest({
        k: ([asdict(x) for x in v] if k=='nodes' else v) for k,v in raw.items()}))


def replay_policy_signature_support_v25(record:PolicySignatureSupportDiagnosticV25,
        study:NetworkStudyContextV17,target:TargetSemanticsV15,signature:SignatureSpecV20):
    """Reject mutable/tampered diagnostic fields by re-deriving exact probabilities."""
    if not isinstance(record,PolicySignatureSupportDiagnosticV25):
        raise TypeError('Typed A6 diagnostic required')
    fresh=diagnose_policy_signature_support_v25(study,target,signature)
    if fresh!=record:raise ValueError('A6 diagnostic tampered or source changed')
    return fresh
