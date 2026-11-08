"""Tiny standalone public D3×E1 identification example; no PFN checkpoint."""
from __future__ import annotations

from fractions import Fraction

from pfn_pipeline import (
    identify, make_two_group_quota_arm_task, replay_population_identification,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


def main() -> None:
    network = NetworkExposureSpec(
        network_id="five-person-d3-e1-fixture",
        node_ids=["0", "1", "2", "3", "4"],
        undirected_edges=[("0", "1"), ("0", "2"), ("0", "3")],
    )
    groups = (("0", "1"), ("2", "3", "4"))
    quotas = (1, 1)
    expected = {(0, 0): "1/6", (0, 1): "1/3", (1, 0): "1/2", (1, 1): "0"}
    for (a, s), mass in expected.items():
        task = make_two_group_quota_arm_task(
            network,
            groups=groups, treated_quotas=quotas,
            node_id="0", own_treatment_value=a, exposure_value=s,
            source="documented synthetic group-quota protocol",
            evidence="known pretreatment groups, quotas and graph",
            admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        result = identify(task)
        if Fraction(mass) > 0:
            assert result.status == "POINT"
            assert result.verification_status == "VERIFIED"
            assert result.result["certificate"]["joint_arm_support_probability"] == mass
            assert replay_population_identification(result).verification_status == "VERIFIED"
        else:
            assert result.status == "UNSUPPORTED"
            assert result.result["reason_code"] == "ZERO_ARM_SUPPORT"
        assert result.estimation_request is None
        print(f"node=0, (a,s)=({a},{s}): support={mass} status={result.status}")
    print("D3×E1 exact support and identification replay: PASS")


if __name__ == "__main__":
    main()
