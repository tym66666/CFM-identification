"""Wald/LATE calculation with monotone latent-type compatibility checking."""
from __future__ import annotations
import numpy as np
from scipy.optimize import linprog
from .iv_contract import validate_observed, IVInputError
from .iv_types import observed_constraint_system, find_farkas_certificate


def _mean(observed, z, variable):
    return sum(variable(d, y) * observed[z, d, y] for d in (0, 1) for y in (0, 1))


def _identify_late(observed, *, assumptions_accepted: bool = False, tol: float = 1e-9) -> dict:
    """Identify complier LATE only after separate scientific approval.

    Negative effects are allowed: for binary Y, the logical range is [-1, 1].
    A common 12-type monotone latent law must also reproduce both Z-stratum
    observed distributions; a positive first stage alone is not sufficient.
    """
    if assumptions_accepted is not True:
        return {"status": "REVIEW_REQUIRED", "reason_code": "IV_SCIENTIFIC_ASSUMPTIONS_NOT_REVIEWED",
                "certificate": None}
    try:
        p = validate_observed(observed)
        types, A, b, _ = observed_constraint_system(p, monotonicity=True)
    except (IVInputError, TypeError, ValueError) as exc:
        return {"status": "CHECK_BLOCKED", "reason_code": getattr(exc, "code", "INVALID_OBSERVED_LAW"),
                "detail": str(exc), "certificate": None}
    feasibility = linprog(np.zeros(len(types)), A_eq=A, b_eq=b, bounds=(0, None), method="highs")
    if feasibility.status == 2:
        farkas = find_farkas_certificate(A, b, tol=tol)
        if farkas is None:
            return {"status": "CHECK_BLOCKED", "reason_code": "INFEASIBLE_STATUS_WITHOUT_REPLAYABLE_CERTIFICATE", "certificate": None}
        return {"status": "INCOMPATIBLE", "reason_code": "OBSERVED_LAW_CONFLICTS_WITH_MONOTONE_IV_MODEL",
                "solver_message": feasibility.message, "certificate": farkas}
    if not feasibility.success:
        return {"status": "CHECK_BLOCKED", "reason_code": "LATENT_MODEL_FEASIBILITY_NUMERICAL_FAILURE",
                "solver_status": int(feasibility.status), "solver_message": feasibility.message, "certificate": None}
    mean_y = lambda d, y: y
    mean_d = lambda d, y: d
    itt_y = _mean(p, 1, mean_y) - _mean(p, 0, mean_y)
    first_stage = _mean(p, 1, mean_d) - _mean(p, 0, mean_d)
    if first_stage < -tol:
        return {"status": "CHECK_BLOCKED", "reason_code": "FEASIBILITY_AND_FIRST_STAGE_NUMERIC_DISAGREEMENT",
                "itt_y": itt_y, "first_stage": first_stage, "certificate": None}
    if first_stage == 0:
        return {"status": "UNSUPPORTED", "reason_code": "NO_POSITIVE_COMPLIER_MASS_LATE_UNDEFINED",
                "itt_y": itt_y, "first_stage": first_stage, "certificate": None}
    if first_stage <= tol:
        return {"status": "CHECK_BLOCKED", "reason_code": "FIRST_STAGE_NUMERICALLY_AMBIGUOUS",
                "itt_y": itt_y, "first_stage": first_stage, "certificate": None}
    value = itt_y / first_stage
    if value < -1 - tol or value > 1 + tol:
        return {"status": "CHECK_BLOCKED", "reason_code": "FEASIBILITY_AND_WALD_NUMERIC_DISAGREEMENT",
                "itt_y": itt_y, "first_stage": first_stage, "late": value, "certificate": None}
    # Round-off at a mathematical endpoint only; never truncate an interior negative value.
    value = min(1.0, max(-1.0, float(value)))
    return {"status": "POINT", "estimand": "LATE_FOR_COMPLIERS", "late": value,
            "logical_range": [-1.0, 1.0], "itt_y": float(itt_y), "first_stage": float(first_stage),
            "compatibility_checked": True, "latent_type_count": 12,
            "certificate": {"kind": "MONOTONE_IV_FEASIBILITY", "types": [list(t) for t in types],
                            "witness": feasibility.x.tolist()},
            "scientific_assumptions_are_reviewed_not_empirically_proved": True}


def identify_late(observed, *, assumptions_accepted=False, tol=1e-9):
    from .iv_types import model_descriptor
    try:
        if isinstance(tol, bool) or not np.isfinite(tol) or not 0 < tol <= 1e-6:
            return dict(status='CHECK_BLOCKED', reason_code='INVALID_TOLERANCE', certificate=None)
        result = _identify_late(observed, assumptions_accepted=assumptions_accepted, tol=tol)
        result['model'] = model_descriptor(True, 'LATE')
        return result
    except (ValueError, TypeError, ArithmeticError, RuntimeError):
        return dict(status='CHECK_BLOCKED', reason_code='IV_INPUT_OR_SOLVER_FAILURE', certificate=None)
