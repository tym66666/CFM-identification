"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import re


VERSION = 'business-condition-evidence-v0.53'


INSTRUCTION = '''
每问增加peer_evidence={"first":原文或null,"second":原文或null}，分别支持first和second的同伴人数条件。
非null引文必须逐字复制这一问question_slots的完整原句，包括编号、标点、限定、否定和尚未决定等词；不截取分句、半句或多个分句组成的片段。
peer_evidence存放原文，不是来源定位；不要填写文件名、行号或“文件名:行号”。其他source字段仍按各自要求填写来源。
同一条件适用于两个情形时，可以引用同一句；不要从历史分组、别的问题或识别要求补出阈值。
只问“同伴使用是否有帮助”，没有说明几人使用、哪两种情形时，neighbors=不明确，peer_evidence对应项=null。
本人状态、评价对象和同伴范围已经明确的部分照常保留。不得因为同伴人数未知而删除其他信息。
只有明确超过一半才用超过一半；恰好一名与至少一名不同。未确定、否定或备选条件不能当成已经选定的条件。
条件为不明确、情形为null或完整名单安排时，对应peer_evidence=null。引文不是科学假设或识别证书。
此检查保守处理未覆盖的表达；不要为通过检查改写用户原句或自动改写目标。
'''


_NUMBER = r'(?:[0-9]+|[零〇一二两三四五六七八九十百]+)'


_EXACT = re.compile(r'(?:恰好|正好)\s*('+_NUMBER+r')\s*(?:个|名|家|位|人|所|间|条|座)')


_PATTERNS = {
    '超过一半': re.compile(r'超过(?:一半|半数)|多于(?:一半|半数)|过半'),
    '至多一半': re.compile(r'(?:至多|最多|不超过)(?:一半|半数)'),
    '至少一个': re.compile(r'至少\s*(?:一|1)\s*(?:个|名|家|位|人|所|间|条|座)'),
    '一个也没有': re.compile(r'(?:一|1)(?:个|名|家|位|人|所|间|条|座)(?:也|都)?(?:没有|未)|没有任何'),
}


_UNSET = re.compile(r'尚未|未确定|没(?:有)?决定|还没|未决定|并非|不是|不一定|不能认为|不代表|不要求|不限定|不按|未采用|没有采用')


_SPLIT = re.compile(r'[，,。；;！？!?\n]')


def augment_request(system, user):
    """Add one common contract to an existing full or staged reading request."""
    message = json.loads(user)
    question = message['output_schema']['$defs']['Question']
    if 'peer_evidence' in question['properties']:
        raise ValueError('DUPLICATE_PEER_EVIDENCE_CONTRACT')
    question['properties']['peer_evidence'] = dict(type='object', additionalProperties=False,
        required=['first', 'second'], properties={s: {'type': ['string', 'null'],
            'description': '条件明确时逐字复制当前 question_slots 完整原句；条件不明确或不适用时为 null。不是文件名或行号。'}
            for s in ('first', 'second')})
    question['required'].append('peer_evidence')
    # Limit quotation form in new requests without supplying semantic labels.
    # Keep the validator backward compatible with already saved full clauses.
    for qid, goal in message['question_slots'].items():
        item = message['output_schema']['properties']['questions']['properties'][qid]
        item.setdefault('allOf', []).append({'properties': {'peer_evidence': {
            'properties': {side: {'enum': [goal, None]} for side in ('first', 'second')}
        }}})
    return system + INSTRUCTION, json.dumps(message, ensure_ascii=False)


def _integer(text):
    if text.isascii() and text.isdigit():
        return int(text)
    digits = dict(zip('零〇一二两三四五六七八九', (0,0,1,2,2,3,4,5,6,7,8,9)))
    if text in digits:
        return digits[text]
    if text.count('十') == 1 and '百' not in text:
        a, b = text.split('十')
        if (not a or a in digits) and (not b or b in digits):
            return (digits[a] if a else 1)*10 + (digits[b] if b else 0)
    return None


