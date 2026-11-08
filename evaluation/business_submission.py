"""Submission boundary for the synthetic fixed-policy materials pilot.

Normalization never selects scientific assumptions. Explicit, separately supplied
reviews are checked through the existing trusted Core port before displaying any
POINT or dispatching a candidate. No credentials or HTTP implementation here.
"""
from copy import deepcopy
from . import business_materials as materials
from . import structured_witness_flat_candidate as candidates
from .business_candidate_base import _validate_context
from .business_materials_base import bundle_value
from .identification_replay_display import _view

from cfm_id.workflows.legacy_network.submission import VERSION


from cfm_id.workflows.legacy_network.submission import preview_submission


def normalize_submission(bundle, provider):
    """Exactly one provider invocation; no retry, repair, or implied review."""
    system, user = materials.make_request(bundle)
    raw = provider.generate_json(system_prompt=system, user_prompt=user)
    return preview_submission(bundle, raw)


def identify_submission(bundle, raw, packet=None, *, context=None, hours_review=None,
                        candidate_provider=None, synthetic_protocol_selected=False,
                        enable_candidates=False):
    """Continue the same draft using existing, content-bound independent reviews.

    This release intentionally supports the existing synthetic fixed-policy
    adapter only. These records do not authenticate reviewer identities.
    """
    out = preview_submission(bundle, raw)
    if out["state"] != "REVIEW_REQUIRED":
        return out
    if not synthetic_protocol_selected or packet is None or context is None:
        return out
    qids = set(bundle["question_slots"])
    # The current display is single-query; do not silently hide later queries.
    if qids != {"q1"}:
        out["state"] = "CHECK_BLOCKED"
        out["view"].update(state="CHECK_BLOCKED", label="当前提交入口尚未适配此问题",
            conclusion="当前入口只展示单个固定方案问题。", next_step="使用已有多目标审核入口。")
        return out
    try:
        _validate_context(context, bundle_value(bundle), raw, packet, qids)
        binding = context.core_port.bindings["q1"]
        if binding.admission.approved_scientific_binding is None:
            out["state"] = "SCIENCE_REVIEW_REQUIRED"
            out["view"].update(state=out["state"], label="缺少独立科学审核",
                conclusion="不能进入正式识别或调用库外候选。", next_step="完成独立科学审核后再提交。")
            return out
        coverage = context.core_port.lookup(case=context.case, quality=context.quality,
            review=context.business_review, query_id="q1")
        receipt = deepcopy(context.core_port.last_real_results["q1"])
        if coverage.status not in ("POINT", "UNSUPPORTED"):
            raise ValueError("REVIEWED_CORE_RESULT_NOT_ADAPTED")
    except Exception:
        out.update(state="REVIEW_REQUIRED", review_error="MISSING_STALE_OR_UNSUPPORTED_REVIEW")
        out["view"].update(conclusion="审核缺失、内容已变化或当前入口尚未适配；未形成可展示的识别结论。",
                           next_step="核对业务目标、科学条件及审核记录的内容绑定。")
        return out
    result = candidates.evaluate_with_candidates(bundle, raw, packet, context=context,
        hours_review=hours_review, provider=candidate_provider,
        synthetic_protocol_selected=True, enable_candidates=enable_candidates)
    row = next((r for r in result["identification"].get("results", []) if r["query_id"] == "q1"), {})
    if row.get("status") != coverage.status:
        raise RuntimeError("Reviewed Core and display Core disagree")
    if any(result.get(k) for k in ("estimation_called", "policy_called", "estimation_handoff_allowed")):
        raise RuntimeError("Identification-only boundary violated")
    view = _view(bundle, raw, result, context=context, qid="q1")
    if coverage.status == "UNSUPPORTED" and not enable_candidates:
        view.update(state="CANDIDATE_NOT_REQUESTED", label="现有识别库未覆盖 · 候选待请求",
            conclusion="审核已完成，现有 Core 没有给出识别公式。",
            next_step="可明确选择请求一个未认证的模型候选，或由研究者继续分析。")
    view.update(version=VERSION)
    out.update(state=view["state"], view=view, identification=result, core_called=True,
        candidate_model_calls=result["candidate_model_calls"], review_receipts={"q1":receipt})
    return out
