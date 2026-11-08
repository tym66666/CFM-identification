"""v0.6 internal component demo: D3 x E2, plus unchanged public ID route."""
from __future__ import annotations

from fractions import Fraction
from pfn_pipeline import identify, make_two_group_quota_arm_task
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, TwoGroupFixedQuotaDesignV1,
)


def main():
    net = NetworkExposureSpec(
        network_id='five-person-cross-group',
        node_ids=['0','1','2','3','4'],
        undirected_edges=[('0','1'),('0','2'),('0','3')],
    )
    groups, quotas = (('0','1'),('2','3','4')), (1, 1)
    assignment = AssignmentSpec(TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=quotas))
    exposure = ExposureSpec('three_level_treated_neighbor_fraction')
    expected = {(0,0):Fraction(0),(0,1):Fraction(1,6),(0,2):Fraction(1,3),
                (1,0):Fraction(1,6),(1,1):Fraction(1,3),(1,2):Fraction(0)}
    for (a, s), mass in expected.items():
        evidence = SupportEngine.evaluate(
            network=net, assignment=assignment, exposure=exposure,
            node_id='0', own_treatment_value=a, exposure_value=s,
        )
        assert evidence.joint_probability == mass
        task = make_two_group_quota_arm_task(
            net, groups=groups, treated_quotas=quotas, node_id='0',
            own_treatment_value=a, exposure_value=s,
            exposure_definition='three_level_treated_neighbor_fraction',
            source='documented synthetic group-quota protocol',
            evidence='known design, fixed pretreatment graph, consistency and randomization',
            synthetic=True, admitted=True, query_authority='TRUSTED_FIXTURE',
        )
        answer = identify(task)
        assert answer.estimation_request is None
        assert answer.status == ('POINT' if mass else 'UNSUPPORTED')
        if mass:
            assert answer.verification_status == 'VERIFIED'
            assert Fraction(answer.result['certificate']['joint_arm_support_probability']) == mass
        else:
            assert answer.result['reason_code'] == 'ZERO_ARM_SUPPORT'
        print(f'a={a},s={s} : pi={mass}, status={answer.status}')
    print('D3×E2 component composition + production Identification: PASS')


if __name__ == '__main__':
    main()
