"""Explicit hypothetical math fixtures; never a real scientific-review helper."""
from fractions import Fraction as F
from itertools import combinations, product
from cfm_id.mean_order_contract import MeanOrderProblem, ReviewedMeanOrder, VERSION, MODEL, SCOPE, input_digest


def make_problem(*, nodes=None, edges=None, quota=2, mode='BOTH', first=None,
                 second=None, weights=None, values=None, outcome_kind='binary', bounds=None):
    nodes = list('ABCD') if nodes is None else list(nodes)
    edges = list(combinations(nodes,2)) if edges is None else edges
    if values is None:
        # Independently stipulated compatible A4, all supported cells included.
        neighbors = {n:{v if u == n else u for u,v in edges if n in (u,v)} for n in nodes}
        cells = set()
        for z in product((0,1),repeat=len(nodes)):
            if sum(z) == quota:
                zz = dict(zip(nodes,z))
                cells.update((n,zz[n],int(2*sum(zz[j] for j in neighbors[n]) > len(neighbors[n]))) for n in nodes)
        values = [dict(node=n,own=a,exposure=e,value=str(F(3*a+2*e,5))) for n,a,e in sorted(cells)]
    modes = {n:mode for n in nodes} if type(mode) is str else mode
    return MeanOrderProblem(version=VERSION, model_scope=MODEL,node_order=nodes,
        undirected_edges=[list(e) for e in edges],graph_scope='KNOWN_FIXED_PRETREATMENT_SIMPLE_UNDIRECTED',
        design='D2_UNIFORM_FIXED_QUOTA',quota=quota,exposure='E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO',
        context='Synthetic fixed study context',treatment_definition='AI assistant assigned to this group',
        outcome_definition='Task completed on time',outcome_kind=outcome_kind,
        outcome_unit='Probability or declared numeric units',outcome_period='Same prespecified study day',
        order_direction='NONDECREASING_NUMERIC_OUTCOME_MEAN',order_scope=SCOPE,
        node_orders=[dict(node=n,mode=modes[n]) for n in nodes],
        randomization_claim='WHOLE_ASSIGNMENT_INDEPENDENT_OF_ALL_POTENTIAL_OUTCOMES_GIVEN_CONTEXT',
        consistency_claim='OBSERVED_OUTCOME_EQUALS_ASSIGNED_POTENTIAL_OUTCOME',
        moments_claim='FINITE_FIRST_MOMENTS',mean_sufficiency_scope=SCOPE,
        mean_sufficiency_claim='NODE_OWN_AND_E1_SIGNATURE_DETERMINES_CONDITIONAL_MEAN',
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',availability='EXACT_POPULATION_VALUE',
        values=values,a4_source='Independent hypothetical population-mean table',
        a4_provenance='Stipulated exact population information, not empirical sample means',
        bounds=[dict(node=n,lower='0',upper='1') for n in nodes] if bounds is None else bounds,
        bounds_kind='CONDITIONAL_MEAN',bounds_scope=SCOPE,
        bounds_provenance='Independently stipulated scientific mean ranges',
        first=[1]*len(nodes) if first is None else first,
        second=[0]*len(nodes) if second is None else second,
        weights=[str(F(1,len(nodes)))]*len(nodes) if weights is None else weights,
        operation='FIRST_MINUS_SECOND',
        scientific_provenance='Hypothetical base and order assumptions specified separately; not inferred from randomization')


def synthetic_review(problem):
    return ReviewedMeanOrder(version=VERSION,problem_sha256=input_digest(problem),
        reviewer='Independent synthetic fixture protocol',evidence='All original hypothetical coordinates and declarations stipulated for offline testing only',
        reviewed_target_direction_population=True,reviewed_complete_a4_and_no_unmodeled_constraints=True,
        reviewed_base_assumptions_and_all_arrangement_scope=True,reviewed_bounds_and_each_order_axis=True,
        synthetic_fixture=True)


if __name__ == '__main__':
    import json
    from cfm_id.mean_order import submit
    results = {}
    for mode in ('BOTH','OWN','NONE'):
        p = make_problem(mode=mode)
        results[mode] = submit(p,review=synthetic_review(p),synthetic_protocol_selected=True)
    print(json.dumps(results,ensure_ascii=False,indent=2))
