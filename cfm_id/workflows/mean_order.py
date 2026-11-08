"""Reusable research workflow around the existing reader and review adapter.

No reference answers, approval generation, credentials or new mathematics live
here. The CLI is offline; a caller may inject an already configured provider.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path

from cfm_id_bridge.scientific_binding import sha
from cfm_id.source_locations import build_catalog
from cfm_id_llm.readers import mean_order_count_guidance as reading_request
from . import mean_order_review as adapter

VERSION = 'mean-order-workflow-1'


class WorkflowError(ValueError):
    pass


def public_bundle(value):
    """Reject accidental inclusion of reference/science/review payloads."""
    keys = {'case_id', 'node_order', 'documents', 'question_slots'}
    if type(value) is not dict or set(value) != keys:
        raise WorkflowError('PUBLIC_BUNDLE_FIELDS_REQUIRED')
    if (type(value['case_id']) is not str or not value['case_id'].strip()
            or type(value['node_order']) is not list or not value['node_order']
            or any(type(n) is not str or not n.strip() for n in value['node_order'])
            or len(set(value['node_order'])) != len(value['node_order'])):
        raise WorkflowError('EXPLICIT_PUBLIC_ROSTER_REQUIRED')
    for name in ('documents', 'question_slots'):
        if (type(value[name]) is not dict or not value[name]
                or any(type(k) is not str or not k.strip() or type(v) is not str
                       or not v.strip() for k, v in value[name].items())):
            raise WorkflowError('PUBLIC_TEXT_AND_QUESTION_SLOTS_REQUIRED')
    return deepcopy(value)


def make_request(bundle):
    system, user = reading_request.make_request(public_bundle(bundle))
    return dict(system=system, user=user)


def _view(bundle, wire, result, *, origin):
    """Present existing results; never infer or repair scientific permissions."""
    comparison = result.get('comparison_view', {})
    orders = result.get('order_view', {})
    questions = list(orders.get('clarification_questions', []))
    questions.extend(comparison.get('assignment_review', {}).get('questions', []))
    target_missing = []
    for qid, row in comparison.get('intent_condition_review', {}).items():
        if row.get('missing_conditions'):
            target_missing.append(dict(query_id=qid, missing=deepcopy(row['missing_conditions'])))
        # Translate the existing typed missing-field codes, without guessing values.
        for code in row.get('missing_conditions', []):
            if code == 'population':
                question = '请明确评价哪些对象：全体、指定子集或单个对象，并给出名单。'
            elif code == 'aggregation':
                question = '请明确汇总方式以及各对象的权重。'
            elif code.startswith('first.'):
                question = '请明确所问安排中“' + code[len('first.'):] + '”是否使用系统。'
            elif code.startswith('second.'):
                question = '请明确比较基准中“' + code[len('second.'):] + '”是否使用系统。'
            else:
                question = '请补充目标字段：' + code
            questions.append(qid + '：' + question)
        if row.get('intent', {}).get('kind') == '不明确':
            questions.append(qid + '：请明确要比较两个安排、评价一个安排，还是选择最优安排。')
    catalog = build_catalog(bundle['documents'])
    source_rows = []
    # The raw packet remains authoritative, including invalid or unknown fields.
    if type(wire) is dict and type(wire.get('order_reading')) is dict:
        claims = wire['order_reading'].get('claims')
        for claim in claims if type(claims) is list else []:
            if type(claim) is not dict:
                continue
            ids = claim.get('source_ids')
            source_rows.append(dict(claim=deepcopy(claim), sources=[deepcopy(catalog[i])
                for i in ids if type(i) is str and i in catalog] if type(ids) is list else [],
                reviewer_decision='PENDING'))
    state = result['state']
    reviewed = bool(result.get('synthetic_review_checked') and result.get('factored_review_checked'))
    certificate = result.get('bounded_result')
    interval = [certificate['lower'], certificate['upper']] if certificate and state in ('POINT', 'PARTIAL') else None
    return dict(workflow_version=VERSION, candidate_origin=origin, state=state,
        bundle_sha256=sha(bundle), candidate_sha256=sha(wire),
        public_materials=deepcopy(bundle), wire_candidate=deepcopy(wire), result=deepcopy(result),
        stages=[
            dict(name='业务材料', status='RECORDED'),
            dict(name='候选结构与引用', status='PARSED' if 'reading_candidate' in result else 'REJECTED',
                 semantic_correctness_automatically_proved=False),
            dict(name='独立业务与科学审核', status='SYNTHETIC_REVIEW_CHECKED' if reviewed else 'NOT_ADMITTED'),
            dict(name='识别计算', status='CALLED' if result.get('bounded_backend_called') else
                 'ENDPOINT_CHECK_ONLY' if result.get('core_called') else 'NOT_CALLED',
                 base_core_called=bool(result.get('core_called')), bounded_backend_called=bool(result.get('bounded_backend_called'))),
            dict(name='独立证书重放', status='VERIFIED' if result.get('bounded_certificate_replayed') else 'NOT_VERIFIED')],
        review_worksheet=dict(is_approval=False, condition_rows=source_rows, proposed_target=deepcopy(comparison.get('proposed_comparisons', {})),
            declared_assignment=deepcopy(comparison.get('assignment_review', {}).get('facts')),
            projection_receipt=deepcopy(result.get('projection_receipt')),
            instruction='逐条确认业务含义、原文与科学依据。此表是待填写视图，不是批准记录。'),
        clarification_questions=list(dict.fromkeys(questions)), target_missing=target_missing,
        unsupported_restrictions=list(orders.get('unsupported_restrictions', [])),
        answer=dict(state=state, exact_interval=interval,
            sharp_within_declared_model=bool(interval and result.get('bounded_certificate_replayed')),
            reason_code=result.get('reason_code'), interpretation={
                'POINT':'在已审核的模型与总体信息下，目标唯一确定。',
                'PARTIAL':'在已审核的模型与总体信息下，目标的sharp区间已重放验证。',
                'NEEDS_INPUT':'材料缺项或含义待澄清，尚未取得识别结论。',
                'REVIEW_REQUIRED':'候选仍需独立业务与科学审核。',
                'UNSUPPORTED':'当前适配入口未支持这些条件；这不是数学不可识别证明。',
                'CHECK_BLOCKED':'结构、来源或审核绑定未通过检查。',
                'INCOMPATIBLE':'已声明的条件与总体信息不相容。'}.get(state, '请查看原始结果与原因码。')),
        production_admission=False, estimation_handoff_allowed=False)


def inspect_candidate(bundle, wire, *, query_id='q1', science=None):
    bundle = public_bundle(bundle)
    wire = deepcopy(wire)
    result = adapter.prepare(bundle, wire, query_id=query_id, science=deepcopy(science))
    return _view(bundle, wire, result, origin='SAVED_CANDIDATE')


def read_once(bundle, provider, *, query_id='q1', allow_external=False, allow_document_sharing=False):
    """Exactly one provider invocation; caller owns authentication and dispatch quota.

    Provider-internal transport policy is not controlled by this helper. The
    established guarded runner must still enforce one HTTP dispatch/no retries.
    No scientific declaration or reference answer can enter the request.
    """
    if allow_external is not True or allow_document_sharing is not True:
        raise WorkflowError('EXPLICIT_EXTERNAL_AND_DOCUMENT_SHARING_REQUIRED')
    bundle = public_bundle(bundle); request = make_request(bundle)
    try:
        wire = deepcopy(provider.generate_json(system_prompt=request['system'], user_prompt=request['user']))
    except Exception:
        # Provider exception strings can contain headers or credentials.
        raise WorkflowError('LLM_REQUEST_FAILED_NO_REPLY') from None
    result = adapter.prepare(bundle, deepcopy(wire), query_id=query_id)
    return _view(bundle, wire, result, origin='PROVIDER_RESPONSE')


def submit_reviewed(bundle, wire, *, query_id='q1', science=None, packet=None, context=None,
                    assignment_review=None, review=None, factored_review=None,
                    synthetic_protocol_selected=False):
    bundle = public_bundle(bundle); wire = deepcopy(wire)
    result = adapter.submit(bundle, wire, query_id=query_id, science=science, packet=packet, context=context,
        assignment_review=assignment_review, review=review, factored_review=factored_review,
        synthetic_protocol_selected=synthetic_protocol_selected)
    return _view(bundle, wire, result, origin='REVIEW_SUBMISSION')


def load_json(path):
    def unique(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise WorkflowError('DUPLICATE_JSON_KEY')
            value[k] = v
        return value
    def invalid_constant(value):
        raise WorkflowError('NONFINITE_JSON_NUMBER')
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                          parse_constant=invalid_constant)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise WorkflowError('INPUT_FILE_OR_JSON_INVALID') from None


def write_json(path, value):
    # No overwriting prior evidence. Do not create partial output on JSON errors.
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        f.write(encoded)


def main(argv=None):
    parser = argparse.ArgumentParser(description='合成研究工作流：请求导出、候选检查、独立参考重放。CLI不调用API。')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('request', 'inspect', 'replay-synthetic'):
        p = sub.add_parser(name)
        p.add_argument('--bundle', required=True, type=Path)
        p.add_argument('--output', required=True, type=Path)
        if name != 'request':
            p.add_argument('--candidate', required=True, type=Path)
            p.add_argument('--query-id', default='q1')
        if name == 'inspect':
            p.add_argument('--science', type=Path)
        if name == 'replay-synthetic':
            p.add_argument('--fixture', required=True, type=Path)
            p.add_argument('--allow-synthetic-review', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise WorkflowError('OUTPUT_ALREADY_EXISTS')
        bundle = public_bundle(load_json(args.bundle))
        if args.command == 'request':
            result = make_request(bundle)
        elif args.command == 'inspect':
            result = inspect_candidate(bundle, load_json(args.candidate), query_id=args.query_id,
                                       science=load_json(args.science) if args.science else None)
        else:
            if not args.allow_synthetic_review:
                raise WorkflowError('EXPLICIT_SYNTHETIC_REVIEW_SELECTION_REQUIRED')
            # Reference admission stays in the explicit source-tree test harness.
            try:
                from examples.mean_order_workflow_fixture import replay_synthetic
            except ImportError:
                raise WorkflowError('SOURCE_TREE_SYNTHETIC_FIXTURE_REQUIRED') from None
            result = replay_synthetic(bundle, load_json(args.candidate), load_json(args.fixture), query_id=args.query_id)
        write_json(args.output, result)
    except (WorkflowError, ValueError, TypeError, KeyError, OSError) as exc:
        # File contents and provider strings are never echoed as diagnostics.
        reason = str(exc) if isinstance(exc, WorkflowError) else 'WORKFLOW_INPUT_OR_OUTPUT_REJECTED'
        print(json.dumps(dict(status='FAILED', reason=reason, api_calls=0)))
        return 2
    print(json.dumps(dict(status='SAVED', state=result.get('state'), output=str(args.output), api_calls=0), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
