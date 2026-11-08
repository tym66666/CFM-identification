"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from dataclasses import dataclass
from typing import Literal
import json
from pydantic import Field
from cfm_id_llm.schemas import StrictModel, BusinessCase, PopulationInformationLevel
from cfm_id_llm.quality import MultiQueryQualityReportV010
from cfm_id_llm.candidate_queries import (
    BusinessQueryReviewV011, CandidateReasonerV011, CandidateSafetyError,
    COVERAGE_GAP_CODES,
)
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_bridge.scientific_binding import sha, canonical_data
from pfn_pipeline.identification_business import FixedPolicyInquiryV21


SHA = r"^[0-9a-f]{64}$"


class MaterialsCandidateApprovalV035(StrictModel):
    """A separate review record, not a signature or proof of natural language."""
    bundle_sha256: str = Field(pattern=SHA)
    model_draft_sha256: str = Field(pattern=SHA)
    science_packet_sha256: str = Field(pattern=SHA)
    gateway_case_sha256: str = Field(pattern=SHA)
    gateway_quality_sha256: str = Field(pattern=SHA)
    gateway_review_sha256: str = Field(pattern=SHA)
    reviewed_query_ids: list[str] = Field(min_length=1, max_length=8)
    reviewed_a4_levels: dict[str, PopulationInformationLevel]
    reviewer: str = Field(min_length=3)
    review_evidence: str = Field(min_length=10)
    reviewed_materials_to_gateway: Literal[True]
    synthetic_fixture: Literal[True]


@dataclass(frozen=True)
class ReviewedMaterialsContextV035:
    case: BusinessCase
    quality: MultiQueryQualityReportV010
    business_review: BusinessQueryReviewV011
    core_port: RealCoreCoveragePortV012
    approval: MaterialsCandidateApprovalV035
