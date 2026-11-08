"""Sufficient singleton front-door certificates; no general ID algorithm."""
from .dag_frontdoor_contract import validate, digest, VERSION, THEOREM, CLAIM_SCOPE, Unavailable
from .dag_backdoor_solver import moral_separation
from cfm_id_bridge.scientific_binding import sha


class CriterionFailure(Unavailable):
    def __init__(self, reason, diagnostic):
        self.diagnostic = diagnostic
        super().__init__('UNSUPPORTED', reason)


def check_candidate(problem, mediator):
    p = problem
    x, y = p.treatment, p.outcome
    reached, pending = {x}, [x]
    while pending:
        node = pending.pop()
        for a, b in p.edges:
            if a == node and b != mediator and b not in reached:
                reached.add(b)
                pending.append(b)
    graph2 = [(a, b) for a, b in p.edges if a != x]
    graph3 = [(a, b) for a, b in p.edges if a != mediator]
    fd2, trace2 = moral_separation(p.nodes, graph2, x, mediator, [])
    fd3, trace3 = moral_separation(p.nodes, graph3, mediator, y, [x])
    return dict(FD1=y not in reached, FD2=fd2, FD3=fd3), dict(
        FD1=dict(removed_node=mediator, reachable_without_node=sorted(reached)),
        FD2=dict(removed_outgoing_from=x, **trace2),
        FD3=dict(removed_outgoing_from=mediator, **trace3),
    )


def functional(problem, mediator):
    x, y = problem.treatment, problem.outcome
    def coordinate(variable, role):
        return dict(variable=variable, value_role=role)
    return dict(
        operation='CLASSICAL_FRONTDOOR', source_id=problem.information.source_id,
        free_values=dict(
            intervention_value=dict(variable=x, domain=[0, 1]),
            outcome_value=dict(variable=y, domain=[0, 1])),
        expression=dict(operation='SUM',
            bind=dict(variable=mediator, role='mediator_value', domain=[0, 1]),
            summand=dict(operation='PRODUCT', factors=[
                dict(operation='CONDITIONAL_PROBABILITY',
                     outcomes=[coordinate(mediator, 'mediator_value')],
                     given=[coordinate(x, 'intervention_value')]),
                dict(operation='SUM',
                     bind=dict(variable=x, role='treatment_marginal_value', domain=[0, 1]),
                     summand=dict(operation='PRODUCT', factors=[
                         dict(operation='CONDITIONAL_PROBABILITY',
                              outcomes=[coordinate(y, 'outcome_value')],
                              given=[coordinate(x, 'treatment_marginal_value'),
                                     coordinate(mediator, 'mediator_value')]),
                         dict(operation='PROBABILITY',
                              outcomes=[coordinate(x, 'treatment_marginal_value')])
                     ]))
            ]))
    )


def solve(problem):
    p = validate(problem)
    candidates = ([p.frontdoor_variable] if p.frontdoor_variable is not None else
                  sorted(set(p.observed) - {p.treatment, p.outcome}))
    attempts = []
    for mediator in candidates:
        conditions, trace = check_candidate(p, mediator)
        attempts.append(dict(frontdoor_variable=mediator, conditions=conditions))
        if not all(conditions.values()):
            continue
        cert = dict(
            version=VERSION, theorem=THEOREM, claim_scope=CLAIM_SCOPE, status='POINT',
            problem_sha256=digest(p), materials_sha256=p.materials_sha256,
            information_sha256=sha(p.information),
            target=dict(kind='INTERVENTIONAL_DISTRIBUTION', treatment=p.treatment,
                        outcome=p.outcome, context=p.context),
            frontdoor_variable=mediator,
            selection=dict(mode='SPECIFIED' if p.frontdoor_variable is not None else 'SEARCH_SINGLETON',
                           requested=p.frontdoor_variable),
            conditions=conditions, graphical_trace=trace, functional=functional(p, mediator),
            positivity='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT', numeric_value=None,
        )
        cert['certificate_sha256'] = sha(cert)
        return cert
    raise CriterionFailure(
        'SPECIFIED_VARIABLE_FAILS_FRONTDOOR' if p.frontdoor_variable is not None
        else 'NO_SINGLE_VARIABLE_FRONTDOOR',
        dict(candidate_checks=attempts, general_nonidentification_proved=False))

