"""One frozen minimal POINT theorem + single-variable ablations.

The synthetic A4/A5 are explicitly stipulated population inputs, NOT inferred
from an observed sample. No LLM, PFN checkpoint, policy optimization or PARTIAL.

Run from repository root::
    python -B -m examples.minimal_correct_core_golden --output /tmp/golden.json
"""
from __future__ import annotations

import argparse
import copy
import json
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

from pfn_pipeline import (
    ArmInquiryV21, identify_network_business_query,
    make_complete_randomization_arm_task, replay_verified_business_outcome,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

NETWORK_ID = 'CFM_ID_MINIMAL_GOLDEN_PATH_3'
NODES = ('0', '1', '2')
BASE_EDGES = (('0', '1'), ('1', '2'))
EXTRA_EDGE = ('0', '2')
BASE_QUOTA = 2


def make_task(*, m: int = BASE_QUOTA, edges: tuple[tuple[str, str], ...] = BASE_EDGES,
              exposure_definition: str = 'strict_majority', admitted: bool = True,
              query_authority: str = 'TRUSTED_FIXTURE'):
    """Typed public constructor: all scientific source declarations synthetic."""
    net = NetworkExposureSpec(network_id=NETWORK_ID, node_ids=list(NODES),
                              undirected_edges=list(edges))
    exposure_state = 2 if exposure_definition == 'three_level_treated_neighbor_fraction' else 1
    return make_complete_randomization_arm_task(
        net, m=m, node_id='0', own_treatment_value=1,
        exposure_value=exposure_state, exposure_definition=exposure_definition,
        source='SYNTHETIC_EXPLICIT_D2_EXPERIMENT_AND_SYMBOLIC_A4',
        evidence=('SYNTHETIC_ONLY: fixed pretreatment graph, exactly m treated '
                  'uniformly; full-vector randomization, consistency and '
                  'typed SYMBOLIC population node-arm mean declared independently'),
        admitted=admitted, synthetic=True, query_authority=query_authority,
    )


def ablated_task(change: str):
    """Each change alters just one declared input class, no global mutation."""
    if change == 'base':
        return make_task()
    if change == 'zero_quota':
        return make_task(m=1)
    if change == 'add_network_edge':
        return make_task(edges=BASE_EDGES + (EXTRA_EDGE,))
    if change == 'different_exposure':
        return make_task(exposure_definition='three_level_treated_neighbor_fraction')
    if change == 'query_not_confirmed':
        return make_task(query_authority='PROPOSED')
    task = make_task()
    raw = copy.deepcopy(task.identification_spec)
    if change == 'missing_a4':
        raw['information_signature']['objects'][0].pop('randomized_arm_observable')
    elif change == 'a4_not_admitted':
        raw['information_signature']['objects'][0]['randomized_arm_observable']['admission'] = 'PROPOSED'
    elif change in ('a5_unresolved', 'a5_rejected'):
        found = False
        for item in raw['assumptions']:
            if item['name'] == 'full_vector_randomization':
                item['status'] = 'UNRESOLVED' if change == 'a5_unresolved' else 'NOT_ADMITTED'
                item['confirmed'] = False
                found = True
        if not found:
            raise RuntimeError('Expected full-vector randomization assumption missing')
    else:
        raise ValueError(f'Unknown ablation: {change}')
    return replace(task, identification_spec=raw)


def independent_support(*, m: int, edges: tuple[tuple[str, str], ...],
                        own_treatment: int = 1, exposure_state: int = 1,
                        exposure_definition: str = 'strict_majority') -> Fraction:
    """Independent oracle enumerating assignments, never imports SupportEngine."""
    neighbors = {v if u == '0' else u for u, v in edges if '0' in (u, v)}
    degree = len(neighbors)
    hits = 0
    for vector in combinations(NODES, m):
        treated = set(vector)
        count = len(neighbors & treated)
        if exposure_definition == 'strict_majority':
            state = int(2 * count > degree)
        elif exposure_definition == 'three_level_treated_neighbor_fraction':
            state = 0 if 3 * count < degree else 1 if 3 * count < 2 * degree else 2
        else:
            raise ValueError('Oracle only covers the two frozen grouping examples')
        hits += int(int('0' in treated) == own_treatment and state == exposure_state)
    return Fraction(hits, comb(len(NODES), m))


SCENARIOS = (
    'base', 'missing_a4', 'a4_not_admitted', 'a5_unresolved',
    'a5_rejected', 'zero_quota', 'add_network_edge',
    'different_exposure', 'query_not_confirmed',
)


def run_scenarios() -> dict:
    rows = []
    base_fingerprint = None
    for change in SCENARIOS:
        task = ablated_task(change)
        identified = identify_network_business_query(ArmInquiryV21(task))
        if change == 'base':
            base_fingerprint = task.target_fingerprint
        verified = replay_verified_business_outcome(identified) if identified.status == 'POINT' else False
        arm = task.identification_spec['query']
        grouping = (task.exposure_definition == 'three_level_treated_neighbor_fraction'
                    and 'three_level_treated_neighbor_fraction' or 'strict_majority')
        actual_m = task.identification_spec['randomized_network_arm_theorem_contract']['design']['m']
        edges = tuple(tuple(e) for e in task.identification_spec['network_exposure']['undirected_edges'])
        independent = independent_support(
            m=actual_m, edges=edges,
            own_treatment=arm['own_treatment_value'], exposure_state=arm['exposure_value'],
            exposure_definition=grouping,
        )
        certified = (
            identified.result.result['certificate']['joint_arm_support_probability']
            if identified.status == 'POINT' else None
        )
        if certified is not None and Fraction(certified) != independent:
            raise AssertionError(f'{change}: core support differs from independent enumeration')
        rows.append({
            'change': change,
            'status': identified.status,
            'route': identified.route,
            'reason_code': identified.reason_code,
            'replay_verified': verified,
            'exact_support_oracle': str(independent),
            'certified_support': certified,
            'same_target_as_base': task.target_fingerprint == base_fingerprint,
            'numeric_effect_estimated': False,
        })
    return {
        'schema_version': 'cfm-id-minimal-golden-stabilization-v1',
        'study': 'explicit synthetic population exercise only',
        'theorem': 'R1a randomized-network design-standardized arm (no exposure sufficiency)',
        'network': {'node_ids': list(NODES), 'undirected_edges': [list(e) for e in BASE_EDGES]},
        'design': {'kind': 'D2 uniform complete randomization', 'treated_quota': BASE_QUOTA},
        'exposure': 'E1 strict majority among pretreatment neighbors',
        'target': 'mu_0^q(1,1 | W)',
        'expected_base_support': '1/3',
        'scenarios': rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=None, help='write deterministic JSON to this path')
    args = parser.parse_args(argv)
    document = run_scenarios()
    content = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8')
    else:
        print(content, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
