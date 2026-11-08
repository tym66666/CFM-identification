"""v2.9.2 reviewed Gateway/Core CLI with whitelisted JSON science packets.

The CLI does not infer q, A4, A5, network or treatment from business text.
The scientific packet is a second human-supplied document. No executable
code/deserialization of arbitrary modules is accepted from JSON.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from dataclasses import replace
from .business_intent import ApprovedBusinessIntentV292
from .evidence import ReviewedScientificEvidenceV292

from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.multiquery import MultiQueryReportV09, HumanMultiQueryReviewV09, approve_multiquery, audit_multiquery
from .bridge import run_verified_multiquery_v29
from .d1_binding import ReviewedD1ArmPacketV29, prepare_d1_arm_binding_v29
from .typed_packets import ReviewedTypedInquiryPacketV291, construct_reviewed_typed_binding_v291
from .scientific_binding import proposed_binding_snapshot_v291, sha
from cfm_id_llm.orchestration_schemas import canonical_sha256


def _read_obj(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    # Do not parse Gateway 0.9 flags through the v2.9 command parser. Unknown
    # option values would otherwise be reordered/lost by parse_known_args.
    if argv and argv[0] == "formulate":
        from cfm_id_llm.multiquery_cli import main as formulate_main
        return formulate_main(argv[1:])
    p = argparse.ArgumentParser(description="Causal-IDFM 2.9.2: independently reviewed A1/A4/A5 + real theorem verifier")
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("formulate", help="Run the original Gateway 0.9 multi-query CLI")
    review = subs.add_parser("review", help="Record explicit human BUSINESS-query approval (not A4/A5)")
    review.add_argument("--case-json", required=True)
    review.add_argument("--report-json", required=True)
    review.add_argument("--confirmed", action="append", required=True, help="Repeat for each query ID")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", required=True)
    review.add_argument("--output")
    run = subs.add_parser("identify", help="Verify reviewed queries using scoped, whitelisted typed packets")
    run.add_argument("--case-json", required=True)
    run.add_argument("--report-json", required=True,
                     help="Gateway MultiQueryReportV09, or top-level {'formulation': ...}")
    run.add_argument("--human-review-json", required=True)
    run.add_argument("--d1-packet-json", action="append", default=[],
                     help="One separately reviewed D1 arm typed packet per query (no automatic admission)")
    run.add_argument("--typed-packet-json", action="append", default=[],
                     help="v2.9.2 reviewed, route-specific safe JSON recipe (repeatable)")
    run.add_argument("--business-intent-json", action="append", default=[],
                     help="Independent human business-coordinate contract per query; REQUIRED for POINT")
    run.add_argument("--scientific-evidence-json", action="append", default=[],
                     help="Human-reviewed source-to-typed-A4/A5 evidence manifest per query")
    run.add_argument("--output")
    prep = subs.add_parser("prepare-science", help="Output an UNAPPROVED A1/A4/A5 worksheet for human scientific review")
    prep.add_argument("--case-json", required=True)
    prep.add_argument("--report-json", required=True)
    prep.add_argument("--human-review-json", required=True)
    prep.add_argument("--typed-packet-json", required=True)
    prep.add_argument("--approved-route", required=True)
    prep.add_argument("--output")
    args = p.parse_args(argv)
    try:
        case = BusinessCase.model_validate(_read_obj(args.case_json))
        raw = _read_obj(args.report_json)
        report = MultiQueryReportV09.model_validate(raw.get("formulation", raw))
        if args.command == "review":
            fresh = audit_multiquery(case, report.draft, provider=report.provider,
                                     prompt_version=report.prompt_version)
            if fresh != report:
                raise ValueError("Gateway report does not match current sources or draft")
            human = HumanMultiQueryReviewV09(
                case_id=case.case_id, input_sha256=report.input_sha256,
                draft_sha256=report.draft_sha256, confirmed_query_ids=args.confirmed,
                reviewed_by=args.reviewer, review_note=args.note, decision="CONFIRMED")
            approve_multiquery(case, report, human)
            payload = json.dumps(human.model_dump(mode="json"), ensure_ascii=False, indent=2)
            if args.output:
                Path(args.output).write_text(payload + "\n", encoding="utf-8")
            else:
                print(payload)
            return 0
        reviewed = approve_multiquery(case, report,
                 HumanMultiQueryReviewV09.model_validate(_read_obj(args.human_review_json)))
        if args.command == "prepare-science":
            packet=ReviewedTypedInquiryPacketV291.model_validate(_read_obj(args.typed_packet_json))
            binding=construct_reviewed_typed_binding_v291(packet)
            q=next((x for x in report.draft.queries if x.query_id==binding.admission.query_id),None)
            if q is None or q.query_id not in reviewed.human_review.confirmed_query_ids:
                raise ValueError('Only separately human-reviewed queries can receive a science worksheet')
            sheet=proposed_binding_snapshot_v291(binding.inquiry,
                business_review_sha256=sha(reviewed.human_review),
                target_sha256=canonical_sha256(q.target),
                business_quote=q.target.description.evidence[0].quote,
                a4_reference=binding.admission.a4_population_operator_reference,
                a5_reference=binding.admission.a5_assumption_reference,
                theorem_route=args.approved_route,
                reviewer=binding.admission.scientific_reviewer,
                evidence=binding.admission.evidence_reference)
            output={'status':'UNAPPROVED_SCIENTIFIC_REVIEW_WORKSHEET',
                    'warning':'Do not attach to ScientificAdmission without independent human scientific review.',
                    'proposed_structured_binding':sheet}
            payload=json.dumps(output,ensure_ascii=False,indent=2)
            if args.output: Path(args.output).write_text(payload+'\n',encoding='utf-8')
            else: print(payload)
            return 0
        bindings = tuple(prepare_d1_arm_binding_v29(
                    ReviewedD1ArmPacketV29.model_validate(_read_obj(path)))
                    for path in args.d1_packet_json) + tuple(
                    construct_reviewed_typed_binding_v291(
                        ReviewedTypedInquiryPacketV291.model_validate(_read_obj(path)))
                    for path in args.typed_packet_json)
        contracts=[ApprovedBusinessIntentV292.model_validate(_read_obj(path))
                   for path in args.business_intent_json]
        by_query={c.query_id:c for c in contracts}
        if len(by_query)!=len(contracts):
            raise ValueError('Duplicate independent business contracts')
        manifests=[ReviewedScientificEvidenceV292.model_validate(_read_obj(path))
                   for path in args.scientific_evidence_json]
        evidence_by_query={e.query_id:e for e in manifests}
        if len(evidence_by_query)!=len(manifests):
            raise ValueError('Duplicate scientific evidence manifest')
        bindings=tuple(replace(b,business_intent=by_query.get(b.admission.query_id),
                               evidence_manifest=evidence_by_query.get(b.admission.query_id))
                       for b in bindings)
        result = run_verified_multiquery_v29(case, reviewed, bindings)
        payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(f"v2.9.2 identification safely stopped ({type(exc).__name__}); no theorem certification produced.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
