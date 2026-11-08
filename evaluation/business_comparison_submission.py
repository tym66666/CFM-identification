"""Reviewed multi-comparison submission adapter; existing Core mathematics only."""
from copy import deepcopy
from . import business_materials as materials
from .business_submission import preview_submission,normalize_submission
from .business_materials_base import bundle_value,compile_inquiry
from .business_core_pilot_base import canonical_hash,_target_blocker
from .business_candidate_base import ReviewedMaterialsContextV035,MaterialsCandidateApprovalV035
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_bridge.scientific_binding import scientific_target_coordinates,actual_scientific_sources,actual_scientific_licenses
from pfn_pipeline.identification_business import EffectsInquiryV21

VERSION="business-comparison-submission-v0.45"
def identify_comparison_submission(bundle,raw,packet=None,*,context=None,synthetic_protocol_selected=False):
    out=preview_submission(bundle,raw)
    # This entry has a per-query display contract; never expose a q1-only view.
    out.pop("view",None)
    out.update(version=VERSION,query_views=[],review_error=None)
    if out["state"]!="REVIEW_REQUIRED":return out
    bundle=bundle_value(bundle);_,design,targets=materials.project(bundle,raw)
    qids=list(bundle["question_slots"])
    if len(qids)!=len(targets) or any(t.kind!="comparison" for t in targets):
        out["state"]="CHECK_BLOCKED";out["reason_code"]="COMPARISON_TARGETS_REQUIRED";return out
    blockers={q:_target_blocker(t,bundle["structure"]["nodes"],design) for q,t in zip(qids,targets)}
    if any(blockers.values()):
        out.update(state="NEEDS_INPUT",query_blockers=blockers);return out
    if not synthetic_protocol_selected or packet is None or context is None:return out
    try:
        if type(context) is not ReviewedMaterialsContextV035 or type(context.core_port) is not RealCoreCoveragePortV012:
            raise ValueError("REAL_REVIEWED_CONTEXT_REQUIRED")
        approval=MaterialsCandidateApprovalV035.model_validate(context.approval.model_dump(mode="json"))
        expected=(canonical_hash(bundle),canonical_hash(raw),canonical_hash(packet),canonical_sha256(context.case),
            canonical_sha256(context.quality),context.business_review.fingerprint())
        actual=(approval.bundle_sha256,approval.model_draft_sha256,approval.science_packet_sha256,
            approval.gateway_case_sha256,approval.gateway_quality_sha256,approval.gateway_review_sha256)
        if expected!=actual or "reviewed_materials_to_gateway" not in context.approval.model_fields_set:
            raise ValueError("STALE_MATERIALS_REVIEW")
        if (approval.reviewed_query_ids!=qids or [q.query_id for q in context.quality.draft.queries]!=qids
            or set(context.core_port.bindings)!=set(qids) or set(context.core_port.crosswalks)!=set(qids)
            or context.business_review.confirmed_query_ids!=qids):
            raise ValueError("FULL_QUERY_REVIEW_REQUIRED")
        if packet.get("mode")!="SYNTHETIC_BENCHMARK_ONLY" or packet.get("bundle_sha256")!=canonical_hash(bundle) or packet.get("study")!=design:
            raise ValueError("SCIENCE_PACKET_MISMATCH")
        science=packet.get("science",{})
        for qid,target in zip(qids,targets):
            binding=context.core_port.bindings[qid];admission=binding.admission
            if (admission.is_synthetic_fixture is not True or admission.formal_family!="R1A_EFFECT"
                or type(binding.inquiry) is not EffectsInquiryV21 or admission.approved_scientific_binding is None):
                raise ValueError("EXPLICIT_EFFECT_SCIENCE_REQUIRED")
            if (not all(science.get(k) for k in ("population_information","causal_licenses"))
                or admission.a4_population_operator_reference!=science["population_information"]
                or admission.a5_assumption_reference!=science["causal_licenses"]):
                raise ValueError("SCIENCE_REFERENCE_MISMATCH")
            compiled=compile_inquiry(design,target,bundle,science)
            if (scientific_target_coordinates(compiled)!=scientific_target_coordinates(binding.inquiry)
                or actual_scientific_sources(compiled)!=actual_scientific_sources(binding.inquiry)
                or actual_scientific_licenses(compiled)!=actual_scientific_licenses(binding.inquiry)):
                raise ValueError("EXACT_TYPED_BINDING_MISMATCH")
    except Exception:
        out["review_error"]="MISSING_STALE_OR_UNSUPPORTED_REVIEW";return out
    # Each lookup revalidates independent intent, science, crosswalk and actual Core.
    # Errors are retained per query, including any earlier completed lookup.
    coverage={};errors={}
    before=len(context.core_port.calls)
    for qid in qids:
        try:
            coverage[qid]=context.core_port.lookup(case=context.case,quality=context.quality,
                review=context.business_review,query_id=qid)
        except Exception:errors[qid]="REVIEWED_CORE_LOOKUP_REJECTED"
    out["core_called"]=len(context.core_port.calls)>before
    out["review_receipts"]=deepcopy(context.core_port.last_real_results)
    if errors:
        out.update(state="CHECK_BLOCKED",query_errors=errors);return out
    ident=materials.evaluate_draft(bundle,raw,packet,synthetic_protocol_selected=True)
    out["identification"]=ident
    if [r["query_id"] for r in ident["results"]]!=qids:raise RuntimeError("CORE_QUERY_COVERAGE_DISAGREES")
    for row,t in zip(ident["results"],targets):
        qid=row["query_id"];core=row.get("core",{});proof=core.get("identification") or {}
        if row["status"]!=coverage[qid].status:raise RuntimeError("REVIEWED_CORE_DISPLAY_DISAGREES")
        verified=(row["status"]=="POINT" and row.get("certificate_replay") is True
            and proof.get("verification_status")=="VERIFIED" and proof.get("bundle_sha256") and proof.get("results"))
        out["query_views"].append(dict(query_id=qid,state="CORE_POINT" if verified else "CHECK_BLOCKED",
            question=bundle["question_slots"][qid],status=row["status"],route=core.get("route"),
            certificate_replayed=bool(verified),certificate_sha256=proof.get("bundle_sha256") if verified else None,
            proof=proof if verified else None,target_nodes=t.nodes,aggregation=t.aggregation,
            first=[t.situation.own,t.situation.peers],second=[t.reference.own,t.reference.peers],
            remaining_rule=t.remaining,remaining_quote=t.remaining_quote,outcome=design["outcome"]))
    out["state"]="CORE_POINT" if all(q["certificate_replayed"] for q in out["query_views"]) else "CHECK_BLOCKED"
    return out

