"""Finite binary-IV potential-response types and observed-law constraints."""
from __future__ import annotations
from itertools import product
from typing import NamedTuple
import numpy as np

class IVType(NamedTuple):
    d0: int
    d1: int
    y0: int
    y1: int


def enumerate_types(monotonicity: bool = False) -> list[IVType]:
    """Enumerate 16 unrestricted or 12 monotone (D(1)>=D(0)) types."""
    if type(monotonicity) is not bool:
        raise TypeError("MONOTONICITY_MUST_BE_BOOLEAN")
    return [IVType(*v) for v in product((0, 1), repeat=4)
            if not monotonicity or v[1] >= v[0]]


def observed_constraint_system(observed, *, monotonicity=False):
    """Return A,b,c for P(D,Y|Z)=A p, with a common latent-type law p."""
    from .iv_contract import validate_observed
    p = validate_observed(observed)
    types = enumerate_types(monotonicity)
    rows, rhs = [], []
    for z in (0, 1):
        for d in (0, 1):
            for y in (0, 1):
                rows.append([float((t.d0 if z == 0 else t.d1) == d and
                                   (t.y0 if d == 0 else t.y1) == y) for t in types])
                rhs.append(p[z, d, y])
    A, b = np.asarray(rows, dtype=float), np.asarray(rhs, dtype=float)
    c = np.asarray([t.y1 - t.y0 for t in types], dtype=float)
    return types, A, b, c


def find_farkas_certificate(A, b, *, tol=1e-9):
    """Find normalized Farkas multiplier proving {p>=0: A p=b} is empty."""
    from scipy.optimize import linprog
    A=np.asarray(A,dtype=float); b=np.asarray(b,dtype=float)
    m=A.shape[0]
    # lambda=lambda_plus-lambda_minus, ||lambda||_1 <= 1.
    objective=np.concatenate([b,-b])
    inequalities=np.vstack([np.hstack([-A.T,A.T]),np.ones((1,2*m))])
    rhs=np.concatenate([np.zeros(A.shape[1]),[1.0]])
    fit=linprog(objective,A_ub=inequalities,b_ub=rhs,bounds=(0,None),method='highs')
    if not fit.success or fit.fun >= -tol:return None
    lam=fit.x[:m]-fit.x[m:]
    if np.min(A.T@lam)<-tol or float(b@lam)>=-tol:return None
    return {'kind':'FARKAS_INCOMPATIBILITY','lambda':lam.tolist(),
            'normalization_l1':float(np.sum(np.abs(lam))),
            'contradiction_margin':float(-(b@lam))}


def model_descriptor(monotonicity, target):
    return dict(target=target, type_coordinates=['D(0)','D(1)','Y(0)','Y(1)'],
        types=[list(t) for t in enumerate_types(monotonicity)], monotonicity=monotonicity,
        observed_coordinates=[[z,d,y] for z in (0,1) for d in (0,1) for y in (0,1)],
        mapping='D=D(Z);Y=Y(D);common_type_law_independent_of_Z',
        effect_direction='Y(1)-Y(0)')
