"""Minimal binary-IV example; scientific assumptions are explicit inputs, not inferred."""
from cfm_id.iv_late_solver import identify_late
from cfm_id.iv_late_verify import verify_late_result
from cfm_id.iv_ate_solver import solve_ate_bounds
from cfm_id.iv_ate_verify import verify_ate_result

# A valid monotone population with a negative complier effect of -0.5.
observed = {
    (0,0,0):0.0,(0,0,1):1.0,(0,1,0):0.0,(0,1,1):0.0,
    (1,0,0):0.0,(1,0,1):0.75,(1,1,0):0.125,(1,1,1):0.125,
}
late = identify_late(observed, assumptions_accepted=True)
print('LATE:', late)
print('LATE replay:', verify_late_result(observed, late))
ate = solve_ate_bounds(observed, monotonicity=True)
print('ATE:', ate.get('status'), ate.get('bounds'), ate.get('reason_code'))
if ate.get('status') == 'SHARP_BOUNDS':
    print('ATE replay:', verify_ate_result(observed, ate, monotonicity=True))
