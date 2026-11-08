"""Opt-in correlated observational assignment A4 for the EXISTING R3 nodewise theorem.

P(X=x|W) is a finite, exact pretreatment population.  Conditional on each
complete X=x, P(T=t|X=x,W)=sum_h alpha_h(x) prod_j Bernoulli(r_hj(x)).
Mixing induces correlated choices after conditioning on X, but cannot establish
local-covariate mean exchangeability or exposure sufficiency.  Both A5 licenses
and the exact population conditional-outcome operators remain indispensable.

The same R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS target and independent verifier
are reused; this module only constructs a different A4 source, not a new family.
"""
from __future__ import annotations
from fractions import Fraction

from .identification_observational_nodewise_adjustment import (
    _fraction_str, _schema, ADJUSTMENT, CONDITIONAL_MIXTURE_LAW,
    CONDITIONAL_MIXTURE_OPERATOR, ConditionalBernoulliComponentV28P2,
    NodewiseMixturePretreatmentProfileV28P2, NodewiseLocalArmPopulationV28,
)
from .identification_observational_r3 import R3Unavailable
from .identification_policy_r2 import SignatureSpecV20
from .network_inquiry_shadow import NetworkStudyContextV17


def declare_nodewise_correlated_arm_population_v28p2(
        study:NetworkStudyContextV17, signature:SignatureSpecV20,
        *, source_id:str, provenance:str, feature_name:str,
        profiles, covered_cells, admission:str='ADMITTED',
        availability:str='SYMBOLIC_POPULATION_OPERATOR') -> NodewiseLocalArmPopulationV28:
    """Declare symbolic A4 only; DO NOT infer this law from finite-sample data.

    profiles entries: (label, P(X=x|W), complete binary X vector,
                       ((P(H=h|X=x,W), complete Bernoulli probability vector),...)).
    H is a mixture index for OBSERVATIONAL ASSIGNMENT, not a treatment or causal
    ignorability guarantee.  Components are canonicalized by their probabilities.
    """
    if (not isinstance(study,NetworkStudyContextV17)
        or study.observation_regime!='observational' or study.design() is not None):
        raise ValueError('NODEWISE_MIXTURE_OBSERVATIONAL_STUDY_REQUIRED')
    if (not isinstance(signature,SignatureSpecV20)
        or signature.study_scope_digest!=study.shared_scope_digest):
        raise ValueError('NODEWISE_MIXTURE_SIGNATURE_MISMATCH')
    if not isinstance(feature_name,str) or not feature_name.strip():
        raise ValueError('NODEWISE_MIXTURE_FEATURE_NAME_REQUIRED')
    rows=[]
    for label,mass,x,components in profiles:
        if isinstance(x,dict):
            if set(x)!=set(study.node_order):
                raise ValueError('NODEWISE_MIXTURE_COMPLETE_X_REQUIRED')
            x=tuple(x[node] for node in study.node_order)
        comp=[]
        for weight,probs in components:
            if isinstance(probs,dict):
                if set(probs)!=set(study.node_order):
                    raise ValueError('NODEWISE_MIXTURE_COMPLETE_PROPENSITY_VECTOR_REQUIRED')
                probs=tuple(probs[node] for node in study.node_order)
            comp.append(ConditionalBernoulliComponentV28P2(
                _fraction_str(weight,positive=True),tuple(_fraction_str(p) for p in probs)))
        comp.sort(key=lambda c:c.treatment_one_probabilities)
        rows.append(NodewiseMixturePretreatmentProfileV28P2(
            label,_fraction_str(mass,positive=True),tuple(x),tuple(comp)))
    rows.sort(key=lambda p:p.label)
    positions={node:i for i,node in enumerate(study.node_order)}
    cells=tuple(sorted((tuple(c) for c in covered_cells),
        key=lambda c:(positions[c[0]],*c[1:])))
    return NodewiseLocalArmPopulationV28(
        source_id,provenance,admission,availability,
        study.shared_scope_digest,study.protocol_digest,study.node_order,
        study.outcome_variable,study.context_reference,feature_name,
        signature.signature_fingerprint,_schema(study,signature,feature_name),
        tuple(rows),cells,adjustment_kind=ADJUSTMENT,
        factorization_kind=CONDITIONAL_MIXTURE_LAW,
        operator=CONDITIONAL_MIXTURE_OPERATOR,
    )


__all__=['declare_nodewise_correlated_arm_population_v28p2',
         'ConditionalBernoulliComponentV28P2',
         'NodewiseMixturePretreatmentProfileV28P2']
