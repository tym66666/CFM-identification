"""Thin adapter; graph proof and nested functional remain front-door-specific."""
from .research_route_workflow import RouteCapability


class DagFrontdoorRoute:
    capability = RouteCapability(
        'DAG_CLASSICAL_FRONTDOOR', 'STATIC_CAUSAL_DAG',
        'SINGLE_INTERVENTIONAL_DISTRIBUTION', 'FULL_SYMBOLIC_OBSERVED_LAW',
        'SINGLETON_FRONTDOOR_GRAPH_AND_NESTED_FUNCTIONAL',
        'At most eight binary nodes incl. explicit latents; one observed front-door variable; '
        'reviewed positive observed law; sufficient POINT only; research only.')

    def prepare(self, problem):
        from .dag_frontdoor import prepare
        return prepare(problem)

    def submit(self, problem, review):
        from .dag_frontdoor import submit
        return submit(problem, review=review, research_protocol_selected=True)

    def certificate(self, result):
        return result.get('certificate')

    def replay(self, problem, certificate):
        from .dag_frontdoor_verify import replay
        return replay(certificate, problem=problem)

    def claim(self, certificate):
        return dict(kind='POINT', representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
                    target=certificate['target'], functional=certificate['functional'], numeric_value=None)

    def verify_claim(self, certificate, claim):
        from cfm_id_bridge.scientific_binding import sha
        expected = dict(kind='POINT', representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
                        target=certificate['target'], functional=certificate['functional'], numeric_value=None)
        return certificate['status'] == 'POINT' and sha(claim) == sha(expected)

