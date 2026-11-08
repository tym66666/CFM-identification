"""D1×E1/E2: verified population POINT without a PFN adapter.

Run from repo root:
    python -m examples.run_heterogeneous_bernoulli_arm
"""

from fractions import Fraction

from pfn_pipeline import identify, make_heterogeneous_bernoulli_arm_task, replay_population_identification
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


def main():
    network = NetworkExposureSpec(
        network_id='d1-small-known-protocol',
        node_ids=['0', '1', '2', '3'],
        undirected_edges=[('0', '1'), ('0', '2'), ('0', '3')],
    )
    probabilities = {'0': '1/2', '1': '1/4', '2': '1/2', '3': '3/4'}
    for grouping, states in (
        ('strict_majority', (0, 1)),
        ('three_level_treated_neighbor_fraction', (0, 1, 2)),
    ):
        print('\n', grouping)
        total = Fraction(0)
        for a in (0, 1):
            for s in states:
                task = make_heterogeneous_bernoulli_arm_task(
                    network, propensities=probabilities, node_id='0',
                    own_treatment_value=a, exposure_value=s,
                    exposure_definition=grouping, source='synthetic known randomization protocol',
                    evidence='known per-node Bernoulli probabilities and pretreatment graph',
                    admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE',
                )
                found = identify(task)
                assert (found.status, found.verification_status) == ('POINT', 'VERIFIED')
                assert found.estimation_request is None
                assert replay_population_identification(found).verification_status == 'VERIFIED'
                support = Fraction(found.result['certificate']['joint_arm_support_probability'])
                total += support
                print(f'  (node=0,a={a},s={s}) support={support} status={found.status.value}')
        assert total == 1
    print('All D1 POINT certificates verified; no EstimationRequest emitted.')


if __name__ == '__main__':
    main()
