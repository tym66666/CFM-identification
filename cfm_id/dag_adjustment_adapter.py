"""Opt-in adapter for the existing research protocol; not a default registry."""
from .research_route_workflow import RouteCapability

class DagAdjustmentRoute:
    capability=RouteCapability('DAG_ADJUSTMENT','STATIC_CAUSAL_DAG',
        'SINGLE_INTERVENTIONAL_DISTRIBUTION','FULL_SYMBOLIC_OBSERVED_LAW',
        'DAG_ADJUSTMENT_GRAPH_AND_FUNCTIONAL',
        'At most eight binary nodes incl. explicit latents; reviewed positive observed law; sufficient POINT only; research only.')
    def prepare(self,problem):
        from .dag_adjustment import prepare
        return prepare(problem)
    def submit(self,problem,review):
        from .dag_adjustment import submit
        return submit(problem,review=review,research_protocol_selected=True)
    def certificate(self,result):return result.get('certificate')
    def replay(self,problem,certificate):
        from .dag_adjustment_verify import replay
        return replay(certificate,problem=problem)
    def claim(self,certificate):
        return dict(kind='POINT',representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
            target=certificate['target'],functional=certificate['functional'],numeric_value=None)
    def verify_claim(self,certificate,claim):
        from cfm_id_bridge.scientific_binding import sha
        expected=dict(kind='POINT',representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
            target=certificate['target'],functional=certificate['functional'],numeric_value=None)
        return certificate['status']=='POINT' and sha(claim)==sha(expected)

