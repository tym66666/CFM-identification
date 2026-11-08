"""D2×E2 complete randomization + three-level neighbor fraction, no PFN needed."""
from pfn_pipeline import identify, make_complete_randomization_arm_task, replay_population_identification
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

net = NetworkExposureSpec(
    network_id="d2-e2-five-node-fixture",
    node_ids=[str(i) for i in range(5)],
    undirected_edges=[("0", "1"), ("0", "2"), ("0", "3")],
)
for a in (0, 1):
    for s in (0, 1, 2):
        task = make_complete_randomization_arm_task(
            net, m=2, node_id="0", own_treatment_value=a,
            exposure_value=s, exposure_definition="three_level_treated_neighbor_fraction",
            source="documented synthetic protocol", evidence="uniform allocation of two treated nodes",
            admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        result = identify(task)
        certificate = result.result.get("certificate", {})
        print(f"(a={a}, exposure={s}): {result.status}, support={certificate.get('joint_arm_support_probability', '0')}")
        assert result.estimation_request is None
        if result.status == "POINT":
            assert result.verification_status == "VERIFIED"
            assert replay_population_identification(result).verification_status == "VERIFIED"
        else:
            assert result.result["reason_code"] == "ZERO_ARM_SUPPORT"
