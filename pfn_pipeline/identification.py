"""Population identification entry point; finite samples do not establish assumptions.

Supply a TaskSpec with the complete, admitted identification_spec. The archived
I0/UI proposal flows are not called implicitly. Every estimation consumer can
replay_handoff to recheck the proof rather than trusting a saved VERIFIED string.
"""
from dataclasses import replace
import json

from .contracts import TaskSpec, IdentificationResult
from ._internal.identification.schemas import IdentificationSpec
from ._internal.identification.schemas import IdentificationResult as BackendResult
from ._internal.identification.identification import IdentificationEngine
from ._internal.identification.verifier import IdentificationVerifier
from ._internal.identification.handoff import compile_estimation_request
from ._internal.identification.majority_response import REQUIRED as MAJORITY_REQUIREMENTS

__all__ = ["identify", "replay_handoff", "make_complete_randomization_arm_task", "make_two_group_quota_arm_task", "make_heterogeneous_bernoulli_arm_task", "replay_population_identification", "make_cluster_bernoulli_arm_task", "make_multi_group_quota_arm_task", "make_two_stage_quota_arm_task"]


def identify(task: TaskSpec) -> IdentificationResult:
    """Verify an explicit population specification and compile its estimation request."""
    replace(task)  # Recheck mutable nested payloads at the module boundary.
    if task.identification_spec is None:
        return IdentificationResult(task=task, diagnostics={"workflow_status": "NEEDS_INPUT"}, result={
            "status": "UNSUPPORTED", "verification_status": "UNSUPPORTED",
            "backend": "missing_population_spec", "query": {"type": task.estimand},
            "reason_code": "IDENTIFICATION_SPEC_REQUIRED",
            "message": "Supply the complete identification specification and assumption evidence.",
        })
    spec = IdentificationSpec.model_validate(task.identification_spec)
    result = IdentificationEngine().solve_verified(spec, IdentificationVerifier())
    diagnostics = {"workflow_status": "COMPLETE" if result.verification_status == "VERIFIED" else "UNSUPPORTED"}
    if result.reason_code == "D6_FIRST_STAGE_PROFILE_EXCLUSION_NOT_ADMITTED":
        diagnostics.update(workflow_status="NEEDS_INPUT",
            missing_assumptions=["first_stage_profile_no_direct_outcome_effect"])
    if result.reason_code == "REQUIRED_ASSUMPTIONS_NOT_ADMITTED":
        records = {item.name: item for item in spec.assumptions}
        missing = sorted(set(MAJORITY_REQUIREMENTS) - spec.confirmed_assumptions())
        rejected = [name for name in missing if name in records and
                    records[name].status in {"NOT_ADMITTED", "CONTRADICTED"}]
        diagnostics.update(
            workflow_status="UNSUPPORTED" if rejected else "NEEDS_INPUT",
            missing_assumptions=missing,
            rejected_assumptions=rejected,
        )
    if result.network_policy_mixture_proof is not None:
        request = None
        diagnostics["handoff_gap"] = (
            "Finite-mixture handoff requires separate population truth/program binding; "
            "TaskSpec factual node rows cannot substitute for that input."
        )
    else:
        request = compile_estimation_request(result, spec=spec)
    if (result.query.type == "NETWORK_RANDOMIZED_ARM_MEAN"
        and result.reason_code == "INTERFERENCE_STRUCTURE_UNRESOLVED"):
        diagnostics["workflow_status"] = "NEEDS_INPUT"
    if result.query.type == "NETWORK_RANDOMIZED_ARM_MEAN" and result.verification_status == "VERIFIED" and request is None:
        diagnostics["workflow_status"] = "IDENTIFIED_NO_ESTIMATION_ADAPTER"
        diagnostics["handoff_gap"] = (
            "The randomized-network arm mean is POINT identified at population level, "
            "but the current frozen PFN has no matching estimator contract. "
            "No EstimationRequest is emitted."
        )
    return IdentificationResult(task=task, result=result.model_dump(mode="python"),
        estimation_request=None if request is None else request.model_dump(mode="python"),
        diagnostics=diagnostics)


