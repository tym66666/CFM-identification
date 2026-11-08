"""Audit the mathematical target proposed by a reading, without calling Core.

Source fields may select a target rule as well as locate evidence. Comparing
only raw non-source fields can therefore miss a dropped known condition.
This audit requires explicit projected targets; an absent projection never
passes. It is an evaluation check against a separately supplied reference,
not a semantic proof or an automatic scientific approval.
"""
from copy import deepcopy


def compare_target_projections(reference_preview, actual_preview):
    expected=reference_preview.get('proposed_targets')
    actual=actual_preview.get('proposed_targets')
    available=(isinstance(expected,list) and bool(expected) and isinstance(actual,list) and bool(actual)
               and all(isinstance(t,dict) for t in expected+actual))
    if not available:
        return dict(available=False,passed=False,issues=[dict(reason='EXPLICIT_TARGET_PROJECTION_REQUIRED')])

    def canonical(target):
        result=deepcopy(target)
        # These coordinates are sets; any weights remain attached to their IDs.
        for key in ('nodes','treated_nodes'):
            if isinstance(result.get(key),list) and all(isinstance(x,str) for x in result[key]):
                result[key]=sorted(result[key])
        return result

    expected=[canonical(t) for t in expected];actual=[canonical(t) for t in actual]
    issues=[]
    if len(expected)!=len(actual):issues.append(dict(reason='QUERY_COUNT_CHANGED',expected=len(expected),actual=len(actual)))
    for i,(left,right) in enumerate(zip(expected,actual),1):
        for key in sorted(set(left)|set(right)):
            if left.get(key,'<MISSING>')!=right.get(key,'<MISSING>'):
                issues.append(dict(query_index=i,field=key,expected=left.get(key,'<MISSING>'),actual=right.get(key,'<MISSING>')))
    return dict(available=True,passed=not issues,issues=issues)
