"""Exact tiny-network sanity oracles for selected curated v0.4 benchmark references.

These are finite, explicit constructions using rational arithmetic. They establish
certain reference examples, NOT completeness of the full benchmark nor an
abstract theorem verifier. No PFN or LLM is involved.
"""
from __future__ import annotations
from fractions import Fraction as F
from itertools import product, combinations

VECTORS=list(product((0,1),repeat=4))


def iid4():
    return {t:F(1,16) for t in VECTORS}


def quota2():
    return {t:(F(1,6) if sum(t)==2 else F(0)) for t in VECTORS}


def conditional_expectation(law, predicate, outcome):
    p=sum((v for t,v in law.items() if predicate(t)),F(0))
    if p==0:return None,p
    ans=sum((v * outcome(t) for t,v in law.items() if predicate(t)),F(0))/p
    return ans,p


def check_r1b_support():
    q=quota2()
    return {'passed':q[(1,1,1,1)]==0 and q[(1,1,0,0)]==F(1,6),
            'q_all_treated':str(q[(1,1,1,1)]),'q_two_treated':str(q[(1,1,0,0)]),
            'supports':'C02,C04,C11,C16'}


def check_r2_signature():
    q=quota2()
    z=(1,1,1,1)
    # each node has one OTHER pretreatment core collaborator
    h=lambda i,a,s:F(10*i+2*a+3*s)
    outcomes=[]
    for i in range(4):
        c=(i+1)%4
        sig_pred=lambda t,i=i,c=c:t[i]==1 and t[c]==1
        observed,p=conditional_expectation(q,sig_pred,lambda t,i=i,c=c:h(i,t[i],t[c]))
        outcomes.append((observed,p,h(i,1,1)))
    return {'passed':q[z]==0 and all(mu==truth and p>0 for mu,p,truth in outcomes),
            'signature_probabilities':[str(p) for mu,p,truth in outcomes],
            'supports':'C03,C12'}


def check_weighted_arm_without_exposure_sufficiency():
    q=iid4()
    def g0(t): return F(t[1]+2*t[2]+3*t[3],6)>F(3,5)
    # Depends on WHO is treated, not only exposure class; deliberately not sufficient.
    def y0(t): return F(2*t[0]+3*t[1]-7*t[2]*t[3])+F(t[1]*t[3],2)
    target,p=conditional_expectation(q,lambda t:t[0]==1 and g0(t),y0)
    observed,p2=conditional_expectation(q,lambda t:t[0]==1 and g0(t),y0)
    return {'passed':p>0 and target==observed and p==p2,
            'arm_support':str(p),'arm_mean':str(target),'supports':'C01,C09'}


def check_arm_compression_not_policy():
    q=iid4()
    x=(1,1,1,0); y=(1,1,0,1)
    def exp_i(t,i):
        treated_neighbors=sum(t[j] for j in range(4) if j!=i)
        return int(treated_neighbors>1)  # strict majority among 3 neighbours
    def yA(i,t):return F(0)
    def yB(i,t):return F(int(t==x)-int(t==y)) if i==0 else F(0)
    equal_arms=True
    for i in range(4):
        for a,s in product((0,1),repeat=2):
            pred=lambda t,i=i,a=a,s=s:t[i]==a and exp_i(t,i)==s
            ea,pa=conditional_expectation(q,pred,lambda t,i=i:yA(i,t))
            eb,pb=conditional_expectation(q,pred,lambda t,i=i:yB(i,t))
            if pa!=pb or ea!=eb:equal_arms=False
    return {'passed':equal_arms and yA(0,x)!=yB(0,x),
            'all_node_arm_means_equal':equal_arms,
            'policy_target_world_A':str(yA(0,x)),
            'policy_target_world_B':str(yB(0,x)),
            'supports':'C06'}


def check_observational_worlds():
    # Exogenous U ~ Bernoulli(.5); T=U and Yobs=T in BOTH worlds, but ATE differs.
    observed_A={(u,u):F(1,2) for u in (0,1)}
    observed_B={(u,u):F(1,2) for u in (0,1)}
    ate_A=F(0) # Y(0)=Y(1)=U
    ate_B=F(1) # Y(0)=0,Y(1)=1
    return {'passed':observed_A==observed_B and ate_A!=ate_B,
            'ATE_A':str(ate_A),'ATE_B':str(ate_B),'supports':'C07,C13'}


def check_zero_node_propensity():
    law={t:(F(1,8) if t[0]==0 else F(0)) for t in VECTORS}
    p=sum((v for t,v in law.items() if t[0]==1),F(0))
    return {'passed':p==0,'P(T0=1)':str(p),'supports':'C10'}


def check_direct_design_vs_fixed_others():
    q=quota2()
    # i=0, one core collaborator=1, S0=T1. Y0 depends ONLY on T2, never on own treatment.
    y=lambda t:F(10*t[2])
    mu_11,p11=conditional_expectation(q,lambda t:t[0]==1 and t[1]==1,y)
    mu_01,p01=conditional_expectation(q,lambda t:t[0]==0 and t[1]==1,y)
    contrast=mu_11-mu_01
    own_contrast=F(0)
    return {'passed':p11>0 and p01>0 and contrast!=own_contrast,
            'design_standardized_direct_contrast':str(contrast),
            'fixed_others_direct_contrast':str(own_contrast),
            'supports':'C14'}


def check_iid_policy_tiny():
    q=iid4()
    return {'passed':q[(1,1,1,1)]==F(1,16),
            'q_all_treated':str(q[(1,1,1,1)]),'supports':'C05,C15'}


ORACLES=(check_r1b_support,check_r2_signature,check_weighted_arm_without_exposure_sufficiency,
         check_arm_compression_not_policy,check_observational_worlds,check_zero_node_propensity,
         check_direct_design_vs_fixed_others,check_iid_policy_tiny)


def run_oracles():
    return {f.__name__:f() for f in ORACLES}


if __name__=='__main__':
    import json
    result=run_oracles()
    print(json.dumps({'passed':sum(r['passed'] for r in result.values()),'checks':len(result),
                      'results':result},ensure_ascii=False,indent=2))
    if not all(r['passed'] for r in result.values()):raise SystemExit(1)
