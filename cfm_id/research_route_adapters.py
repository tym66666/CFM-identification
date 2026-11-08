"""Explicit adapters around separate route implementations; no default registry."""
from .research_route_workflow import RouteCapability


class DagBackdoorRoute:
    capability=RouteCapability('DAG_CLASSICAL_BACKDOOR','STATIC_CAUSAL_DAG',
        'SINGLE_INTERVENTIONAL_DISTRIBUTION','FULL_SYMBOLIC_OBSERVED_LAW',
        'CLASSICAL_BACKDOOR_GRAPH_AND_FUNCTIONAL',
        'At most 8 binary variables including declared latents; strict observed positivity declared and reviewed; research only.')
    def prepare(self,problem):
        from .dag_backdoor import prepare
        return prepare(problem)
    def submit(self,problem,review):
        from .dag_backdoor import submit
        return submit(problem,review=review,research_protocol_selected=True)
    def certificate(self,result):return result.get('certificate')
    def replay(self,problem,certificate):
        from .dag_backdoor_verify import replay
        return replay(certificate,problem=problem)
    def claim(self,certificate):
        return dict(kind='POINT',representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
            target=certificate['target'],functional=certificate['functional'],numeric_value=None)
    def verify_claim(self,certificate,claim):
        return (set(claim)=={'kind','representation','target','functional','numeric_value'}
            and claim['kind']==certificate['status']=='POINT'
            and claim['representation']=='OBSERVED_DISTRIBUTION_FUNCTIONAL'
            and claim['target']==certificate['target'] and claim['functional']==certificate['functional']
            and claim['numeric_value'] is None)


class MeanOrderRoute:
    capability=RouteCapability('MEAN_ORDER_D2_E1','FIXED_NETWORK_MEAN_ORDER',
        'FIXED_POLICY_MEAN_CONTRAST','EXACT_LISTED_SIGNATURE_MEANS',
        'PRIMAL_DUAL_AND_ENDPOINTS_OR_FARKAS',
        'Existing D2/E1 finite contract and separate synthetic review; no wider model or production admission.')
    def prepare(self,problem):
        from .mean_order import prepare
        return prepare(problem)
    def submit(self,problem,review):
        from .mean_order import submit
        return submit(problem,review=review,synthetic_protocol_selected=True)
    def certificate(self,result):return result.get('bounded_result') or result.get('incompatibility_certificate')
    def replay(self,problem,certificate):
        from .mean_order_verify import replay
        return replay(certificate,problem=problem)
    def claim(self,certificate):
        if certificate['status']=='INCOMPATIBLE':
            return dict(kind='INCOMPATIBLE',representation='CONSTRAINT_CONTRADICTION',identified_set=None)
        return dict(kind=certificate['status'],representation='EXACT_IDENTIFIED_INTERVAL',
            interval=[certificate['lower'],certificate['upper']],sharp=certificate['sharp'])
    def verify_claim(self,certificate,claim):
        if certificate['status']=='INCOMPATIBLE':
            return claim==dict(kind='INCOMPATIBLE',representation='CONSTRAINT_CONTRADICTION',identified_set=None)
        return (set(claim)=={'kind','representation','interval','sharp'} and claim['kind']==certificate['status']
            and claim['representation']=='EXACT_IDENTIFIED_INTERVAL'
            and claim['interval']==[certificate['lower'],certificate['upper']]
            and claim['sharp'] is True and certificate['sharp'] is True)


def capabilities():
    """Read-only descriptions, not automatic applicability or approval."""
    from .research_route_catalog import registrations
    return tuple(r.capability for r in registrations())
