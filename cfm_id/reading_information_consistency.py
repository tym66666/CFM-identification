"""Detect an explicit cross-stage contradiction, without repairing either read.

The caller must first validate the current intake, its independent field review,
and the fact candidate. UNKNOWN is not evidence of absence; STATED is not A4
admission. The check compares declared states, not the truth of business prose.
"""
from copy import deepcopy


def population_information_conflict(entry, information):
    claim = entry.get('reviewed_population_information')
    if not isinstance(claim, dict) or claim.get('state') != 'MISSING':
        return None
    indices = [i for i, row in enumerate(information) if row['availability'] in
               ('SYMBOLIC_POPULATION_OPERATOR', 'EXACT_POPULATION_VALUE')]
    if not indices:
        return None
    return dict(
        reason_code='POPULATION_INFORMATION_DISAGREES_WITH_REVIEWED_A0',
        a0_field='common.available_information',
        reviewed_a0_claim=deepcopy(claim),
        conflicting_fact_paths=[f'/information/{i}' for i in indices],
        fact_claims=[deepcopy(information[i]) for i in indices],
        intake_sha256=entry['intake_sha256'],
        request_sha256=entry['request_sha256'],
        reference_namespaces=dict(a0='reviewed intake candidate refs', facts='parsed fact source ids'),
        candidate_modified=False, scientific_approval=False,
        source_absence_proven=False,
    )
