"""CFM-ID LLM Gateway v0.12: independent business-first A0 quality extension."""
from .schemas import BusinessCase, DraftProblemSpec, FormulationReport
from .formulator import ProblemFormulator
from .orchestration_schemas import HumanReviewV02, OrchestrationReportV02, ConfirmedProblemV02
from .orchestrator import GatewayV02, route_formulation, confirm_formulation

from .candidate_schemas import CandidateDraftV03, CandidateReportV03
from .candidate_reasoner import CandidateReasonerV03, GatewayV03, CandidateNotAllowed

__version__ = "0.12.0"
__all__ = [
    "BusinessCase", "DraftProblemSpec", "FormulationReport", "ProblemFormulator",
    "HumanReviewV02", "OrchestrationReportV02", "ConfirmedProblemV02",
    "GatewayV02", "route_formulation", "confirm_formulation",
    "Audience", "BusinessExplanationV05", "explain_business",
    "NormalizationReviewV06", "ClarificationAnswerV06", "build_normalization_review", "append_clarification",
    "CandidateDraftV03", "CandidateReportV03", "CandidateReasonerV03", "GatewayV03", "CandidateNotAllowed",
    "create_grounded_intake", "review_grounded_intake", "MaterialQualityReportV08",
    "MultiQueryDraftV09", "MultiQueryReportV09", "MultiQueryFormulatorV09",
    "HumanMultiQueryReviewV09", "approve_multiquery", "prepare_core_handoff_preview",
    "QuerySemanticsV010", "MultiQueryDraftV010", "MultiQueryQualityReportV010",
    "A0QualityFormulatorV010", "audit_business_quality", "draft_from_v09",
    "ApprovedBusinessMathCrosswalkV012", "RealCoreCoveragePortV012",
    "unapproved_crosswalk_worksheet_v012",
]

from .business_presentation import Audience, BusinessExplanationV05, explain_business

from .normalization import (NormalizationReviewV06, ClarificationAnswerV06,
    build_normalization_review, append_clarification, render_review_text)

from .document_intake import (AttachmentRequestV07, AttachmentRecordV07, IntakeReportV07, create_intake)
from .multisource_normalization import (MultisourceReviewV07, review_intake)

from .material_integrity import (create_grounded_intake, review_grounded_intake, MaterialQualityReportV08)

from .multiquery import (MultiQueryDraftV09, MultiQueryReportV09, HumanMultiQueryReviewV09, approve_multiquery)
from .multiquery_formulator import MultiQueryFormulatorV09
from .handoff_preview import prepare_core_handoff_preview

from .quality import (QuerySemanticsV010, MultiQueryDraftV010,
    MultiQueryQualityReportV010, audit_business_quality, draft_from_v09)
from .quality_formulator import A0QualityFormulatorV010

from .trusted_core import (
    ApprovedBusinessMathCrosswalkV012, RealCoreCoveragePortV012,
    unapproved_crosswalk_worksheet_v012,
)
