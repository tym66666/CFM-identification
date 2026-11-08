"""Read-only ID -> Estimation capability inspection (contract v1).

No PFN calls, weight loading, estimator inference, new identification assumptions,
or conversion of POINT status into an executable EstimationRequest.

This is a diagnostic at the public boundary, not a replacement for the
independently replayed typed requests in ``replay_handoff``.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

from .contracts import IdentificationResult

__all__ = ["inspect_identification_estimation", "compare_arm_with_legacy_response"]

_VERSION = "idfm-id-estimation-target-contract-v1"
_ARM = "NETWORK_RANDOMIZED_ARM_MEAN"
_RESPONSE = "NETWORK_RESPONSE_SURFACE"
_SCORE = "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"
_EXPOSURE_STATES = {
    "strict_majority": (0, 1),
    "three_level_treated_neighbor_fraction": (0, 1, 2),
    "pretreatment_core_collaborator_majority": (0, 1),
}


def _verify_when_identified(identified: IdentificationResult) -> None:
    """Do not trust a persisted VERIFIED label or arbitrary support claims."""
    if identified.verification_status != "VERIFIED" or identified.status not in ("POINT", "PARTIAL"):
        return
    if identified.estimation_request is not None:
        from .identification import replay_handoff
        replay_handoff(identified)
    else:
        from .identification import replay_population_identification
        replay_population_identification(identified)


def inspect_identification_estimation(identified: IdentificationResult) -> dict[str, Any]:
    """Describe the *verified* target and whether a typed estimator request exists.

    Status ``REQUEST_DEFINED_RUNTIME_UNCHECKED`` does NOT imply that model
    weights, factual samples or training-target compatibility were checked.
    ``NO_ADAPTER`` does NOT mean the target is unidentifiable.
    """
    if not isinstance(identified, IdentificationResult):
        raise TypeError("Expected a public IdentificationResult")
    _verify_when_identified(identified)
    task = identified.task
    ready = identified.status in ("POINT", "PARTIAL") and identified.verification_status == "VERIFIED"
    report: dict[str, Any] = {
        "contract_version": _VERSION,
        "query_type": task.estimand,
        "target_id": task.target_id,
        "target_semantics": task.target_semantics,
        "target_fingerprint": (task.target_fingerprint or
                                (identified.result.get("identified_functional") or {}).get("target_fingerprint") or
                                identified.result.get("query", {}).get("response_target_fingerprint")),
        "outcome_kind": task.outcome_kind,
        "node_count": task.n_nodes,
        "identification": {
            "status": identified.status.value,
            "verification_status": identified.verification_status.value,
            "workflow_status": identified.diagnostics.get("workflow_status"),
        },
        "estimation": {
            "status": "NOT_IDENTIFIED" if not ready else (
                "REQUEST_DEFINED_RUNTIME_UNCHECKED" if identified.estimation_request is not None
                else "NO_ADAPTER"),
            "request_type": None if identified.estimation_request is None else
                            identified.estimation_request.get("request_type"),
            "runtime_checked": False,
            "trained_model_checked": False,
            "finite_sample_estimability_proven": False,
        },
    }
    if task.estimand == _ARM:
        # Read the checked *formal contract*, not loose task metadata or the
        # observed treatment sample. The full spec is replayed above when POINT.
        from ._internal.identification.schemas import IdentificationSpec
        if task.identification_spec is None:
            raise ValueError("Arm target requires the full identification specification")
        spec = IdentificationSpec.model_validate(task.identification_spec)
        contract = spec.randomized_network_arm_theorem_contract
        if contract is None:
            raise ValueError("Randomized-network arm target lacks its theorem contract")
        query = spec.query
        design = contract.design
        states = _EXPOSURE_STATES[task.exposure_definition]
        report.update({
            "query_scope": "single_node_single_arm",
            "conditioning": "full_fixed_pretreatment_network_context_W",
            "assignment": design.model_dump(mode="json"),
            "exposure": {
                "definition": task.exposure_definition,
                "states": list(states),
                "reference_set": "declared_C_i" if task.exposure_definition ==
                                 "pretreatment_core_collaborator_majority" else "all_network_neighbors",
            },
            "queried_arm": {
                "node_id": query.target_node_id,
                "own_treatment": query.own_treatment_value,
                "exposure_state": query.exposure_value,
            },
            "observable_functional": "E[Y_i^obs | W,T_i=a,S_i=s]",
            "potential_output_layout_if_all_arms_supported": [task.n_nodes, 2, len(states)],
            "full_surface_certified_by_this_single_arm": False,
        })
        if ready:
            support = identified.result.get("certificate", {}).get("joint_arm_support_probability")
            if support is None or Fraction(support) <= 0:
                raise ValueError("Verified arm result requires strictly positive support")
            report["population_joint_arm_support"] = support
        report["estimation"]["missing_for_existing_PFN"] = (
            "A separate estimator adapter matching the exact q, g, queried target "
            "and arm layout. The frozen PFN consumes a Bernoulli(1/2) E1 "
            "four-arm RESPONSE-SURFACE request, not this single-arm request."
        )
    elif task.estimand in (_RESPONSE, _SCORE):
        # A response surface may be a dependency of a policy score query; it
        # must not be mislabeled as the policy score itself.
        program = identified.result.get("identified_functional") or {}
        if task.estimand == _SCORE:
            response_program = program.get("response_program") or {}
        else:
            response_program = program
        report.update({
            "query_scope": "all_nodes_four_response_arms"
                            if task.estimand == _RESPONSE else "policy_score_with_response_dependency",
            "response_dependency": {
                "semantics": response_program.get("semantics"),
                "response_target_fingerprint": response_program.get("target_fingerprint"),
                "assignment_probability": response_program.get("assignment_probability_rational"),
                "grouping": response_program.get("grouping"),
                "arm_coordinates": [[0, 0], [0, 1], [1, 0], [1, 1]],
                "response_shape": [task.n_nodes, 2, 2],
            },
        })
        if identified.estimation_request is not None and task.estimand == _SCORE:
            report["estimation"]["response_request_type"] = (
                identified.estimation_request.get("response_request") or {}).get("request_type")
    else:
        report["query_scope"] = "route_specific_not_a_network_arm_surface"
    return report


def compare_arm_with_legacy_response(
    arm: IdentificationResult, legacy: IdentificationResult,
) -> dict[str, Any]:
    """Check a narrow symbolic alignment, NOT a permission to call the PFN.

    Compares a verified new single arm to the legacy Bernoulli majority response
    *dependency* (which may be nested inside a score query). Both must refer to
    the same node order, graph, outcome and full-context experimental target.
    """
    arm_profile = inspect_identification_estimation(arm)
    legacy_profile = inspect_identification_estimation(legacy)
    reasons: list[str] = []
    if arm_profile["query_type"] != _ARM or legacy_profile["query_type"] not in (_RESPONSE, _SCORE):
        reasons.append("Query types are not randomized arm vs legacy majority response")
    if (arm_profile["identification"]["verification_status"] != "VERIFIED"
        or legacy_profile["identification"]["verification_status"] != "VERIFIED"):
        reasons.append("Both population identification proofs must be independently verified")
    if reasons:
        return {"aligned": False, "reasons": reasons, "estimation_request_emitted": False}
    from ._internal.identification.schemas import IdentificationSpec
    spec = IdentificationSpec.model_validate(arm.task.identification_spec)
    design = spec.randomized_network_arm_theorem_contract.design
    response = legacy_profile["response_dependency"]
    if (arm.task.node_ids != legacy.task.node_ids
        or not _same_graph(arm.task.adjacency, legacy.task.adjacency)):
        reasons.append("Network and node order differ")
    if arm.task.outcome_kind != legacy.task.outcome_kind:
        reasons.append("Outcome domain differs")
    if arm.task.exposure_definition != "strict_majority":
        reasons.append("Legacy response uses only strict-majority E1")
    if design.kind != "heterogeneous_bernoulli_binary_v1":
        reasons.append("Legacy response requires independent Bernoulli assignment")
    else:
        p = Fraction(response["assignment_probability"])
        if set(design.propensities) != set(arm.task.node_ids) or any(
            Fraction(value) != p for value in design.propensities.values()
        ):
            reasons.append("Different assignment laws: new p_i do not all equal legacy p")
    if response["grouping"] != "K_i>floor(degree_i/2);ties=0":
        reasons.append("Exposure grouping differs")
    if response["semantics"] != "design_averaged_local_stochastic_response_not_fixed_assignment":
        reasons.append("Legacy response semantics are not the approved design-standardized target")
    if arm.task.target_semantics != "design_standardized_conditional_arm_mean_not_fixed_assignment":
        reasons.append("Arm target semantics differ")
    if spec.query.target_population != "fixed_network_conditional_context":
        reasons.append("Target population/conditioning context differs")
    # Compare a selected arm's exact joint support against the legacy proof
    # certificate rather than relying solely on matching prose or output shape.
    if not reasons:
        node_id = spec.query.target_node_id
        node_index = arm.task.node_ids.index(node_id)
        degree = int(arm.task.adjacency[node_index].sum())
        if legacy.task.estimand == _SCORE:
            response_result = legacy.result["certificate"]["response_identification_result"]
        else:
            response_result = legacy.result
        by_degree = response_result["certificate"]["design_by_degree"]
        weights = by_degree[str(degree)]["joint_own_treatment_arm_probabilities"]
        key = f"{spec.query.own_treatment_value},{spec.query.exposure_value}"
        actual = Fraction(arm_profile["population_joint_arm_support"])
        expected = Fraction(weights[key])
        if actual != expected:
            reasons.append("Verified queried-arm population support differs")
    return {
        "aligned": not reasons,
        "reasons": reasons,
        "comparison_scope": "symbolic_design_standardized_arm_semantics_under_same_W",
        "estimation_request_emitted": False,
        "note": (
            "Matching target semantics does not create a usable adapter for the new query. "
            "Legacy ER300 estimation must still run through its existing verified handoff."
        ),
    }


def _same_graph(a, b) -> bool:
    import numpy as np
    return bool(np.array_equal(a, b))
