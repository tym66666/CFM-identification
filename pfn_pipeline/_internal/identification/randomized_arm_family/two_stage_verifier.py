"""Independent D6 verifier: ORIGINAL allocation integer generating polynomials.

This checker does not invoke the proposer's conditional hypergeometric mixture
or AssignmentSpec. The small-network tests independently enumerate 2^N vectors.
"""
from __future__ import annotations
from fractions import Fraction
from math import comb
from collections.abc import Callable
from ..schemas import NetworkExposureSpec, TwoStageQuotaMixtureDesignV27


def original_assignment_mass(
    node_order: tuple[str,...], design: TwoStageQuotaMixtureDesignV27,
    allocation: tuple[int,...],
) -> Fraction:
    """Independent full-vector q(z) via profile matching and direct allocation counting."""
    if len(node_order)!=len(allocation) or len(node_order)!=len(set(node_order)):
        raise ValueError('D6 verifier assignment coordinate mismatch')
    if any(type(x) is not int or x not in (0,1) for x in allocation):
        raise ValueError('D6 verifier needs binary full vector')
    lookup=dict(zip(node_order,allocation))
    if any(node not in lookup for group in design.groups for node in group):
        raise ValueError('D6 verifier group coordinate mismatch')
    q=tuple(sum(lookup[n] for n in group) for group in design.groups)
    masses={profile:Fraction(raw) for profile,raw in zip(design.quota_profiles,design.profile_probabilities)}
    if q not in masses:return Fraction(0)
    denom=1
    for group,quota in zip(design.groups,q):denom*=comb(len(group),quota)
    return masses[q]/denom


def original_integer_polynomial(
    network: NetworkExposureSpec, design: TwoStageQuotaMixtureDesignV27,
    node_id: str, a: int, reference_nodes: frozenset[str],
) -> tuple[Fraction,...]:
    """P(T_i=a,K=k) from unconditional, integer legal allocation counts.

    For profile u the number of legal full vectors with own a and k treated
    reference neighbors has coefficients of product_g
    sum_k C(c_g,k) C(n_g-own-c_g, m_g-own*a-k) x^k.
    Divide by product_g C(n_g,m_g), then weight by the first-stage profile law.
    """
    if node_id not in network.node_ids or a not in (0,1) or type(a) is not int:
        raise ValueError('D6 verifier node and own treatment invalid')
    if node_id in reference_nodes or not reference_nodes <= set(network.node_ids):
        raise ValueError('D6 verifier reference coordinate mismatch')
    degree=len(reference_nodes)
    total=[Fraction(0)]*(degree+1)
    for quotas, raw in zip(design.quota_profiles,design.profile_probabilities):
        numerator=[1]
        denom=1
        for g,m in zip(design.groups,quotas):
            own=int(node_id in g)
            selected=len(reference_nodes.intersection(g))
            rest=len(g)-own-selected
            ways=[comb(selected,k)*comb(rest,m-a*own-k)
                  if 0 <= m-a*own-k <= rest else 0 for k in range(selected+1)]
            new=[0]*(len(numerator)+len(ways)-1)
            for j,x in enumerate(numerator):
                for k,y in enumerate(ways):new[j+k]+=x*y
            numerator=new
            denom*=comb(len(g),m)
        if len(numerator)!=degree+1:raise ValueError('D6 verifier polynomial shape mismatch')
        for k,x in enumerate(numerator):total[k]+=Fraction(raw)*Fraction(x,denom)
    return tuple(total)


def independent_joint_support(
    network: NetworkExposureSpec, design: TwoStageQuotaMixtureDesignV27,
    node_id: str, a: int, s: int, grouping: str,
    exposure_match: Callable[[int,int,int,str],bool],
    reference_nodes: frozenset[str] | None = None,
) -> Fraction:
    # Do not reuse proposer neighbor_set or exposure bin implementation.
    if reference_nodes is None:
        refs=set()
        for i,j in network.undirected_edges:
            if i==node_id:refs.add(j)
            elif j==node_id:refs.add(i)
        reference_nodes=frozenset(refs)
    dist=original_integer_polynomial(network,design,node_id,a,reference_nodes)
    d=len(reference_nodes)
    return sum((x for k,x in enumerate(dist) if exposure_match(k,d,s,grouping)),Fraction(0))