def replay_handoff(identification: IdentificationResult):
    """Return a freshly verified typed request; reject changed graphs/queries/proofs."""
    replace(identification.task)
    replace(identification)
    if identification.task.identification_spec is None or identification.estimation_request is None:
        raise ValueError("A complete source specification and verified estimation handoff are required")
    spec = IdentificationSpec.model_validate(identification.task.identification_spec)
    saved = BackendResult.model_validate(identification.result)
    checked = IdentificationVerifier().verify(spec, saved)
    if checked.verification_status != "VERIFIED" or checked.status not in ("POINT", "PARTIAL"):
        raise ValueError("Identification proof replay failed: " + checked.verification_message)
    if checked.network_policy_mixture_proof is not None:
        raise NotImplementedError("Finite-mixture replay needs a separate population/program input")
    request = compile_estimation_request(checked, spec=spec)
    if request is None:
        raise ValueError("The verified result has no executable estimation handoff")
    current = json.dumps(request.model_dump(mode="json"), sort_keys=True)
    original = json.dumps(identification.estimation_request, sort_keys=True)
    if current != original:
        raise ValueError("Estimation handoff differs from the independently replayed request")
    return request


def make_complete_randomization_arm_task(
    network,
    *,
    m: int,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int,
    source: str,
    evidence: str,
    exposure_definition: str = "strict_majority",
    core_collaborators=None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> TaskSpec:
    """Create a public population-only TaskSpec for D2 x E1/E2 single-arm ID.

    This constructor does not inspect treatment/outcome samples, infer an
    unknown design or elevate unreviewed assumptions.  Use it with ``identify``;
    a verified POINT result currently has no executable PFN EstimationRequest.
    """
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_complete_randomization_arm_spec
    network = NetworkExposureSpec.model_validate(network)
    spec = make_complete_randomization_arm_spec(
        network, m=m, node_id=node_id,
        own_treatment_value=own_treatment_value,
        exposure_value=exposure_value,
        source=source, evidence=evidence,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        admitted=admitted, query_authority=query_authority,
        synthetic=synthetic, outcome_kind=outcome_kind,
    )
    return _build_arm_task(
        network, spec,
        assignment_design={
            "design_type": "randomized_experiment",
            "assignment_scheme": "complete_randomization",
            "treated_quota": m,
        },
        name=f"D2-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}",
        setting=f"D2x{_exposure_label(exposure_definition)}",
        source=source, evidence=evidence,
    )


def make_two_group_quota_arm_task(
    network,
    *,
    groups: tuple[tuple[str, ...], tuple[str, ...]],
    treated_quotas: tuple[int, int],
    node_id: str,
    own_treatment_value: int,
    exposure_value: int,
    source: str,
    evidence: str,
    exposure_definition: str = "strict_majority",
    core_collaborators=None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> TaskSpec:
    """D3×E1/E2: one POINT arm with two pretreatment-group fixed quotas.

    Membership and treated quotas must be in the documented study design;
    do not infer them from a realized assignment. Between-group network edges
    are allowed. The target is conditional on the ORIGINAL group-quota law.
    """
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_two_group_quota_arm_spec
    network = NetworkExposureSpec.model_validate(network)
    spec = make_two_group_quota_arm_spec(
        network, groups=groups, treated_quotas=treated_quotas,
        node_id=node_id, own_treatment_value=own_treatment_value,
        exposure_value=exposure_value, source=source, evidence=evidence,
        exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,
        admitted=admitted, query_authority=query_authority,
        synthetic=synthetic, outcome_kind=outcome_kind,
    )
    design = spec.randomized_network_arm_theorem_contract.design
    return _build_arm_task(
        network, spec,
        assignment_design={
            "design_type": "randomized_experiment",
            "assignment_scheme": "two_group_fixed_quotas",
            "groups": [list(group) for group in design.groups],
            "treated_quotas": list(design.treated_quotas),
        },
        name=f"D3-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}",
        setting=f"D3x{_exposure_label(exposure_definition)}",
        source=source, evidence=evidence,
    )


def make_heterogeneous_bernoulli_arm_task(
    network,
    *,
    propensities,
    node_id: str,
    own_treatment_value: int,
    exposure_value: int,
    source: str,
    evidence: str,
    exposure_definition: str = "strict_majority",
    core_collaborators=None,
    admitted: bool = False,
    query_authority: str = "PROPOSED",
    synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> TaskSpec:
    """D1×E1/E2: one known heterogeneous independent-Bernoulli arm mean.

    ``propensities`` maps *every* pretreatment node ID to its known p_i.
    Accepts finite decimal/rational strings and finite numeric values; exact
    rational strings are stored in the formal design, not learned from data.
    This route has no executable PFN EstimationRequest yet.
    """
    from collections.abc import Mapping
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_heterogeneous_bernoulli_arm_spec
    if not isinstance(propensities, Mapping):
        raise TypeError("propensities must map every node ID to a known p_i")
    if any(isinstance(p, bool) for p in propensities.values()):
        raise ValueError("Boolean propensities are not valid probabilities")
    network = NetworkExposureSpec.model_validate(network)
    spec = make_heterogeneous_bernoulli_arm_spec(
        network,
        propensities={node: str(p) for node, p in propensities.items()},
        node_id=node_id, own_treatment_value=own_treatment_value,
        exposure_value=exposure_value, source=source, evidence=evidence,
        exposure_definition=exposure_definition, admitted=admitted,
        core_collaborators=core_collaborators,
        query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind,
    )
    return _build_arm_task(
        network, spec,
        assignment_design={
            "design_type": "randomized_experiment",
            "assignment_scheme": "heterogeneous_independent_bernoulli",
            "propensities": dict(spec.randomized_network_arm_theorem_contract.design.propensities),
        },
        name=f"D1-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}",
        setting=f"D1x{_exposure_label(exposure_definition)}",
        source=source, evidence=evidence,
    )


def make_two_stage_quota_arm_task(
    network, *, groups, quota_profiles, profile_probabilities,
    node_id:str,own_treatment_value:int,exposure_value:int,
    source:str,evidence:str,exposure_definition:str='strict_majority',
    core_collaborators=None,admitted:bool=False,
    profile_exclusion_admitted:bool=False,query_authority:str='PROPOSED',
    synthetic:bool=False,outcome_kind:str='continuous',
)->TaskSpec:
    """D6 public opt-in construction; no inferred A5 or numeric outcomes."""
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_two_stage_quota_arm_spec
    network=NetworkExposureSpec.model_validate(network)
    spec=make_two_stage_quota_arm_spec(network,
        groups=tuple(tuple(g) for g in groups),
        quota_profiles=tuple(tuple(q) for q in quota_profiles),
        profile_probabilities=tuple(profile_probabilities),
        node_id=node_id,own_treatment_value=own_treatment_value,
        exposure_value=exposure_value,source=source,evidence=evidence,
        exposure_definition=exposure_definition,core_collaborators=core_collaborators,
        admitted=admitted,profile_exclusion_admitted=profile_exclusion_admitted,
        query_authority=query_authority,synthetic=synthetic,outcome_kind=outcome_kind)
    design=spec.randomized_network_arm_theorem_contract.design
    return _build_arm_task(network,spec,assignment_design={
        'design_type':'randomized_experiment','assignment_scheme':'two_stage_quota_mixture',
        'groups':[list(g) for g in design.groups],
        'quota_profiles':[list(q) for q in design.quota_profiles],
        'profile_probabilities':list(design.profile_probabilities)},
        name=f'D6-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}',
        setting=f'D6x{_exposure_label(exposure_definition)}',source=source,evidence=evidence)


def make_multi_group_quota_arm_task(
    network, *, groups, treated_quotas, node_id:str,own_treatment_value:int,
    exposure_value:int,source:str,evidence:str,exposure_definition:str='strict_majority',
    core_collaborators=None,admitted:bool=False,query_authority:str='PROPOSED',
    synthetic:bool=False,outcome_kind:str='continuous',
)->TaskSpec:
    """D5: independent complete randomization within 3..64 fixed strata."""
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_multi_group_quota_arm_spec
    network=NetworkExposureSpec.model_validate(network)
    spec=make_multi_group_quota_arm_spec(
        network,groups=tuple(tuple(g) for g in groups),
        treated_quotas=tuple(treated_quotas),node_id=node_id,
        own_treatment_value=own_treatment_value,exposure_value=exposure_value,
        source=source,evidence=evidence,exposure_definition=exposure_definition,
        core_collaborators=core_collaborators,admitted=admitted,
        query_authority=query_authority,synthetic=synthetic,outcome_kind=outcome_kind)
    design=spec.randomized_network_arm_theorem_contract.design
    return _build_arm_task(network,spec,assignment_design={
        'design_type':'randomized_experiment','assignment_scheme':'multi_group_fixed_quotas',
        'groups':[list(g) for g in design.groups],
        'treated_quotas':list(design.treated_quotas)},
        name=f'D5-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}',
        setting=f'D5x{_exposure_label(exposure_definition)}',source=source,evidence=evidence)


def make_cluster_bernoulli_arm_task(
    network, *, clusters, cluster_probabilities, node_id: str,
    own_treatment_value: int, exposure_value: int, source: str, evidence: str,
    exposure_definition: str = 'strict_majority', core_collaborators=None,
    admitted: bool = False, query_authority: str = 'PROPOSED',
    synthetic: bool = False, outcome_kind: str = 'continuous',
) -> TaskSpec:
    """D4: fixed cluster partition, independent cluster-level Bernoulli draws."""
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.randomized_network_arm import make_cluster_bernoulli_arm_spec
    network = NetworkExposureSpec.model_validate(network)
    spec = make_cluster_bernoulli_arm_spec(
        network, clusters=tuple(tuple(x) for x in clusters),
        cluster_probabilities=tuple(str(x) for x in cluster_probabilities),
        node_id=node_id, own_treatment_value=own_treatment_value,
        exposure_value=exposure_value, source=source, evidence=evidence,
        exposure_definition=exposure_definition, core_collaborators=core_collaborators,
        admitted=admitted, query_authority=query_authority, synthetic=synthetic,
        outcome_kind=outcome_kind)
    design = spec.randomized_network_arm_theorem_contract.design
    return _build_arm_task(network, spec, assignment_design={
        'design_type': 'randomized_experiment',
        'assignment_scheme': 'cluster_bernoulli',
        'clusters': [list(x) for x in design.clusters],
        'cluster_probabilities': list(design.cluster_probabilities),
    }, name=f'D4-{_exposure_label(exposure_definition)} arm mean: node={node_id}, a={own_treatment_value}, s={exposure_value}',
        setting=f'D4x{_exposure_label(exposure_definition)}', source=source, evidence=evidence)


def _exposure_label(exposure_definition: str) -> str:
    return {"strict_majority": "E1", "three_level_treated_neighbor_fraction": "E2",
            "pretreatment_core_collaborator_majority": "E3",
            "exact_treated_neighbor_count": "E4", "any_treated_neighbor": "E5"}[exposure_definition]


def _build_arm_task(network, spec, *, assignment_design, name, setting, source, evidence) -> TaskSpec:
    """One public envelope for all supported single-arm randomized-network designs."""
    import numpy as np
    node_index = {node: i for i, node in enumerate(network.node_ids)}
    a = np.zeros((len(node_index), len(node_index)), dtype=np.int8)
    for left, right in network.undirected_edges:
        i, j = node_index[left], node_index[right]
        a[i, j] = a[j, i] = 1
    return TaskSpec(
        name=name,
        target_id=(
            f"randomized-network-arm-{spec.query.target_node_id}-{spec.query.own_treatment_value}-{spec.query.exposure_value}"
            + ("-E2" if spec.randomized_network_arm_theorem_contract.grouping == "three_level_treated_neighbor_fraction"
               else "-E3" if spec.randomized_network_arm_theorem_contract.grouping == "pretreatment_core_collaborator_majority"
               else "-E4" if spec.randomized_network_arm_theorem_contract.grouping == "exact_treated_neighbor_count"
               else "-E5" if spec.randomized_network_arm_theorem_contract.grouping == "any_treated_neighbor"
               else "")
        ),
        estimand="NETWORK_RANDOMIZED_ARM_MEAN",
        target_semantics="design_standardized_conditional_arm_mean_not_fixed_assignment",
        node_ids=tuple(network.node_ids),
        adjacency=a,
        assignment_design=assignment_design,
        exposure_definition={
            "strict_majority_ties_low": "strict_majority",
            "three_level_treated_neighbor_fraction": "three_level_treated_neighbor_fraction",
            "pretreatment_core_collaborator_majority": "pretreatment_core_collaborator_majority",
            "exact_treated_neighbor_count": "exact_treated_neighbor_count",
            "any_treated_neighbor": "any_treated_neighbor",
        }[spec.randomized_network_arm_theorem_contract.grouping],
        outcome_kind=spec.domain(spec.query.outcome).kind,
        identification_spec=spec.model_dump(mode="python"),
        target_fingerprint=spec.query.response_target_fingerprint,
        metadata={"setting": setting, "source": source, "evidence": evidence},
    )


def replay_population_identification(identification: IdentificationResult):
    """Recheck an identification certificate without requiring an estimator.

    Replays the *population* proof with the current formal specification;
    unlike ``replay_handoff``, this works for a route with no PFN adapter.
    Returns a fresh typed verification result, and never manufactures an
    EstimationRequest.
    """
    replace(identification.task)
    replace(identification)
    if identification.task.identification_spec is None:
        raise ValueError("Population identification replay requires a complete formal specification")
    spec = IdentificationSpec.model_validate(identification.task.identification_spec)
    saved = BackendResult.model_validate(identification.result)
    checked = IdentificationVerifier().verify(spec, saved)
    if checked.status not in ("POINT", "PARTIAL") or checked.verification_status != "VERIFIED":
        raise ValueError("Population identification proof replay failed: " + checked.verification_message)
    return checked
