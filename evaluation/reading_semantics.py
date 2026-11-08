"""Evaluation-only semantic comparison on a fixed, bound unit roster.

Listing every unit explicitly and choosing the whole roster denote the same
population in this reading protocol. This does not change model responses,
future rosters, aggregation weights, target validation, or Core inputs.
"""
from copy import deepcopy

EVIDENCE_FIELDS=frozenset({'quote','population_source','remaining_source','remaining_evidence_span','peer_evidence',
    'independence_source','probability_source','design_sources','exposure_source','source'})


def semantic_payload(raw, node_ids):
    """Pair with target-projection and source audits; not a standalone grade."""
    roster=tuple(node_ids)
    def visit(value,key=''):
        if isinstance(value,dict):
            result={k:visit(v,k) for k,v in value.items() if k not in EVIDENCE_FIELDS}
            if key=='population' and result.get('selection')=='指定':
                ids=result.get('ids')
                if (roster and isinstance(ids,list) and all(isinstance(x,str) for x in ids)
                    and len(ids)==len(roster)==len(set(ids)) and set(ids)==set(roster)):
                    result.update(selection='全体',ids=[])
            return result
        if isinstance(value,list):
            result=[visit(v) for v in value]
            return sorted(result) if key in ('population','ids') and all(isinstance(v,str) for v in result) else result
        return deepcopy(value)
    return visit(raw)
