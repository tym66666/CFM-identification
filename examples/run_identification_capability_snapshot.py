"""Machine-readable finite capability snapshot from the v2.8 route catalog.

Counts are components/implemented contracts, NOT realized business coverage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pfn_pipeline.identification_observational_nodewise_adjustment import implemented_assumption_catalog_v28
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import (
    GROUP_E1,GROUP_E2,GROUP_E3,GROUP_E4,GROUP_E5,
)

_DESIGNS = [
    ('D1','nodewise heterogeneous independent Bernoulli'),
    ('D2','complete randomization with fixed treated quota'),
    ('D3','two pretreatment groups, separate fixed quotas'),
    ('D4','pretreatment clusters, independently assigned Bernoulli treatment'),
    ('D5','3–64 pretreatment groups, separately fixed treated quotas'),
    ('D6','known two-stage quota-profile mixture; extra stage-one A5 required'),
]
_EXPOSURES = [
    ('E1',GROUP_E1,'strict treated-neighbor majority'),
    ('E2',GROUP_E2,'three treated-neighbor proportion levels'),
    ('E3',GROUP_E3,'strict majority of declared core collaborators'),
    ('E4',GROUP_E4,'exact treated-neighbor count'),
    ('E5',GROUP_E5,'any treated neighbor'),
]


def generate():
    catalog=implemented_assumption_catalog_v28()
    routes=catalog['route_ids']
    groups={
        'R1a': [r for r in routes if r.startswith('R1A_')],
        'R1b': [r for r in routes if r.startswith('R1B_')],
        'R2': [r for r in routes if r.startswith('R2_')],
        'R3': [r for r in routes if r.startswith('R3_')],
    }
    assert sum(map(len,groups.values()))==len(routes)==10
    return {
        'snapshot_version':'v2.8-Postrelease-P1-Correlated-Observational-A4',
        'classification_source':catalog['contract'],
        'scientific_assumptions_verified_in_real_world':False,
        'coverage_denominator':'IMPLEMENTED_FINITE_CONTRACTS_NOT_REAL_MARKET_QUERIES',
        'identification_mechanism_count':len(groups),
        'route_count':len(routes), 'routes_by_mechanism':groups,
        'documented_premise_name_count':len(catalog['assumptions']),
        'assumption_names':[r['name'] for r in catalog['assumptions']],
        'A4_design_premise_name_count':sum(a['layer']=='A4_DESIGN' for a in catalog['assumptions']),
        'experimental_assignment_count':len(_DESIGNS),
        'experimental_assignments':[dict(id=d,name=n) for d,n in _DESIGNS],
        'exposure_mapping_count':len(_EXPOSURES),
        'exposures':[dict(id=e,code=group,meaning=meaning) for e,group,meaning in _EXPOSURES],
        'conditional_DxE_combination_count':len(_DESIGNS)*len(_EXPOSURES),
        'observational_population_A4_source_kinds':[
            'FINITE_FULL_ASSIGNMENT_POPULATION_LAW (R3 fixed W, <=12 nodes)',
            'NODEWISE_INDEPENDENT_BERNOULLI_CONDITIONAL_LAW',
            'FINITE_MIXTURE_OF_NODEWISE_BERNOULLI (new v2.8 P1)',
            'SHARED_PRETREATMENT_STRATA_WITH_BERNOULLI_WITHIN_STRATUM',
            'NODEWISE_PRETREATMENT_BINARY_COVARIATE_PROFILE_LAW',
        ],
        'A1_target_classes':[
            'q-standardized node-arm population mean',
            'q-standardized Direct/Spillover/Total and preweighted aggregation',
            'fixed full-assignment policy value',
            'finite certified full-policy mixture',
            'p_obs-standardized node-arm contrasts',
            'shared-pretreatment-stratum adjusted exposure potential-outcome contrast',
            'nodewise pretreatment-covariate adjusted exposure potential-outcome contrast',
        ],
        'A2_A3_scope':'known fixed pretreatment simple undirected networks; one time; binary treatment; finite mean outcome targets',
        'verified_causal_parameter_values':None,
        'automated_numerical_estimator_for_new_R3':'NO_ADAPTER',
        'excluded_research_scope':['A0 owned by another developer','R4 identified sets','R5 encouragement/IV','general DAG/unknown dynamic networks'],
        'caveat':'Counts are finite implemented route and design types; cannot be interpreted as success rate over real causal queries.',
    }


def write(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    path=outdir/'CFM_ID_v2_8_P1_Verified_Identification_Capability_Snapshot.json'
    path.write_text(json.dumps(generate(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return path


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',default='showcase_r3_mixture_v28p1')
    print(write(Path(ap.parse_args().outdir)))
