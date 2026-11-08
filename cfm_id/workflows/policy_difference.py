"""Ordered receipt for two existing R2 results; no new Core theorem.

Owns the business composition boundary only. Native identification and its
independent verifier remain in pfn_pipeline. No reading, approval or estimation.
"""
from copy import deepcopy
from fractions import Fraction
from cfm_id_bridge.scientific_binding import sha

VERSION = 'r2-policy-difference-1'
SIDES = ('first', 'second')


def _verified_endpoints(first, second, target):
    from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21, replay_verified_business_outcome
    from pfn_pipeline.identification_policy_r2 import VerifiedSignaturePolicyV20
    if set(target) != {'node_order','first','second','unit_weights','operation'} or target['operation'] != 'first_minus_second':
        raise ValueError('EXACT_ORDERED_TARGET_REQUIRED')
    before = sha((first, second))
    for side, outcome in zip(SIDES, (first, second)):
        if (type(outcome) is not VerifiedBusinessOutcomeV21 or outcome.status != 'POINT'
                or outcome.route != 'R2_MEAN_SIGNATURE' or type(outcome.result) is not VerifiedSignaturePolicyV20
                or replay_verified_business_outcome(outcome) is not True):
            raise ValueError('TWO_REPLAYED_R2_ENDPOINTS_REQUIRED')
        t = outcome.result.target
        if (list(t.node_order) != target['node_order'] or list(t.policy_assignment) != target[side]
                or list(t.unit_weights) != target['unit_weights']):
            raise ValueError('ENDPOINT_TARGET_MISMATCH')
    if sha((first, second)) != before:
        raise ValueError('ENDPOINT_REPLAY_MUTATED_INPUT')
    a,b = first.result,second.result
    for key in ('study','signature','sufficiency','sources','assumptions'):
        if sha(getattr(a,key)) != sha(getattr(b,key)):
            raise ValueError('COMMON_ENDPOINT_MODEL_REQUIRED')
    weights = [Fraction(w) for w in target['unit_weights']]
    positive = [w for w in weights if w > 0]
    if not positive or any(w < 0 for w in weights) or sum(weights) != 1 or len(set(positive)) != 1:
        raise ValueError('COMMON_EQUAL_POPULATION_REQUIRED')


def compose(first, second, *, target, binding):
    _verified_endpoints(first,second,target)
    terms=[]
    for side,sign,outcome in zip(SIDES,(1,-1),(first,second)):
        r=outcome.result
        for cell,weight,observable in zip(r.policy_node_classes,r.node_weights,r.required_observables):
            terms.append(dict(side=side,node=cell[0],assignment=list(r.target.policy_assignment),
                own=cell[1],exposure=cell[2],coefficient=str(sign*Fraction(weight)),observable=observable))
    receipt=dict(version=VERSION,verification='TWO_R2_CORE_REPLAYS_AND_SIGNED_COMPOSITION',
        target=deepcopy(target),binding=deepcopy(binding),study_sha256=sha(first.result.study),
        endpoint_sha256={s:sha(r.summary()) for s,r in zip(SIDES,(first,second))},terms=terms,
        identified_functional=f'({first.result.identified_functional}) - ({second.result.identified_functional})',
        new_core_theorem=False,estimation_handoff_allowed=False)
    receipt['receipt_sha256']=sha(receipt)
    return receipt


def replay(receipt, first, second, *, target, binding):
    """Reconstruct signed coordinates from external target and native evidence."""
    try:
        _verified_endpoints(first,second,target)
        r=deepcopy(receipt);digest=r.pop('receipt_sha256')
        if sha(r)!=digest or r['target']!=target or r['binding']!=binding:
            return False
        if (set(r)!={'version','verification','target','binding','study_sha256','endpoint_sha256',
                     'terms','identified_functional','new_core_theorem','estimation_handoff_allowed'}
                or r['version']!=VERSION or r['verification']!='TWO_R2_CORE_REPLAYS_AND_SIGNED_COMPOSITION'
                or r['study_sha256']!=sha(first.result.study) or r['new_core_theorem'] is not False
                or r['estimation_handoff_allowed'] is not False or set(r['endpoint_sha256'])!=set(SIDES)):
            return False
        expected=[]
        for side,outcome in zip(SIDES,(first,second)):
            x=outcome.result
            if r['endpoint_sha256'][side]!=sha(outcome.summary()):return False
            by_node={cell[0]:(cell[1],cell[2],observable) for cell,observable in zip(x.policy_node_classes,x.required_observables)}
            for node,weight in zip(target['node_order'],target['unit_weights']):
                if Fraction(weight):
                    own,exposure,observable=by_node[node]
                    coefficient=Fraction(weight) if side=='first' else -Fraction(weight)
                    expected.append(dict(side=side,node=node,assignment=target[side],own=own,exposure=exposure,
                        coefficient=str(coefficient),observable=observable))
        return r['terms']==expected and r['identified_functional']==f'({first.result.identified_functional}) - ({second.result.identified_functional})'
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        return False
