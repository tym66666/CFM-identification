"""Target-only evaluation for current, ID-bound comparison readings.

This does not approve a candidate, verify assignment facts, certify scientific
conditions, or replace any historical/frozen scoring rule. Actual candidates
are never changed. It only removes the irrelevant order of an explicitly
equal-weight population after the existing coordinate validation succeeds.
"""
from copy import deepcopy


def equivalent_target(bundle, actual, reference):
    """Compare full reading/binding and compiled targets without list-order bias.

Both arguments are comparison members (reading plus reported_assignment).
Incomplete readings retain all their unknowns. Two empty compiled-target
maps alone are never enough for equivalence; full normalized readings must
also agree. Assignment facts and source evidence require separate metrics.
"""
    # Lazy import avoids changing existing module initialization paths.
    from cfm_id.fixed_comparison import project
    try:
        actual_targets=project(bundle,actual)[3]
        reference_targets=project(bundle,reference)[3]
        ranks={node:i for i,node in enumerate(bundle['node_order'])}
        def view(candidate):
            reading=deepcopy(candidate['reading'])
            for question in reading['questions'].values():
                if question['aggregation']=='等权平均' and question['population'] is not None:
                    question['population']=sorted(question['population'],key=ranks.__getitem__)
            return reading
        return actual_targets==reference_targets and view(actual)==view(reference)
    except (ValueError,TypeError,KeyError,AttributeError):
        return False
