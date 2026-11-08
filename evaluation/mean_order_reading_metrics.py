"""Non-throwing candidate metrics for fully specified per-object references.

This is an evaluation utility, not a semantic repair or scientific approval.
Source validity alone never proves the natural-language interpretation.
"""
from cfm_id import mean_order_reading as reader

def _rows(value):
    rows={}
    for claim in value.claims:
        if not claim.nodes or claim.axis=='UNKNOWN':return None
        for node in claim.nodes:
            rows[node,claim.axis]=(claim.relation,claim.level,claim.scope,claim.basis,set(claim.source_ids))
    return rows

def compare_order_readings(bundle,actual,reference):
    """Score candidate unknowns as failures, without dropping the observation.

    The reference must explicitly cover every roster object and both axes.
    Missing/unknown candidate objects and axes are allowed by the reading
    contract; they are incomplete predictions, not scoring exceptions.
    Malformed reference data still raises so a broken gold label is visible.
    """
    expected=reader.OrderReading.model_validate(reference)
    reader.project(bundle,reference)
    want=_rows(expected)
    grid={(n,a) for n in bundle['node_order'] for a in ('OWN','PEERS')}
    if want is None or set(want)!=grid:raise ValueError('COMPLETE_REFERENCE_OBJECT_AXES_REQUIRED')
    result=dict(valid_reading=False,object_axes_complete=False,order_fields=False,
        source_evidence=False,order_flags=False,semantic_passed=False,reading_state=None,
        scientific_approval=False,counts_in_denominator=True,error_code=None)
    try:
        parsed=reader.OrderReading.model_validate(actual)
        projected=reader.project(bundle,actual)
    except (ValueError,TypeError,KeyError):
        return dict(result,error_code='INVALID_ORDER_READING')
    got=_rows(parsed)
    result.update(valid_reading=True,reading_state=projected['state'],
        order_flags=parsed.reported_conflict==expected.reported_conflict
            and set(parsed.other_restriction_source_ids)==set(expected.other_restriction_source_ids))
    if got is None or set(got)!=grid:
        return dict(result,error_code='INCOMPLETE_OBJECT_AXES')
    result.update(object_axes_complete=True,
        order_fields=all(got[k][:4]==v[:4] for k,v in want.items()),
        source_evidence=all(v[4]<=got[k][4] for k,v in want.items()))
    result['semantic_passed']=all(result[k] for k in ('order_fields','source_evidence','order_flags'))
    return result

