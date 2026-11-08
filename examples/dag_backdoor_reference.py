"""Frozen synthetic graphical examples. Review helper is for tests only."""
from cfm_id.dag_backdoor_contract import BackdoorProblem,PopulationLaw,BackdoorReview,VERSION,DECISIONS,digest
from cfm_id_bridge.scientific_binding import sha


def make_problem(nodes=None,edges=None,latent=None,adjustment=None):
    nodes=list(nodes or ['Z','X','Y']);latent=list(latent or [])
    edges=[['Z','X'],['Z','Y'],['X','Y']] if edges is None else edges
    observed=[v for v in nodes if v not in latent]
    return BackdoorProblem(version=VERSION,model='RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS',
        variable_domain='BINARY',nodes=nodes,observed=observed,latent=latent,edges=edges,
        graph_status='DECLARED',graph_source='Independent hypothetical causal diagram',
        materials_sha256=sha({'business':'Hypothetical training and completion', 'nodes':nodes,'edges':edges}),
        context='Single fixed synthetic study population',treatment='X',outcome='Y',adjustment=adjustment,
        information=PopulationLaw(source_id='synthetic_joint_law',source_sha256=sha({'source':'independently stipulated population law'}),
            variables=observed,availability='SYMBOLIC_POPULATION_LAW',strictly_positive_joint=True,
            provenance='Hypothetical full positive joint population law, no finite-sample estimates'),additional_restrictions=[])


def synthetic_review(problem):
    return BackdoorReview(version=VERSION,problem_sha256=digest(problem),
        reviewer='Independent frozen synthetic reference',evidence='All declared graph and law conditions stipulated only for offline research acceptance',
        authority='SYNTHETIC_TEST',decisions={k:'ACCEPTED' for k in DECISIONS})


def cases():
    # Expected adjustment sets and stop reasons are specified before execution.
    return [
      ('observed_confounder',make_problem(),'POINT',['Z']),
      ('unconfounded',make_problem(['X','Y'],[['X','Y']]),'POINT',[]),
      ('latent_path_blocked_observed',make_problem(['U','Z','X','Y'],[['U','X'],['U','Z'],['Z','Y'],['X','Y']],['U']),'POINT',['Z']),
      ('unobserved_confounder',make_problem(['U','X','Y'],[['U','X'],['U','Y'],['X','Y']],['U']),'UNSUPPORTED','NO_CLASSICAL_BACKDOOR_SET'),
      ('wrong_empty_adjustment',make_problem(adjustment=[]),'UNSUPPORTED','SPECIFIED_SET_FAILS_CLASSICAL_BACKDOOR'),
      ('collider_opened',make_problem(['X','Y','A','B','C'],[['A','X'],['A','C'],['B','C'],['B','Y'],['X','Y']],adjustment=['C']),'UNSUPPORTED','SPECIFIED_SET_FAILS_CLASSICAL_BACKDOOR'),
      ('collider_descendant_opened',make_problem(['X','Y','A','B','C','D'],[['A','X'],['A','C'],['B','C'],['B','Y'],['C','D'],['X','Y']],adjustment=['D']),'UNSUPPORTED','SPECIFIED_SET_FAILS_CLASSICAL_BACKDOOR'),
      ('post_treatment_mediator',make_problem(['X','M','Y'],[['X','M'],['M','Y']],adjustment=['M']),'UNSUPPORTED','ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT'),
      ('criterion_incomplete_y_parent',make_problem(['X','Y'],[['Y','X']]),'UNSUPPORTED','NO_CLASSICAL_BACKDOOR_SET'),
      ('frontdoor_graph_not_yet_supported',make_problem(['U','X','M','Y'],[['U','X'],['U','Y'],['X','M'],['M','Y']],['U']),'UNSUPPORTED','NO_CLASSICAL_BACKDOOR_SET'),
    ]
