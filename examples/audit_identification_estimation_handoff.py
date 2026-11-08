"""Small, checkpoint-free target/estimator capability audit.

From repository root: python -m examples.audit_identification_estimation_handoff
"""
from pathlib import Path
import json

from pfn_pipeline import (
    identify, inspect_identification_estimation, compare_arm_with_legacy_response,
    make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task,
    simulate_task,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.simulation import load_graph


def main():
    root = Path(__file__).resolve().parents[1]
    graph = load_graph(root / "pfn_pipeline/_internal/estimation/data/fixed_er_N20_p0.5_seed12345.json")
    legacy = identify(simulate_task(adjacency=graph, seed=2026, budget=3))
    network = NetworkExposureSpec.model_validate(legacy.task.identification_spec["network_exposure"])

    common = dict(
        network=network, node_id=network.node_ids[0],
        own_treatment_value=1, exposure_value=1,
        source="synthetic declared study protocol", evidence="known design and fixed pre-treatment graph",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
    )
    matching = identify(make_heterogeneous_bernoulli_arm_task(
        propensities={n: "1/2" for n in network.node_ids}, **common
    ))
    different = identify(make_complete_randomization_arm_task(m=10, **common))

    for name, identified in (("legacy_ER_response_dependency", legacy),
                             ("new_D1_half_E1_single_arm", matching),
                             ("new_D2_E1_single_arm", different)):
        audit = inspect_identification_estimation(identified)
        print(name, json.dumps({
            "query_type": audit["query_type"],
            "scope": audit["query_scope"],
            "id": audit["identification"],
            "estimation": audit["estimation"],
            "queried_arm": audit.get("queried_arm"),
            "support": audit.get("population_joint_arm_support"),
        }, ensure_ascii=False, indent=2))

    overlap = compare_arm_with_legacy_response(matching, legacy)
    assert overlap["aligned"] is True
    assert matching.estimation_request is None
    print("Symbolic overlap:", json.dumps(overlap, ensure_ascii=False))


if __name__ == "__main__":
    main()
