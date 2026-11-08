"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.materials as materials
from cfm_id.workflows.legacy_network.submission import preview_submission
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.workflows.legacy_network.materials_base import compile_inquiry
from cfm_id.serialization import canonical_hash
from cfm_id.workflows.legacy_network.target_model import _target_blocker
from cfm_id.workflows.legacy_network.review_context import ReviewedMaterialsContextV035
from cfm_id.workflows.legacy_network.review_context import MaterialsCandidateApprovalV035
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.identification_business import ArmInquiryV21


VERSION="business-arm-submission-v0.43.1"


def _validate_context(context,bundle,raw,packet,design,target):
    if not isinstance(context,ReviewedMaterialsContextV035) or type(context.core_port) is not RealCoreCoveragePortV012:
        raise ValueError("REAL_REVIEWED_CONTEXT_REQUIRED")
    approval=MaterialsCandidateApprovalV035.model_validate(context.approval.model_dump(mode="json"))
    expected=(canonical_hash(bundle),canonical_hash(raw),canonical_hash(packet),
        canonical_sha256(context.case),canonical_sha256(context.quality),context.business_review.fingerprint())
    actual=(approval.bundle_sha256,approval.model_draft_sha256,approval.science_packet_sha256,
        approval.gateway_case_sha256,approval.gateway_quality_sha256,approval.gateway_review_sha256)
    if actual!=expected or "reviewed_materials_to_gateway" not in context.approval.model_fields_set:
        raise ValueError("STALE_OR_IMPLICIT_MATERIALS_REVIEW")
    if (approval.reviewed_query_ids!=["q1"] or list(bundle["question_slots"])!=["q1"]
        or [q.query_id for q in context.quality.draft.queries]!=["q1"]):
        raise ValueError("SINGLE_QUERY_REVIEW_REQUIRED")
    if packet.get("mode")!="SYNTHETIC_BENCHMARK_ONLY" or packet.get("bundle_sha256")!=canonical_hash(bundle) or packet.get("study")!=design:
        raise ValueError("INDEPENDENT_PROTOCOL_MISMATCH")
    b=context.core_port.bindings["q1"]
    if b.admission.is_synthetic_fixture is not True or b.admission.formal_family!="R1A_ARM" or type(b.inquiry) is not ArmInquiryV21:
        raise ValueError("SYNTHETIC_ARM_REVIEW_REQUIRED")
    science=packet.get("science",{})
    if (not all(science.get(k) for k in ("population_information","causal_licenses"))
        or b.admission.a4_population_operator_reference!=science["population_information"]
        or b.admission.a5_assumption_reference!=science["causal_licenses"]):
        raise ValueError("SCIENCE_PACKET_REFERENCE_MISMATCH")
    # Only compare with an already independently reviewed typed inquiry.
    from pfn_pipeline._internal.identification.schemas import IdentificationSpec
    actual=compile_inquiry(design,target,bundle,science)
    actual_spec=IdentificationSpec.model_validate(actual.task.identification_spec)
    reviewed_spec=IdentificationSpec.model_validate(b.inquiry.task.identification_spec)
    if (actual_spec.model_dump(mode="json")!=reviewed_spec.model_dump(mode="json")
        or actual.task.target_fingerprint!=b.inquiry.task.target_fingerprint):
        raise ValueError("TYPED_ARM_BINDING_MISMATCH")
    return b


