"""Runnable D2xE1 population-only Identification demo (no checkpoint)."""
from pfn_pipeline import (
    identify, make_complete_randomization_arm_task, replay_population_identification,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

net = NetworkExposureSpec(
    network_id="small-complete-design-fixture",
    node_ids=["0", "1", "2"],
    undirected_edges=[("0", "1")],
)
task = make_complete_randomization_arm_task(
    net,
    m=2, node_id="0", own_treatment_value=1, exposure_value=1,
    source="documented small-network synthetic experiment",
    evidence="all size-2 allocations equally likely; finite potential outcomes",
    admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
)
result = identify(task)
assert result.status == "POINT" and result.verification_status == "VERIFIED"
assert result.estimation_request is None
replay_population_identification(result)

print("Query:", result.result["query"]["expression"])
print("Identification:", result.status, result.verification_status)
print("Exact arm support:", result.result["certificate"]["joint_arm_support_probability"])
print("Downstream:", result.diagnostics["workflow_status"])
