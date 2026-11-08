"""Independent D4 exact-support verifier: balanced polynomial over CLUSTER draws.

Distinct from the proposer sequential conditional-count DP. A treatment at
one node fixes the entire pretreatment cluster, not just that node.
"""
from fractions import Fraction

from ..schemas import ClusterBernoulliDesignV24, NetworkExposureSpec
from .assignment import neighbor_set


def verify_cluster_joint_support(
    network: NetworkExposureSpec, design: ClusterBernoulliDesignV24,
    node_id: str, a: int, s: int, grouping: str,
    match_exposure, reference_nodes: frozenset[str] | None = None,
) -> Fraction:
    if node_id not in network.node_ids or a not in (0,1):
        raise ValueError('Invalid D4 arm query')
    refs = set(reference_nodes) if reference_nodes is not None else neighbor_set(network,node_id)
    owner = next(j for j,cluster in enumerate(design.clusters) if node_id in cluster)
    own_p = Fraction(design.cluster_probabilities[owner])
    own = own_p if a else 1-own_p
    if not own:
        return Fraction(0)
    forced = a*sum(member in refs for member in design.clusters[owner])
    polys=[]
    for j,cluster in enumerate(design.clusters):
        if j == owner:
            continue
        count = sum(member in refs for member in cluster)
        if not count:
            continue
        p = Fraction(design.cluster_probabilities[j])
        poly=[Fraction(0)]*(count+1)
        poly[0] += 1-p
        poly[count] += p
        polys.append(tuple(poly))
    if not polys:
        polys = [(Fraction(1),)]
    while len(polys)>1:
        next_level=[]
        for j in range(0,len(polys),2):
            if j+1==len(polys):
                next_level.append(polys[j]);continue
            x,y=polys[j],polys[j+1]
            z=[Fraction(0)]*(len(x)+len(y)-1)
            for k,v in enumerate(x):
                if v:
                    for l,w in enumerate(y):
                        if w:
                            z[k+l] += v*w
            next_level.append(tuple(z))
        polys=next_level
    return own*sum((mass for k,mass in enumerate(polys[0])
                    if match_exposure(k+forced,len(refs),s,grouping)),Fraction(0))
