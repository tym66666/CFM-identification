"""Independent replay of the binary-IV Wald/LATE claim."""
from __future__ import annotations
from .iv_contract import validate_observed
from .iv_types import enumerate_types
import numpy as np


def verify_late_result(observed,result,*,tol=1e-8):
    if type(result) is not dict:
        return {'valid':False,'reason_code':'MALFORMED_LATE_RESULT'}
    try:
        from .iv_types import model_descriptor
        if not np.isfinite(tol) or not 0 < tol <= 1e-6:
            return {'valid':False,'reason_code':'INVALID_TOLERANCE'}
        if result.get('model') != model_descriptor(True, 'LATE'):
            return {'valid':False,'reason_code':'MODEL_MAPPING_MISMATCH'}
        p=validate_observed(observed); types=enumerate_types(True)
        A=[]; b=[]
        for z in (0,1):
            for d in (0,1):
                for y in (0,1):
                    A.append([float((t.d0 if z==0 else t.d1)==d and (t.y0 if d==0 else t.y1)==y) for t in types])
                    b.append(p[z,d,y])
        A=np.asarray(A);b=np.asarray(b)
        if result.get('status')=='INCOMPATIBLE':
            cert=result.get('certificate') or {}
            lam=np.asarray(cert.get('lambda'),dtype=float)
            valid=(cert.get('kind')=='FARKAS_INCOMPATIBILITY' and lam.shape==(A.shape[0],)
                and np.all(np.isfinite(lam)) and np.min(A.T@lam)>=-tol
                and float(b@lam)<-tol and np.sum(np.abs(lam))<=1+tol
                and abs(float(cert.get('normalization_l1',float('nan')))-float(np.sum(np.abs(lam))))<=tol
                and abs(float(cert.get('contradiction_margin',float('nan'))) + float(b@lam))<=tol)
            return {'valid':bool(valid),'reason_code':None if valid else 'FARKAS_CERTIFICATE_REPLAY_FAILED'}
        if result.get('status')!='POINT':
            return {'valid':False,'reason_code':'NO_LATE_POINT_TO_VERIFY'}
        cert = result.get('certificate') or {}
        x = np.asarray(cert.get('witness'), dtype=float)
        if (cert.get('kind') != 'MONOTONE_IV_FEASIBILITY'
                or cert.get('types') != [list(t) for t in types]
                or result.get('estimand') != 'LATE_FOR_COMPLIERS'
                or result.get('latent_type_count') != 12
                or x.shape != (12,) or not np.all(np.isfinite(x))
                or np.min(x) < -tol or abs(float(x.sum())-1) > tol
                or np.max(np.abs(A@x-b)) > tol):
            return {'valid':False,'reason_code':'MONOTONE_LATENT_WITNESS_INVALID'}
        ey=lambda z:sum(y*p[z,d,y] for d in (0,1) for y in (0,1))
        ed=lambda z:sum(d*p[z,d,y] for d in (0,1) for y in (0,1))
        itt=ey(1)-ey(0); fs=ed(1)-ed(0)
        if fs<=tol:return {'valid':False,'reason_code':'POSITIVE_FIRST_STAGE_REQUIRED'}
        value=itt/fs
        valid=(-1-tol<=value<=1+tol and abs(value-float(result.get('late',float('nan'))))<=tol
               and abs(itt-float(result.get('itt_y',float('nan'))))<=tol
               and abs(fs-float(result.get('first_stage',float('nan'))))<=tol
               and result.get('compatibility_checked') is True
               and result.get('logical_range')==[-1.0,1.0])
        return {'valid':bool(valid),'reason_code':None if valid else 'LATE_CLAIM_REPLAY_FAILED',
                'checks':{'monotone_model_feasible':True,'wald_ratio_matches':abs(value-float(result.get('late',float('nan'))))<=tol,
                          'binary_outcome_range':-1-tol<=value<=1+tol}}
    except (ValueError,TypeError,KeyError,AttributeError):return {'valid':False,'reason_code':'INVALID_LATE_INPUT_OR_RESULT'}
