"""Read-only presentation of certified results; no solver or model invocation."""
from copy import deepcopy
from fractions import Fraction
from .business_core_pilot_base import canonical_hash


def effect_summary(proof):
    """Compact only after exact verification of every displayed coefficient."""
    if proof.get('status')!='POINT' or proof.get('verification_status')!='VERIFIED':raise ValueError('VERIFIED_EFFECT_REQUIRED')
    arms=proof['constituent_arms'];nodes=sorted({x['node_id'] for x in arms});n=len(nodes)
    positive={(x['own_treatment'],x['exposure_state']) for x in arms if Fraction(x['coefficient'])>0}
    negative={(x['own_treatment'],x['exposure_state']) for x in arms if Fraction(x['coefficient'])<0}
    if not n or len(positive)!=1 or len(negative)!=1:return proof['identified_functional'],False
    a,b=next(iter(positive)),next(iter(negative))
    expected={(node,*s):Fraction(sign,n) for node in nodes for s,sign in ((a,1),(b,-1))}
    actual={}
    for x in arms:
        key=(x['node_id'],x['own_treatment'],x['exposure_state'])
        if key in actual:return proof['identified_functional'],False
        actual[key]=Fraction(x['coefficient'])
        if Fraction(x['joint_support'])<=0:raise ValueError('NONPOSITIVE_CERTIFICATE_SUPPORT')
    if expected!=actual:return proof['identified_functional'],False
    return f'θ = (1/{n}) Σᵢ [ μᵢ({a[0]},{a[1]} | W) − μᵢ({b[0]},{b[1]} | W) ]',True


def cards(result):
    """All certificate formulas come from immutable result fields."""
    out=[]
    if result.get('query_views'):
        for q in result['query_views']:
            if not q.get('certificate_replayed'):
                out.append(dict(query_id=q['query_id'],state=q['state'],question=q.get('question'),certificate_replayed=False));continue
            proof=q['proof'];effect=proof.get('results')
            if effect:
                if len(effect)!=1 or proof.get('verification_status')!='VERIFIED':raise ValueError('SINGLE_VERIFIED_DISPLAY_EFFECT_REQUIRED')
                p=effect[0];formula,compact=effect_summary(p);full=p['identified_functional'];fingerprint=q['certificate_sha256']
                support=None;kind=p['kind']
            else:
                if proof.get('status')!='POINT' or proof.get('verification_status')!='VERIFIED':raise ValueError('VERIFIED_ARM_REQUIRED')
                p=proof;f=p['identified_functional'];formula=f"θ = μ_{f['node_id']}({f['own_treatment_value']},{f['exposure_value']} | W)";compact=False
                full=f['functional'];fingerprint=canonical_hash(p['certificate']);support=p['certificate']['joint_arm_support_probability'];kind='ARM'
            out.append(dict(query_id=q['query_id'],state='CORE_POINT',question=q.get('question'),certificate_replayed=True,
                route=q['route'],kind=kind,formula=formula,compact_formula_checked=compact,full_formula=full,
                certificate_sha256=fingerprint,support_probability=support,proof=deepcopy(proof)))
    elif result.get('view',{}).get('state')=='CORE_POINT':
        view=result['view'];c=view['core'];p=result['identification']['results'][0]['core']['identification'];f=p['identified_functional']
        if not c.get('certificate_replayed') or p.get('verification_status')!='VERIFIED':raise ValueError('VERIFIED_ARM_REQUIRED')
        out.append(dict(query_id=view['query_id'],state='CORE_POINT',question=view['question'],certificate_replayed=True,
            route=c['route'],kind='ARM',formula=f"θ = μ_{f['node_id']}({f['own_treatment_value']},{f['exposure_value']} | W)",
            compact_formula_checked=False,full_formula=f['functional'],certificate_sha256=c['certificate_sha256'],
            support_probability=c['assignment_probability'],proof=deepcopy(p)))
    return out
