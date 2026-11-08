"""Bound ordinary-language follow-up for fixed-assignment-id, without approvals.

Plans report missing fields in the actual candidate, not proven omissions in
the source. Replies become new source text; no model coordinate is patched.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
from cfm_id_bridge.scientific_binding import sha
from .question_bound_assignment import CONTRACT, question_catalog, resolve_reading, preview

VERSION = 'question-clarification-1'


def _question(fields):
    parts = ['请先核对原材料是否已经说明；若尚未说明，请补充这道题的以下内容，也可以说明仍未决定。']
    if 'intent' in fields:
        parts.append('您想问某个安排下的平均结果，还是比较两种安排？')
    for side, label in (('first', '所问安排'), ('second', '比较的另一种安排')):
        nodes = [f[len(side)+1:] for f in fields if f.startswith(side+'.')]
        if nodes:
            parts.append(f'{label}中，{"、".join(nodes)}各自是否使用这项措施？')
    if 'population' in fields:
        parts.append('结果要评价哪些对象？请给出评价范围或名单。')
    if 'aggregation' in fields:
        parts.append('多个评价对象的结果要怎样汇总，各自采用什么权重？')
    return ' '.join(parts)


def clarification_plan(bundle, candidate):
    """Recompute from the current source-bound candidate, never trust a status."""
    resolve_reading(bundle, candidate)
    out = preview(bundle, candidate)
    cat = question_catalog(bundle)
    plan = dict(version=VERSION, contract=CONTRACT, bundle_sha256=sha(bundle),
        candidate_sha256=sha(candidate), scientific_approval=False, core_called=False,
        missing_basis='ACTUAL_CANDIDATE_NOT_PROVEN_SOURCE_ABSENCE',
        assignment_state=out['assignment_review']['state'], questions=[])
    for qid, receipt in out['intent_condition_review'].items():
        fields = list(receipt['missing_conditions'])
        if receipt['intent']['kind'] == '不明确':
            fields.append('intent')
        if not fields:
            continue
        question = _question(fields)
        record = dict(query_id=qid, question_id=cat[qid]['question_id'],
            missing_fields=fields, question=question)
        record['clarification_id'] = 'clarify_' + sha(dict(
            version=VERSION, bundle_sha256=plan['bundle_sha256'],
            candidate_sha256=plan['candidate_sha256'], **record))
        plan['questions'].append(record)
    return plan


def append_reply(bundle, candidate, plan, clarification_id, reply):
    """Append to one current question; rereading and fresh review are mandatory."""
    fresh = clarification_plan(bundle, candidate)
    if type(plan) is not dict or plan != fresh:
        raise ValueError('STALE_OR_CHANGED_CLARIFICATION_PLAN')
    record = next((q for q in fresh['questions'] if q['clarification_id'] == clarification_id), None)
    if record is None:
        raise ValueError('ACTIVE_CLARIFICATION_REQUIRED')
    if type(reply) is not str or not reply.strip():
        raise ValueError('ORDINARY_LANGUAGE_REPLY_REQUIRED')
    result = deepcopy(bundle)
    history = result.setdefault('question_clarifications', [])
    if type(history) is not list:
        raise ValueError('INVALID_CLARIFICATION_HISTORY')
    qid = record['query_id']
    text = bundle['question_slots'][qid] + '\n【用户对本题的补充材料，尚未经业务与科学审核】\n' + reply
    doc_id = 'question_reply_' + sha(dict(clarification_id=clarification_id, reply=reply))[:24] + '.txt'
    if doc_id in result['documents']:
        raise ValueError('CLARIFICATION_DOCUMENT_ALREADY_EXISTS')
    result['documents'][doc_id] = text
    result['question_slots'][qid] = text
    history.append(dict(version=VERSION, parent_bundle_sha256=sha(bundle),
        parent_candidate_sha256=sha(candidate), clarification_id=clarification_id,
        query_id=qid, previous_question_id=record['question_id'],
        previous_question_text=bundle['question_slots'][qid],
        missing_fields=deepcopy(record['missing_fields']), question=record['question'],
        reply=reply, document_id=doc_id, scientific_approval=False,
        requires_fresh_reading=True, requires_fresh_review=True))
    # Validate source locations only. Reply semantics are still entirely unread.
    question_catalog(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('plan', 'reply'):
        p = sub.add_parser(name)
        p.add_argument('--bundle', required=True)
        p.add_argument('--candidate', required=True)
        p.add_argument('--output', required=True)
        if name == 'reply':
            p.add_argument('--plan', required=True)
            p.add_argument('--clarification-id', required=True)
            p.add_argument('--reply-file', required=True)
    args = parser.parse_args(argv)
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        b, raw = read(args.bundle), read(args.candidate)
        if args.command == 'plan':
            result = clarification_plan(b, raw)
        else:
            result = append_reply(b, raw, read(args.plan), args.clarification_id,
                Path(args.reply_file).read_text(encoding='utf-8-sig'))
        with Path(args.output).open('x', encoding='utf8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'CLARIFICATION_INPUT_OR_OUTPUT_ERROR: {type(exc).__name__}; use current inputs and a new output path.\n')
    print(json.dumps(dict(command=args.command, http_calls=0, core_called=False, scientific_approval=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

