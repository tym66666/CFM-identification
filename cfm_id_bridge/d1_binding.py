"""One *explicit* serializable v2.9 adapter: admitted D1/E1 randomized arm mean.

Other v2.8 routes are accepted through already-typed FormalQueryBindingV29,
never by guessing scientific parameters from business narratives.
"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator

from cfm_id_llm.schemas import StrictModel
from pfn_pipeline.identification import make_heterogeneous_bernoulli_arm_task
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline.identification_business import ArmInquiryV21
from .bridge import FormalQueryBindingV29, ScientificAdmissionV29


class ReviewedD1ArmPacketV29(StrictModel):
    schema_version: Literal["causal-idfm-reviewed-d1-arm-v2.9"] = "causal-idfm-reviewed-d1-arm-v2.9"
    scientific_admission: ScientificAdmissionV29
    network_id: str = Field(min_length=1)
    node_order: list[str] = Field(min_length=1)
    undirected_edges: list[tuple[str, str]]
    propensities: dict[str, str]
    target_node_id: str
    target_own_treatment: Literal[0, 1]
    target_exposure: int = Field(ge=0)
    exposure_definition: Literal["strict_majority"] = "strict_majority"
    outcome_kind: Literal["continuous", "binary"] = "continuous"
    protocol_evidence: str = Field(min_length=18)

    @model_validator(mode="after")
    def enforce_scope(self):
        if self.scientific_admission.formal_family != "R1A_ARM":
            raise ValueError("D1 packet cannot be used for a non-arm theorem family")
        if len(set(self.node_order)) != len(self.node_order) or set(self.propensities) != set(self.node_order):
            raise ValueError("Every distinct study node needs exactly one scientifically declared propensity")
        if self.target_node_id not in self.node_order:
            raise ValueError("Arm node is not a member of the declared network")
        return self


def prepare_d1_arm_binding_v29(packet: ReviewedD1ArmPacketV29) -> FormalQueryBindingV29:
    """Explicit, independently scientist-supplied design and A4/A5 declaration.

    Mathematical result is always conditional on truth of admitted scientific
    inputs. A signed PDF is NOT inferred from the presence of a CSV file.
    """
    a = packet.scientific_admission
    network = NetworkExposureSpec(network_id=packet.network_id,
                                  node_ids=packet.node_order,
                                  undirected_edges=packet.undirected_edges)
    task = make_heterogeneous_bernoulli_arm_task(
        network, propensities=packet.propensities,
        node_id=packet.target_node_id,
        own_treatment_value=packet.target_own_treatment,
        exposure_value=packet.target_exposure,
        source=a.a4_population_operator_reference,
        evidence=(f"Independent scientific review {a.scientific_reviewer}: "
                  f"{a.evidence_reference}; A5 {a.a5_assumption_reference}; "
                  f"protocol {packet.protocol_evidence}"),
        admitted=True,
        query_authority="TRUSTED_FIXTURE" if a.is_synthetic_fixture else "HUMAN_CONFIRMED",
        synthetic=a.is_synthetic_fixture,
        outcome_kind=packet.outcome_kind,
        exposure_definition=packet.exposure_definition,
    )
    return FormalQueryBindingV29(admission=a, inquiry=ArmInquiryV21(task))