def _literal_support(text, condition, count):
    if condition == '恰好人数':
        return type(count) is int and any(_integer(m.group(1)) == count for m in _EXACT.finditer(text))
    if count is not None or condition not in _PATTERNS:
        return False
    if condition == '超过一半':
        # Do not accept a substring inside a non-strict upper bound.
        text = re.sub(r'(?:不超过|未超过)(?:一半|半数)', '', text)
    return bool(_PATTERNS[condition].search(text))


def project_evidence(bundle, raw):
    """Return an unchanged semantic candidate plus an auditable evidence receipt.

    Only the extra evidence object is removed for legacy schema compatibility.
    No source words are converted into model fields. A failure blocks dispatch
    for the whole candidate; per-question issues are retained for reading review.
    """
    issues = []
    def issue(qid, side, code):
        issues.append(dict(query_id=qid, field=side, reason_code=code))
    if (not isinstance(raw, dict) or set(raw) not in ({'questions'}, {'study', 'questions'})
            or not isinstance(raw.get('questions'), dict) or set(raw['questions']) != set(bundle['question_slots'])):
        return None, dict(passed=False, issues=[dict(reason_code='QUESTION_COVERAGE_INVALID')], semantic_proof=False)
    projected = deepcopy(raw)
    for qid, q in projected['questions'].items():
        if not isinstance(q, dict):
            issue(qid, None, 'QUESTION_OBJECT_REQUIRED'); continue
        evidence = q.pop('peer_evidence', None)
        if not isinstance(evidence, dict) or set(evidence) != {'first', 'second'}:
            issue(qid, None, 'PEER_EVIDENCE_PAIR_REQUIRED'); continue
        goal = bundle['question_slots'][qid]
        clauses = [x.strip() for x in _SPLIT.split(goal) if x.strip()]
        for side in ('first', 'second'):
            state, quote = q.get(side), evidence[side]
            if state is not None and not isinstance(state, dict):
                issue(qid, side, 'LOCAL_STATE_OBJECT_REQUIRED'); continue
            condition = state.get('neighbors') if state else None
            if condition in (None, '不明确'):
                if quote is not None:
                    issue(qid, side, 'UNASSERTED_CONDITION_REQUIRES_NULL_EVIDENCE')
                continue
            if not isinstance(quote, str) or not quote.strip():
                issue(qid, side, 'ASSERTED_CONDITION_REQUIRES_EVIDENCE'); continue
            # A complete question or complete clause is required; tiny fragments
            # cannot erase negation elsewhere in that same current question.
            if quote != goal and quote not in clauses:
                issue(qid, side, 'CURRENT_QUESTION_COMPLETE_QUOTE_REQUIRED'); continue
            if _UNSET.search(goal):
                issue(qid, side, 'NEGATED_OR_UNRESOLVED_CONDITION_REQUIRES_REVIEW'); continue
            if not _literal_support(quote, condition, state.get('neighbor_count')):
                issue(qid, side, 'PEER_PREDICATE_NOT_LITERAL_SUPPORTED')
    receipt = dict(version=VERSION, passed=not issues, issues=issues, semantic_proof=False,
        scope='current-question peer predicate only; no role/orientation/science proof',
        projection='remove evidence metadata only; preserve all semantic fields')
    return projected, receipt


def guarded_dispatch(bundle, raw, consumer):
    """Never invoke the selected entry (or its Core path) if evidence fails."""
    projected, receipt = project_evidence(bundle, raw)
    if not receipt['passed']:
        result = dict(state='READING_REVIEW_REQUIRED', reason_code='TARGET_CONDITION_EVIDENCE_REJECTED',
            core_called=False, candidate_model_calls=0, production_admission=False,
            estimation_called=False, policy_called=False, estimation_handoff_allowed=False,
            query_views=[], clarification_questions=[], semantic_candidate_accepted=False)
    else:
        result = consumer(projected)
    result = deepcopy(result)
    result.update(reading_prompt_version=VERSION, reading_candidate=deepcopy(raw), peer_evidence_review=receipt)
    return result
