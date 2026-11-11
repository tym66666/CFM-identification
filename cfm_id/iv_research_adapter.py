"""Formal research-route adapter for the reviewed binary-IV contract."""
from .research_route_workflow import RouteCapability

class BinaryIVRoute:
    capability=RouteCapability('BINARY_IV_LATE_ATE','BINARY_INSTRUMENTAL_VARIABLE',
        'LATE_OR_ATE','COMPLETE_P_DY_GIVEN_Z_TABLE',
        'MONOTONE_LATENT_TYPE_FEASIBILITY_AND_PRIMAL_DUAL_ENDPOINTS',
        'Binary Z/D/Y only; complete conditional population law; separate source-reading and scientific reviews; research only.')
    def prepare(self,problem):
        from .iv_research import prepare
        return prepare(problem)
    def submit(self,problem,review):
        from .iv_research import submit
        return submit(problem,review=review,research_protocol_selected=True)
    def certificate(self,result):return result.get('certificate')
    def replay(self,problem,certificate):
        from .iv_route_contract import validate, digest
        from .iv_late_verify import verify_late_result
        from .iv_ate_verify import verify_ate_result
        p=validate(problem)
        if type(certificate) is not dict or certificate.get('problem_sha256') != digest(p): return False
        if p.target=='LATE':return verify_late_result(p.observed(),certificate).get('valid') is True
        return verify_ate_result(p.observed(),certificate,monotonicity=p.monotonicity).get('valid') is True
    def claim(self,certificate):
        if certificate.get('status')=='INCOMPATIBLE':
            return dict(kind='INCOMPATIBLE',representation='FARKAS_CONSTRAINT_CONTRADICTION',reason_code=certificate.get('reason_code'))
        if certificate.get('estimand')=='LATE_FOR_COMPLIERS':
            return dict(kind='POINT',estimand='LATE_FOR_COMPLIERS',value=certificate['late'],logical_range=[-1.0,1.0])
        kind='POINT' if certificate['bounds'][1]==certificate['bounds'][0] else 'PARTIAL'
        return dict(kind=kind,representation='SHARP_ATE_BOUNDS',estimand='ATE',interval=certificate['bounds'],sharp=True)
    def verify_claim(self,certificate,claim):
        if certificate.get('status')=='INCOMPATIBLE':
            expected=dict(kind='INCOMPATIBLE',representation='FARKAS_CONSTRAINT_CONTRADICTION',reason_code=certificate.get('reason_code'))
        elif certificate.get('estimand')=='LATE_FOR_COMPLIERS':
            expected=dict(kind='POINT',estimand='LATE_FOR_COMPLIERS',value=certificate.get('late'),logical_range=[-1.0,1.0])
        else:
            bounds=certificate.get('bounds')
            if type(bounds) is not list or len(bounds)!=2:return False
            kind='POINT' if bounds[1]==bounds[0] else 'PARTIAL'
            expected=dict(kind=kind,representation='SHARP_ATE_BOUNDS',estimand='ATE',interval=bounds,sharp=True)
        return claim==expected
