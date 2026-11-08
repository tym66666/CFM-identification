"""Frozen synthetic single-variable front-door cases; never real approval."""
from cfm_id.dag_frontdoor_contract import FrontdoorProblem, FrontdoorReview, VERSION, DECISIONS, digest
from cfm_id_bridge.scientific_binding import sha


def make_problem(nodes=None, edges=None, latent=None, frontdoor_variable=None):
    nodes = list(nodes) if nodes is not None else ['U', 'X', 'M', 'Y']
    edges = [list(e) for e in edges] if edges is not None else [['U','X'],['U','Y'],['X','M'],['M','Y']]
    latent = list(latent) if latent is not None else (['U'] if 'U' in nodes else [])
    observed = [n for n in nodes if n not in latent]
    return FrontdoorProblem(
        version=VERSION, model='RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS',
        variable_domain='BINARY', nodes=nodes, observed=observed, latent=latent, edges=edges,
        graph_status='DECLARED', graph_source='Independent hypothetical causal diagram',
        materials_sha256=sha(dict(nodes=nodes, edges=edges)),
        context='Fixed hypothetical population and intervention scope',
        treatment='X', outcome='Y', frontdoor_variable=frontdoor_variable,
        information=dict(source_id='synthetic_population_joint',
                         source_sha256=sha({'source':'hypothetical population law'}),
                         variables=observed, availability='SYMBOLIC_POPULATION_LAW',
                         strictly_positive_joint=True,
                         provenance='Hypothetical complete observed population law; not finite-sample estimates'),
        additional_restrictions=[])


def synthetic_review(problem):
    return FrontdoorReview(version=VERSION, problem_sha256=digest(problem),
        reviewer='Independent frozen synthetic reference',
        evidence='Graph and scientific assumptions stipulated only for offline synthetic testing',
        authority='SYNTHETIC_TEST', decisions={k:'ACCEPTED' for k in DECISIONS})


def cases():
    classic = [['U','X'],['U','Y'],['X','M'],['M','Y']]
    bad = 'SPECIFIED_VARIABLE_FAILS_FRONTDOOR'
    return [
        ('classic_latent_confounding_search', make_problem(), 'POINT', 'M'),
        ('classic_specified', make_problem(frontdoor_variable='M'), 'POINT', 'M'),
        ('observed_chain', make_problem(['X','M','Y'],[['X','M'],['M','Y']],[]), 'POINT', 'M'),
        ('nonroot_latent', make_problem(['A','U','X','M','Y'],[['A','U'],*classic],['U']), 'POINT', 'M'),
        ('extra_observed_variable', make_problem(['U','X','M','Y','W'],[*classic,['X','W']],['U'],'M'), 'POINT', 'M'),
        ('direct_path_bypasses_m', make_problem(edges=[*classic,['X','Y']],frontdoor_variable='M'), 'UNSUPPORTED', bad),
        ('x_m_confounding', make_problem(edges=[['U','X'],['U','M'],['X','M'],['M','Y']],frontdoor_variable='M'), 'UNSUPPORTED', bad),
        ('m_y_confounding', make_problem(['U','V','X','M','Y'],[*classic,['V','M'],['V','Y']],['U','V'],'M'), 'UNSUPPORTED', bad),
        ('collider_closed', make_problem(['X','M','Y','C'],[['X','M'],['M','Y'],['X','C'],['M','C']],[],'M'), 'POINT', 'M'),
        ('collider_descendant_opened_by_x', make_problem(
            ['X','M','Y','A','B','C'],[['A','M'],['A','C'],['B','C'],['B','Y'],['C','X']],['A','B'],'M'), 'UNSUPPORTED', bad),
        ('collider_x_opened', make_problem(['X','M','Y'],[['M','X'],['Y','X']],[],'M'), 'UNSUPPORTED', bad),
        ('no_causal_path_vacuous', make_problem(['X','M','Y'],[],[],'M'), 'POINT', 'M'),
        ('reverse_mediator_edge', make_problem(['X','M','Y'],[['M','X'],['M','Y']],[],'M'), 'UNSUPPORTED', bad),
        ('wrong_specified_while_m_works', make_problem(['U','X','M','Y','W'],[*classic,['X','W']],['U'],'W'), 'UNSUPPORTED', bad),
        ('two_valid_singletons', make_problem(['U','X','M','N','Y'],
            [['U','X'],['U','Y'],['X','M'],['M','N'],['N','Y']],['U']), 'POINT', 'M'),
        ('no_candidate', make_problem(['X','Y'],[['X','Y']],[]), 'UNSUPPORTED', 'NO_SINGLE_VARIABLE_FRONTDOOR'),
        ('no_valid_singleton', make_problem(['X','M','Y'],[['X','Y']],[]), 'UNSUPPORTED', 'NO_SINGLE_VARIABLE_FRONTDOOR'),
    ]

