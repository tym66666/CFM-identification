"""Source-preserving D1 target replies; no target coordinates or approvals."""
from copy import deepcopy

KIND = 'D1_SESSION_TARGET_REPLY'
FIELDS = {'kind', 'query_id', 'parent_active_goal_document', 'active_goal_document', 'reply_document'}


def original_goal_text(bundle):
    """Validate an additive document chain before indexing the original questions.

    D1 sources for target fields must be in the active goal document. A new active
    copy contains the prior text plus the verbatim follow-up. Question marks in
    that follow-up are material for rereading, not newly invented question slots.
    """
    docs = bundle['documents']
    records = bundle.get('question_clarifications', [])
    if not isinstance(records, list):
        raise ValueError('D1_REPLY_DOCUMENT_CHAIN_REQUIRED')
    if not records or not any(isinstance(r, dict) and r.get('kind') == KIND for r in records):
        return docs[bundle['active_goal_document']]
    if any(not isinstance(r, dict) or set(r) != FIELDS or r['kind'] != KIND or
           any(not isinstance(v, str) or not v.strip() for v in r.values()) for r in records):
        raise ValueError('D1_REPLY_DOCUMENT_CHAIN_REQUIRED')
    first = records[0]['parent_active_goal_document']
    cursor = first
    seen = {first}
    for row in records:
        previous, active, reply = (row[k] for k in
            ('parent_active_goal_document', 'active_goal_document', 'reply_document'))
        if (previous != cursor or active in seen or reply in seen or active == reply or
                row['query_id'] not in bundle['question_slots'] or
                any(name not in docs for name in (previous, active, reply)) or
                docs[active] != docs[previous] + '\n' + docs[reply]):
            raise ValueError('D1_REPLY_DOCUMENT_CHAIN_CHANGED')
        seen.update((active, reply))
        cursor = active
    if cursor != bundle['active_goal_document']:
        raise ValueError('D1_REPLY_ACTIVE_DOCUMENT_CHANGED')
    return docs[first]


def append_target_reply(bundle, query_id, document_id, text):
    """Keep original source files and question slots; create a citable active copy."""
    original_goal_text(bundle)
    result = deepcopy(bundle)
    active = document_id.removesuffix('.txt') + '_goals.txt'
    if query_id not in result['question_slots'] or any(
            name in result['documents'] for name in (document_id, active)):
        raise ValueError('CURRENT_QUERY_AND_NEW_REPLY_DOCUMENTS_REQUIRED')
    previous = result['active_goal_document']
    result['documents'][document_id] = ('【针对业务问题 ' + query_id + '：' +
        result['question_slots'][query_id] + '】\n' + text)
    result['documents'][active] = result['documents'][previous] + '\n' + result['documents'][document_id]
    result['active_goal_document'] = active
    result.setdefault('question_clarifications', []).append(dict(kind=KIND, query_id=query_id,
        parent_active_goal_document=previous, active_goal_document=active, reply_document=document_id))
    original_goal_text(result)
    return result
