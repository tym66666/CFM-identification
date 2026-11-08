"""D2 public-materials arm adapter. Existing complete-randomization Core only."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import StrictBool,StrictInt
from .business_core_pilot_base import Closed,Target,State,canonical_hash,_target_blocker,target_coordinates
from .business_materials_base import bundle_value,Selection,select
from .business_materials_intake import sources,prompt_materials
from .business_materials_target_provenance import target_sources
from .business_materials_whole_clause_evidence import normalize as remaining_gate
from .business_candidate_base import ReviewedMaterialsContextV035,MaterialsCandidateApprovalV035
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_bridge.scientific_binding import scientific_target_coordinates,actual_scientific_sources,actual_scientific_licenses

from cfm_id.workflows.legacy_network.d2_submission import VERSION
from cfm_id.workflows.legacy_network.d2_submission import Study
from cfm_id.workflows.legacy_network.d2_submission import Local
from cfm_id.workflows.legacy_network.d2_submission import Question
from cfm_id.workflows.legacy_network.d2_submission import SYSTEM
from cfm_id.workflows.legacy_network.d2_submission import make_request

from cfm_id.workflows.legacy_network.d2_submission import project

from cfm_id.workflows.legacy_network.d2_submission import compile_inquiry

from cfm_id.workflows.legacy_network.d2_submission import preview_submission

def normalize_submission(bundle,provider):
    s,u=make_request(bundle);return preview_submission(bundle,provider.generate_json(system_prompt=s,user_prompt=u))

from cfm_id.workflows.legacy_network.d2_submission import identify_submission
