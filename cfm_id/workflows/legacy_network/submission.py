"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import cfm_id.workflows.legacy_network.materials as materials
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.workflows.legacy_network.result_view import _view


VERSION = "business-submission-v0.42"


def preview_submission(bundle, raw):
    """Validate the actual model draft without a science packet or Core call."""
    bundle = bundle_value(bundle)
    ident = materials.evaluate_draft(bundle, raw, {}, synthetic_protocol_selected=False)
    state = "REVIEW_REQUIRED"
    if ident["status"] == "REJECTED":
        state = "DRAFT_INVALID"
    elif ident.get("study_reading", {}).get("draws_independent") is not True:
        state = "NEEDS_INPUT"
        ident.update(status=state, reason_code="INDEPENDENT_GROUP_DRAWS_NOT_DECLARED")
    elif any(t.get("unresolved") for t in ident.get("proposed_targets", [])):
        state = "NEEDS_INPUT"
        ident.update(status=state, reason_code="BUSINESS_TARGET_INCOMPLETE")
    stub = dict(identification=ident, candidate_results=[], candidate_model_calls=0,
                candidate_gate="REVIEWED_MATERIALS_CONTEXT_REQUIRED")
    view = _view(bundle, raw, stub, context=None, qid="q1")
    if state == "DRAFT_INVALID":
        view.update(state=state, label="模型理解稿不符合输入合同", tone="failed",
                    conclusion="保留原始输出，本次没有进入识别。", next_step="检查原始材料与模型理解稿。")
    view.update(version=VERSION)
    return dict(version=VERSION, state=state, draft=deepcopy(raw), view=view,
                normalization=ident, identification=None, review_receipts={},
                candidate_model_calls=0, core_called=False, production_admission=False,
                estimation_called=False, policy_called=False, estimation_handoff_allowed=False)
