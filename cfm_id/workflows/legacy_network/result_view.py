"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from __future__ import annotations
import json


VERSION="identification-display-v0.41"


STATES={
 "CORE_POINT":("已识别 · Core 证书已重放","point"),
 "NEEDS_INPUT":("需要补充业务信息","pending"),
 "REVIEW_REQUIRED":("需要业务与科学审核","pending"),
 "SCIENCE_REVIEW_REQUIRED":("缺少独立科学审核","pending"),
 "CANDIDATE_CHECKED":("候选附件核对通过 · 无 Core 证书","candidate"),
 "CANDIDATE_UNDETERMINED":("模型未提出可核对的反例","pending"),
 "CANDIDATE_OUTPUT_INVALID":("候选输出不符合格式合同","failed"),
 "CANDIDATE_CHECK_FAILED":("候选附件未通过核对","failed"),
 "CHECK_BLOCKED":("审核或检查未完成","pending"),
}


def _view(bundle, raw, result, *, context, qid):
    ident=result["identification"]
    row=next((r for r in ident.get("results",[]) if r["query_id"]==qid),{})
    proposed=row.get("proposed_target") or next(iter(ident.get("proposed_targets",[])),{})
    cand=next((r for r in result.get("candidate_results",[]) if r["query_id"]==qid),{})
    check=result.get("schedule_diagnostics",{}).get(qid,{})
    study=ident.get("study_reading",{})
    core=row.get("core",{})
    proof=core.get("identification") or {}
    formula=None;witness=None;certificate=None
    state="CHECK_BLOCKED"
    detail="尚未形成可展示的识别结论。"
    next_step="先核对输入与审核记录，再重放识别。"
    if ident.get("status")=="NEEDS_INPUT":
        state="NEEDS_INPUT"
        reason=ident.get("reason_code")
        if reason=="INDEPENDENT_GROUP_DRAWS_NOT_DECLARED":
            detail="材料没有说明不同组的抽签是否相互独立；不能从各组中签概率自行推断。"
            next_step="补充各组抽签之间的关系，再重新提交。"
        else:
            detail="当前业务描述或字段仍不完整。"
            next_step="补充缺失信息，确认目标与比较方式。"
    elif row.get("status")=="POINT":
        if (row.get("certificate_replay") is True and proof.get("verification_status")=="VERIFIED"
            and proof.get("certificate_sha256") and proof.get("identified_functional")):
            state="CORE_POINT"
            certificate=proof["certificate_sha256"]
            formula=proof["identified_functional"]
            detail="在本例明确设定的合成科学条件下，目标可由声明的总体观测信息唯一确定。"
            next_step="查看识别公式与适用条件；尚未计算现实业务效果。"
        else:
            detail="POINT 声明缺少完整的证书重放依据，不能展示为认证结论。"
    elif result.get("candidate_gate")=="REVIEWED_MATERIALS_CONTEXT_REQUIRED":
        state="REVIEW_REQUIRED"
        detail="业务和科学审核上下文未提供，候选生成已被阻止。"
        next_step="确认业务目标、总体信息来源和所需因果前提后，再提交。"
    elif cand.get("status")=="BLOCKED":
        missing_science=False
        if context is not None:
            binding=context.core_port.bindings.get(qid)
            missing_science=binding is not None and binding.admission.approved_scientific_binding is None
        if missing_science:
            state="SCIENCE_REVIEW_REQUIRED"
            detail="独立科学审核缺失，现有条件不能授权调用库外数学候选。"
            next_step="由研究者审核本问题的总体信息和科学假设；模型不能代为批准。"
        else:
            detail="审核或 Core 查询没有通过，候选调用已被阻止。"
    elif any(e.get("query_id")==qid for e in result.get("flat_contract_errors",[])):
        state="CANDIDATE_OUTPUT_INVALID"
        detail="服务返回了 JSON，但字段组合不符合候选合同；这不是网络调用失败。"
        next_step="保留原始输出，检查输出格式；本次不形成数学结论。"
    elif check.get("status")=="PASSED_EXACT_CONSTRUCTION" and cand.get("status")=="UNVERIFIED_CANDIDATE":
        state="CANDIDATE_CHECKED"
        witness={k:check[k] for k in ("assignments_checked","support_probability_sum","target_in_support","theta_a","theta_b","target_gap")}
        witness["support_rows"]=check["support_rows"]
        detail="已重新核对两个虚构世界：实际可出现的分配下观测相同，原目标却不同。"
        next_step="附件可供进一步科学复核；它没有新增 Core 证书，也不用于业务效果估计。"
    elif check.get("status")=="MODEL_UNDETERMINED":
        state="CANDIDATE_UNDETERMINED"
        detail="模型未给出可核对的反例。弃答及其解释不能证明目标可识别或不可识别。"
        next_step="保留原目标与条件，进一步检查或改进候选生成。"
    elif check:
        state="CANDIDATE_CHECK_FAILED"
        reasons={"OBSERVABLE_LAWS_DIFFER":"至少一种正概率分配下，两世界观测结果不同。",
                 "TARGETS_EQUAL":"两个世界的原目标值相同，不能构成所需反例。",
                 "BINDING_MISMATCH":"候选与当前目标或科学条件不匹配。",
                 "INVALID_CONTRACT":"结构化输出不符合合同。"}
        detail=reasons.get(check["status"],"附件未通过当前范围的核对，不能给出数学结论。")
        next_step="依据核对失败的位置检查原始候选，保留当前 Core 结果。"
    label,tone=STATES[state]
    groups=study.get("groups",[]);probabilities=study.get("probabilities") or []
    return dict(version=VERSION,query_id=qid,state=state,label=label,tone=tone,
        conclusion=detail,next_step=next_step,
        question=bundle["documents"][bundle["active_goal_document"]].strip(),
        understanding=dict(outcome={"downtime_hours":"停机小时（时间窗见业务原文）"}.get(study.get("outcome"),study.get("outcome") or "未定"),
            design=study.get("design") or "未定",independence=study.get("draws_independent"),
            exposure={"any_treated_neighbor":"至少一台相邻设备启用工具"}.get(study.get("exposure"),study.get("exposure") or "未定"),
            treated_nodes=proposed.get("treated_nodes") or [],target_nodes=proposed.get("nodes") or [],
            aggregation={"equal_mean":"等权平均","single":"单台设备的总体均值"}.get(proposed.get("aggregation"),"待确认"),
            groups=[dict(nodes=g,probability=probabilities[i] if i<len(probabilities) else None) for i,g in enumerate(groups)]),
        core=dict(status=row.get("status") or "NOT_RUN",reason=core.get("reason_code") or ident.get("reason_code"),
            route=core.get("route"),certificate_replayed=state=="CORE_POINT",
            certificate_sha256=certificate,formula=formula,assignment_probability=proof.get("assignment_probability") if state=="CORE_POINT" else None),
        candidate=dict(status=cand.get("status") or "NOT_RUN",check_status=check.get("status") or "NOT_CHECKED",
            display_error_kind="OUTPUT_CONTRACT_FAILURE" if state=="CANDIDATE_OUTPUT_INVALID" else None,
            certificate_issued=False,witness=witness,
            replay_provider_calls=result["candidate_model_calls"]),
        scope="全部为合成业务；科学前提是显式测试设定，未获真实企业研究的科学批准。",
        result_kind="POPULATION_IDENTIFICATION_OR_CONSTRUCTION_NOT_BUSINESS_ESTIMATE",
        production_admission=False,estimation_called=False,policy_called=False,estimation_handoff_allowed=False,
        a4_note="识别需要明确认可的总体观测信息；有限样本日志不能替代它。",
        a5_note="需要独立审核随机化、一致性、固定网络与有限矩条件；同伴暴露定义不自动许可均值充分性。",
        documents=dict(bundle["documents"]),
        provenance_hashes={k:ident.get(k) for k in ("model_draft_sha256","input_bundle_sha256","packet_sha256")})
