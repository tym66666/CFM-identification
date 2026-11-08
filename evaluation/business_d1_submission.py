"""D1 heterogeneous Bernoulli materials and reviewed comparisons; no new Core math."""
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

from fractions import Fraction
from pathlib import Path
from hashlib import sha256
from .business_materials_intake import load_bundle as original_load, PUBLIC, _rows
from .business_d2_submission import Question
from pfn_pipeline.identification_business import EffectsInquiryV21
from cfm_id.workflows.legacy_network.d1_submission import VERSION
from cfm_id.workflows.legacy_network.d1_submission import Study

def load_bundle(case_id,*,public_root=PUBLIC,**kwargs):
    b=original_load(case_id,public_root=public_root,**kwargs)
    name="design_probabilities.csv"
    if name in b["tables"]:
        data=(Path(public_root)/case_id/name).read_bytes()
        if sha256(data).hexdigest()!=b["file_inventory"][name]["sha256"]:raise ValueError("PROBABILITY_FILE_CHANGED")
        headers,rows=_rows(data.decode("utf-8-sig"))
        if not {"node_id","randomization_probability"}<=set(headers):raise ValueError("PROBABILITY_COLUMNS_MISSING")
        b["tables"][name]["rows"]=[{k:r[k] for k in ("node_id","randomization_probability")} for r in rows]
        b["probability_binding"]=dict(source=name,file_sha256=sha256(data).hexdigest(),table_sha256=canonical_hash(b["tables"][name]))
    else:b["probability_binding"]=None
    probability_table(b)
    return b

from cfm_id.workflows.legacy_network.d1_submission import probability_table

from cfm_id.workflows.legacy_network.d1_submission import SYSTEM
from cfm_id.workflows.legacy_network.d1_submission import make_request

from cfm_id.workflows.legacy_network.d1_submission import project

from cfm_id.workflows.legacy_network.d1_submission import compile_inquiry

from cfm_id.workflows.legacy_network.d1_submission import preview_submission

def normalize_submission(bundle,provider):
    s,u=make_request(bundle);return preview_submission(bundle,provider.generate_json(system_prompt=s,user_prompt=u))

from cfm_id.workflows.legacy_network.d1_submission import identify_submission
