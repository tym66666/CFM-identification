"""Sharp binary-IV ATE bounds from a finite latent response-type LP."""
from __future__ import annotations
import numpy as np
from scipy.optimize import linprog
from .iv_contract import validate_observed, IVInputError
from .iv_types import observed_constraint_system, find_farkas_certificate


def build_lp(observed, *, monotonicity: bool = False):
    return observed_constraint_system(observed, monotonicity=monotonicity)


def _solve_ate_bounds(observed, *, monotonicity: bool = False):
    """Solve sharp ATE bounds and return endpoint primal/dual certificates.

    This numerical solver does not grant scientific approval. Callers must
    retain separate source/reading and scientific review records.
    """
    try:
        types, A, b, c = build_lp(observed, monotonicity=monotonicity)
    except (IVInputError, TypeError, ValueError) as exc:
        return {"status": "CHECK_BLOCKED", "reason_code": getattr(exc, "code", "INVALID_IV_INPUT"),
                "detail": str(exc), "certificate": None}
    lo = linprog(c, A_eq=A, b_eq=b, bounds=(0, None), method="highs")
    hi = linprog(-c, A_eq=A, b_eq=b, bounds=(0, None), method="highs")
    if lo.status == 2 or hi.status == 2:
        farkas = find_farkas_certificate(A, b)
        if farkas is None:
            return {"status": "CHECK_BLOCKED", "reason_code": "INFEASIBLE_STATUS_WITHOUT_REPLAYABLE_CERTIFICATE",
                    "type_count": len(types), "certificate": None}
        return {"status": "INCOMPATIBLE", "reason_code": "OBSERVED_LAW_CONFLICTS_WITH_ACCEPTED_IV_TYPE_MODEL",
                "lower_solver_message": lo.message, "upper_solver_message": hi.message,
                "type_count": len(types), "certificate": farkas}
    if not lo.success or not hi.success:
        failed = lo if not lo.success else hi
        return {"status": "CHECK_BLOCKED", "reason_code": "ATE_LP_NUMERICAL_FAILURE",
                "solver_status": int(failed.status), "solver_message": failed.message,
                "type_count": len(types), "certificate": None}
    lower_dual = np.asarray(lo.eqlin.marginals, dtype=float)
    upper_dual = -np.asarray(hi.eqlin.marginals, dtype=float)
    result = {
        "status": "SHARP_BOUNDS", "estimand": "ATE=E[Y(1)-Y(0)]",
        "target": {"kind": "ATE", "outcome_domain": "BINARY", "treatment_domain": "BINARY"},
        "bounds": [float(lo.fun), float(-hi.fun)], "monotonicity": monotonicity,
        "type_count": len(types), "types": [list(t) for t in types],
        "lower_witness": lo.x.tolist(), "upper_witness": hi.x.tolist(),
        "lower_dual": lower_dual.tolist(), "upper_dual": upper_dual.tolist(),
        "lower_objective": float(np.dot(c, lo.x)), "upper_objective": float(np.dot(c, hi.x)),
        "solver": "scipy.optimize.linprog(method='highs')",
        "certificate": {"kind": "PRIMAL_DUAL_ENDPOINT_CERTIFICATE", "independent_replay_required": True},
    }
    return result


def solve_ate_bounds(observed, *, monotonicity=False):
    from .iv_types import model_descriptor
    try:
        result = _solve_ate_bounds(observed, monotonicity=monotonicity)
        result['model'] = model_descriptor(monotonicity, 'ATE')
        return result
    except (ValueError, TypeError, ArithmeticError, RuntimeError):
        return dict(status='CHECK_BLOCKED', reason_code='IV_INPUT_OR_SOLVER_FAILURE', certificate=None)