def identify_arm_submission(bundle,raw,packet=None,*,context=None,synthetic_protocol_selected=False):
    out=preview_submission(bundle,raw);out["version"]=VERSION
    view=out["view"];view["version"]=VERSION
    if out["state"]!="REVIEW_REQUIRED":return out
    bundle=bundle_value(bundle)
    _,design,targets=materials.project(bundle,raw)
    if len(targets)!=1 or targets[0].kind!="arm":
        out["state"]="CHECK_BLOCKED";view.update(state="CHECK_BLOCKED",label="当前入口仅支持单个局部条件目标",
            conclusion="没有把其他问题改写成单门店条件目标。",next_step="使用对应目标的审核入口。")
        return out
    target=targets[0]
    blocker=_target_blocker(target,bundle["structure"]["nodes"],design)
    if blocker:
        out.update(state=blocker[0],reason_code=blocker[1])
        view.update(state=blocker[0],label="需要补充业务信息",conclusion="目标范围、情形或其余安排尚未明确。",
            next_step="明确这些业务条件后重新提交。")
        return out
    if not synthetic_protocol_selected or packet is None or context is None:return out
    try:
        binding=_validate_context(context,bundle,raw,packet,design,target)
        if binding.admission.approved_scientific_binding is None:
            out["state"]="SCIENCE_REVIEW_REQUIRED";view.update(state=out["state"],label="缺少独立科学审核",
                conclusion="没有执行正式识别。",next_step="完成独立科学审核后再提交。")
            return out
        coverage=context.core_port.lookup(case=context.case,quality=context.quality,
            review=context.business_review,query_id="q1")
    except Exception:
        out["review_error"]="MISSING_STALE_OR_UNSUPPORTED_REVIEW"
        view.update(conclusion="审核缺失、内容变化或科学绑定不匹配；未形成可展示结论。")
        return out
    out["core_called"]=True
    out["review_receipts"]=deepcopy(context.core_port.last_real_results)
    ident=materials.evaluate_draft(bundle,raw,packet,synthetic_protocol_selected=True)
    row=next((r for r in ident.get("results",[]) if r["query_id"]=="q1"),{})
    if row.get("status")!=coverage.status:raise RuntimeError("REVIEWED_CORE_DISPLAY_DISAGREE")
    out["identification"]=ident
    core=row.get("core",{});proof=core.get("identification") or {}
    view["core"].update(status=row.get("status","NOT_RUN"),reason=core.get("reason_code"),route=core.get("route"))
    if (row.get("status")=="POINT" and row.get("certificate_replay") is True
        and proof.get("verification_status")=="VERIFIED" and proof.get("certificate")
        and proof.get("identified_functional")):
        functional=proof["identified_functional"];cert=proof["certificate"]
        if functional["kind"]!="randomized_network_design_standardized_arm_mean":
            raise RuntimeError("UNEXPECTED_ARM_FUNCTIONAL")
        view.update(state="CORE_POINT",label="已识别 · Core 证书已重放",tone="point",
            conclusion="在明确审核的合成科学条件下，该门店在指定局部情形中的总体均值可识别。",
            next_step="核对条件平均公式及适用条件；尚未估计实际营业额。")
        view["core"].update(certificate_replayed=True,certificate_sha256=canonical_hash(cert),
            formula=functional["functional"],assignment_probability=cert["joint_arm_support_probability"],
            probability_label="所述局部情形的发生概率",
            formula_details=functional,certificate_hash_origin="FRESH_REPLAYED_CORE_CERTIFICATE")
        out["state"]="CORE_POINT"
    else:
        out["state"]="CHECK_BLOCKED";view.update(state="CHECK_BLOCKED",label="当前目标没有通过认证的识别公式",
            conclusion="保留当前Core结果；局部条件目标尚未适配库外候选。",next_step="检查目标支持及审核范围。")
    view["provenance_hashes"]={k:ident.get(k) for k in ("model_draft_sha256","input_bundle_sha256","packet_sha256")}
    view["understanding"].update(target_kind="arm",local_situation=[target.situation.own,target.situation.peers],
        remaining_rule=target.remaining,remaining_quote=target.remaining_quote,
        treated_nodes=[],target_nodes=target.nodes,aggregation="该门店的总体条件均值")
    view["a5_note"]="独立审核随机化、一致性、固定网络等前提；邻居分类不自动许可暴露均值充分性。本目标按原设计在指定局部条件下平均。"
    return out
