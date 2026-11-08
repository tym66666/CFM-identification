"""Compatibility import. New runtime code uses cfm_id_llm.readers.mean_order.

Protocol values, public call signatures and referenced type identities are retained.
Reference conversion and scoring, when present, remain evaluation-only.
"""
from cfm_id_llm.readers.mean_order import *  # noqa: F401,F403
from cfm_id_llm.readers import mean_order as _implementation


def __getattr__(name):
    # Preserve explicit access to historical private helpers without copies.
    return getattr(_implementation, name)


def reference_wire(bundle,canonical):
    """Mechanical reference conversion only; authors annotate observed statistics.

    Legacy UNKNOWN remains unknown here. This helper does not guess the new
    quantity from prose or silently label it OBSERVED_STATISTIC.
    """
    comp,order=legacy.split(canonical);ids.resolve_reading(bundle,comp);legacy.project(bundle,order)
    claims=[]
    inverse={v:k for k,v in DIRECTIONS.items()}
    quantities={'CONDITIONAL_MEAN':'平均潜在结果','EACH_OUTCOME':'每次潜在结果','UNKNOWN':'尚不明确'}
    basis={'ASSUMPTION_STATEMENT':'提出条件','OBSERVED_PATTERN':'仅报告观察','UNKNOWN':'尚不明确'}
    for old in order['claims']:
        none=old['relation']=='NOT_ASSUMED'
        if none and old['basis']!='ASSUMPTION_STATEMENT':raise ValueError('EXPLICIT_NONASSUMPTION_REFERENCE_REQUIRED')
        if not none and old['level'] not in quantities:raise ValueError('EXPLICIT_REFERENCE_LEVEL_REQUIRED')
        claims.append(dict(nodes=deepcopy(old['nodes']),axis=old['axis'],
            declaration='明确不作假设' if none else basis[old['basis']],
            quantity=None if none else quantities[old['level']],
            direction=None if none else inverse[old['relation']],scope=old['scope'],source_ids=list(old['source_ids'])))
    raw=dict(comparison=deepcopy(comp),order_reading=dict(version=VERSION,claims=claims,
        reported_conflict=order['reported_conflict'],other_restriction_source_ids=list(order['other_restriction_source_ids'])))
    if to_canonical(bundle,raw)!=canonical:raise ValueError('REFERENCE_PROJECTION_MISMATCH')
    return raw


def wire_metrics(bundle,actual,reference):
    """Full new semantics, including distinctions absent from legacy UNKNOWN."""
    # Reference errors are setup errors, not model failures.
    to_canonical(bundle,reference)
    grid={(n,a) for n in bundle['node_order'] for a in ('OWN','PEERS')}
    def rows(raw):
        out={}
        for r in raw['order_reading']['claims']:
            if not r['nodes'] or r['axis']=='UNKNOWN':return None
            for n in r['nodes']:
                out[n,r['axis']]=(r['declaration'],r['quantity'],r['direction'],r['scope'],set(r['source_ids']))
        return out
    expected=rows(reference)
    if expected is None or set(expected)!=grid:raise ValueError('COMPLETE_FACTORED_REFERENCE_REQUIRED')
    result=dict(valid_wire=False,fields_match=False,source_evidence=False,flags_match=False,passed=False,counts_in_denominator=True)
    try:to_canonical(bundle,actual)
    except (ValueError,TypeError,KeyError):return result
    got=rows(actual);result['valid_wire']=True
    if got is None or set(got)!=grid:return result
    result.update(fields_match=all(got[k][:4]==v[:4] for k,v in expected.items()),
        source_evidence=all(v[4]<=got[k][4] for k,v in expected.items()),
        flags_match=actual['order_reading']['reported_conflict']==reference['order_reading']['reported_conflict']
            and set(actual['order_reading']['other_restriction_source_ids'])==set(reference['order_reading']['other_restriction_source_ids']))
    result['passed']=all(result[k] for k in ('fields_match','source_evidence','flags_match'))
    return result
