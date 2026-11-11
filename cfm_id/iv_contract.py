"""Strict observed-data contract for the binary instrumental-variable model."""
from __future__ import annotations
from typing import Mapping, Tuple
import math
Cell = Tuple[int, int, int]

class IVInputError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(code if not detail else f"{code}: {detail}")


def validate_observed(observed: Mapping[Cell, float], tol: float = 1e-8) -> dict[Cell, float]:
    """Validate all eight conditional cells P(D=d,Y=y | Z=z).

    This contract does not validate instrument randomization, exclusion, or
    monotonicity; those are separate scientific declarations and reviews.
    """
    if not isinstance(observed, Mapping):
        raise IVInputError("OBSERVED_LAW_MAPPING_REQUIRED")
    if not math.isfinite(tol) or not 0 < tol <= 1e-6:
        raise IVInputError("INVALID_TOLERANCE")
    expected = {(z, d, y) for z in (0, 1) for d in (0, 1) for y in (0, 1)}
    try:
        keys = set(observed)
    except TypeError as exc:
        raise IVInputError("INVALID_OBSERVED_CELL_KEYS") from exc
    if keys != expected:
        missing, extra = expected - keys, keys - expected
        raise IVInputError("INCOMPLETE_OR_EXTRA_OBSERVED_CELLS", f"missing={sorted(missing)}, extra={sorted(extra)}")
    vals = {}
    for key, value in observed.items():
        if type(key) is not tuple or len(key) != 3 or any(type(v) is not int or v not in (0, 1) for v in key):
            raise IVInputError("BINARY_CELL_COORDINATES_REQUIRED", repr(key))
        if isinstance(value, bool): raise IVInputError("NUMERIC_PROBABILITY_REQUIRED")
        try: x = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise IVInputError("NUMERIC_PROBABILITY_REQUIRED", repr(key)) from exc
        if not math.isfinite(x) or x < -tol or x > 1 + tol:
            raise IVInputError("PROBABILITY_OUT_OF_RANGE", repr(key))
        vals[key] = min(1.0, max(0.0, x))
    for z in (0, 1):
        total = sum(vals[z, d, y] for d in (0, 1) for y in (0, 1))
        if abs(total - 1.0) > tol:
            raise IVInputError("CONDITIONAL_LAW_NOT_NORMALIZED", f"Z={z}, sum={total:.12g}")
    return vals
