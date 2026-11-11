"""Independent replay of binary-IV ATE primal and dual endpoint certificates.

This module deliberately does not import iv_ate_solver or its LP builder.
"""
from __future__ import annotations
import numpy as np
from .iv_contract import validate_observed, IVInputError
from .iv_types import enumerate_types


def _verifier_system(observed, monotonicity):
    p = validate_observed(observed)
    types = enumerate_types(monotonicity)
    rows=[]; rhs=[]
    for z in (0,1):
        for d in (0,1):
            for y in (0,1):
                rows.append([float((t.d0 if z==0 else t.d1)==d and
                                   (t.y0 if d==0 else t.y1)==y) for t in types])
                rhs.append(p[z,d,y])
    return types, np.asarray(rows,dtype=float), np.asarray(rhs,dtype=float), np.asarray([t.y1-t.y0 for t in types],dtype=float)


def verify_ate_result(observed, result, *, monotonicity: bool = False, tol: float = 1e-7) -> dict:
    if type(result) is not dict:
        return {"valid": False, "reason_code": "MALFORMED_ATE_RESULT"}
    try:
        from .iv_types import model_descriptor
        if not np.isfinite(tol) or not 0 < tol <= 1e-6:
            return {'valid':False,'reason_code':'INVALID_TOLERANCE'}
        if result.get('model') != model_descriptor(monotonicity, 'ATE'):
            return {'valid':False,'reason_code':'MODEL_MAPPING_MISMATCH'}
        types,A,b,c=_verifier_system(observed,monotonicity)
        if result.get("status")=="INCOMPATIBLE":
            cert=result.get("certificate") or {}; lam=np.asarray(cert.get("lambda"),dtype=float)
            valid=(cert.get("kind")=="FARKAS_INCOMPATIBILITY" and lam.shape==(A.shape[0],)
                and np.all(np.isfinite(lam)) and np.min(A.T@lam)>=-tol
                and float(b@lam)<-tol and np.sum(np.abs(lam))<=1+tol
                and abs(float(cert.get('normalization_l1',float('nan')))-float(np.sum(np.abs(lam))))<=tol
                and abs(float(cert.get("contradiction_margin",float("nan")))+float(b@lam))<=tol)
            return {"valid":bool(valid),"reason_code":None if valid else "FARKAS_CERTIFICATE_REPLAY_FAILED"}
        if result.get("status") != "SHARP_BOUNDS":
            return {"valid":False,"reason_code":"NO_SUCCESSFUL_ATE_CERTIFICATE"}
        if result.get('estimand') != 'ATE=E[Y(1)-Y(0)]':
            return {'valid':False,'reason_code':'TARGET_MISMATCH'}
        if type(monotonicity) is not bool or result.get("monotonicity") is not monotonicity:
            return {"valid":False,"reason_code":"MODEL_MAPPING_MISMATCH"}
        if result.get("target") != {"kind":"ATE","outcome_domain":"BINARY","treatment_domain":"BINARY"}:
            return {"valid":False,"reason_code":"TARGET_MISMATCH"}
        if result.get("certificate") != {"kind":"PRIMAL_DUAL_ENDPOINT_CERTIFICATE","independent_replay_required":True}:
            return {"valid":False,"reason_code":"TARGET_MISMATCH"}
        if result.get("type_count") != len(types) or result.get("types") != [list(t) for t in types]:
            return {"valid":False,"reason_code":"POTENTIAL_TYPE_COORDINATE_MISMATCH"}
        bounds=np.asarray(result["bounds"],dtype=float)
        if bounds.shape!=(2,) or not np.all(np.isfinite(bounds)) or bounds[0]>bounds[1]+tol:
            return {"valid":False,"reason_code":"INVALID_ATE_BOUNDS"}
    except (KeyError,TypeError,ValueError,IVInputError) as exc:
        return {"valid":False,"reason_code":"INVALID_CERTIFICATE_OR_INPUT","detail":str(exc)}
    checks={}
    for label,pk,dk,endpoint,sense in (("lower","lower_witness","lower_dual",bounds[0],"min"),
                                        ("upper","upper_witness","upper_dual",bounds[1],"max")):
        try:
            x=np.asarray(result[pk],dtype=float); lam=np.asarray(result[dk],dtype=float)
        except (KeyError,TypeError,ValueError):
            return {"valid":False,"reason_code":f"MISSING_{label.upper()}_CERTIFICATE"}
        if x.shape!=(len(types),) or lam.shape!=(A.shape[0],) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(lam)):
            return {"valid":False,"reason_code":f"MALFORMED_{label.upper()}_CERTIFICATE"}
        checks[f"{label}_primal_nonnegative"]=bool(np.min(x)>=-tol)
        checks[f"{label}_observed_constraints"]=bool(np.max(np.abs(A@x-b))<=tol)
        checks[f"{label}_normalization"]=bool(abs(float(x.sum())-1.0)<=tol)
        primal=float(c@x)
        checks[f"{label}_objective_matches_target"]=bool(abs(primal-float(endpoint))<=tol)
        try:
            checks[f"{label}_reported_objective"]=bool(abs(primal-float(result[label+'_objective']))<=tol)
        except (KeyError, TypeError, ValueError):
            return {'valid':False,'reason_code':'MALFORMED_REPORTED_OBJECTIVE'}
        lhs=A.T@lam; dual=float(b@lam)
        checks[f"{label}_dual_feasible"]=bool(np.max(lhs-c)<=tol) if sense=="min" else bool(np.min(lhs-c)>=-tol)
        checks[f"{label}_strong_duality"]=bool(abs(primal-dual)<=tol)
    return {"valid":all(checks.values()),"checks":checks,
            "reason_code":None if all(checks.values()) else "CERTIFICATE_REPLAY_FAILED",
            "scope":"Replays the declared binary response-type LP; does not prove scientific assumptions."}
