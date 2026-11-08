"""Single randomized-arm submission/display adapter, no new mathematics.

Only separately supplied, exact business/science reviews can authorize Core.
The existing Core computes support, the observable formula, and certificate replay.
"""
from copy import deepcopy
import json
from . import business_materials as materials
from .business_submission import preview_submission, normalize_submission
from .business_materials_base import bundle_value, compile_inquiry
from .business_core_pilot_base import canonical_hash, _target_blocker
from .business_candidate_base import ReviewedMaterialsContextV035, MaterialsCandidateApprovalV035
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.identification_business import ArmInquiryV21

from cfm_id.workflows.legacy_network.arm_submission import VERSION

from cfm_id.workflows.legacy_network.arm_submission import _validate_context

from cfm_id.workflows.legacy_network.arm_submission import identify_arm_submission
