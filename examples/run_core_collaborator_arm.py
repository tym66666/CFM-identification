"""D1/D2/D3 x E3: pre-treatment core-collaborator majority POINT demo.

Run from repository root:
    python -m examples.run_core_collaborator_arm

No model weights or outcome samples are used by Identification.
"""
from fractions import Fraction

from pfn_pipeline import (
    identify, replay_population_identification,
    make_complete_randomization_arm_task,
    make_heterogeneous_bernoulli_arm_task,
    make_two_group_quota_arm_task,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


def main():
    network = NetworkExposureSpec(
        network_id="core-collaborators-5-person-example",
        node_ids=["0", "1", "2", "3", "4"],
        undirected_edges=[("0", "1"), ("0", "2"), ("0", "3"), ("0", "4")],
    )
    # Source-of-truth C_i is supplied by the documented pre-treatment protocol;
    # no exposure mapping is learned from assignment or outcome observations.
    core = {
        "0": ["1", "2", "3"], "1": ["0"], "2": ["0"],
        "3": ["0"], "4": ["0"],
    }
    designs = (
        ("D1", make_heterogeneous_bernoulli_arm_task,
         {"propensities": {"0": "1/2", "1": "1/4", "2": "1/2", "3": "3/4", "4": "1/2"}}),
        ("D2", make_complete_randomization_arm_task, {"m": 2}),
        ("D3", make_two_group_quota_arm_task,
         {"groups": (("0", "1"), ("2", "3", "4")), "treated_quotas": (1, 1)}),
    )
    for design_name, constructor, args in designs:
        print(f"\n{design_name} x E3")
        probability_sum = Fraction(0)
        for own in (0, 1):
            for exposure in (0, 1):
                task = constructor(
                    network, **args, core_collaborators=core,
                    node_id="0", own_treatment_value=own, exposure_value=exposure,
                    exposure_definition="pretreatment_core_collaborator_majority",
                    source="pre-treatment synthetic collaboration protocol",
                    evidence="declared network, core sets, and known randomization",
                    admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
                )
                result = identify(task)
                support = (Fraction(result.result["certificate"]["joint_arm_support_probability"])
                           if result.status == "POINT" else Fraction(0))
                probability_sum += support
                if support:
                    assert (result.status, result.verification_status) == ("POINT", "VERIFIED")
                    assert replay_population_identification(result).verification_status == "VERIFIED"
                    assert result.estimation_request is None
                else:
                    assert result.result["reason_code"] == "ZERO_ARM_SUPPORT"
                print(f"  a={own}, s={exposure}: pi={support}, status={result.status.value}")
        assert probability_sum == 1
    print("\nThree assignment designs x E3 verified; no PFN adapter required or claimed.")


if __name__ == "__main__":
    main()
