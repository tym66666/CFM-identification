"""Task 05: the reading path, from a plain business description to a checked result.

Run from the repository root after setting CFM_ID_LLM_API_KEY:

    python examples/dag_id_llm_reading.py

Without a key the script prints what is missing and exits, exactly like the other
online entries in this repository: it never sends material anywhere by accident.

The expected outcome of every case is written down here before the model runs.
The prompt asks for a reading, not for an answer; the identification result comes
from the solver and is replayed by the independent checker.

No graph or scientific condition is automatically approved. Without a separately
supplied approved_graph and digest-bound review, the walkthrough stops for review.
The historical narratives are not certified positive mathematical fixtures.

Each run writes a uniquely named JSON record per case to outputs/dag_id_reading/ (override with
CFM_ID_LLM_SAVE_DIR): the material as sent, the model's verbatim reply, the parsed
reading, the final state and the transport diagnostics for that call. Those records
are the de-identified input/output the review asked to keep locally. They are run
products, not deliverables, and are excluded from version control.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cfm_id_llm.dag_id_reading import declared_graph, make_request, parse, to_problem
from cfm_id_llm.dag_reading import ReadingError, Scope
from cfm_id_llm.providers.base import ProviderError
from cfm_id.dag_backdoor_contract import DECISIONS
from cfm_id.dag_id_route import (DagGeneralIdRoute, GeneralIdProblem, GeneralIdReview,
                                 UnresolvedResponse, digest)
from cfm_id.research_route_workflow import run_route
from cfm_id_bridge.scientific_binding import sha


CASES = {
    # Historical input retained verbatim. Its common cause is M<->Y, NOT
    # X<->Y, and it lacks a complete finite-model declaration/review. This is
    # a reading/clarification exercise, not certified front-door acceptance.
    'frontdoor': dict(
        documents={
            'brief': (
                '某连锁咖啡品牌想评估新品推荐活动对会员当月是否复购的影响。'
                '活动是否触达由运营按门店排期决定，没有随机分配。'
                '顾客先是否注意到这次推荐，用的是我们叫“活动感知”的指标，再决定是否复购。'
                '市场部认为，“门店客流基础”这个因素同时影响顾客是否注意到推荐和是否复购，'
                '但这个指标我们门店层面没有测量记录，只有门店经理的定性印象。'
                '如果强制给所有会员推送这次推荐活动，我们想知道当月复购比例的分布。'
                '我们假定活动只通过“活动感知”影响复购，没有别的直接渠道。'
            ),
            'data_note': (
                '数据是 2026 年 3 月到 5 月的会员消费明细，覆盖全部 42 家门店、18 万名会员，'
                '没有抽样，分析时按该总体的完整联合分布使用。'
            ),
        },
        question='强制给所有会员推送推荐活动后，会员当月是否复购的分布是什么？',
        expected='REVIEW_REQUIRED',
    ),
    # Historical bow-shaped narrative; no independent review is supplied.
    # The business amount is not silently converted to a finite variable.
    'unidentifiable': dict(
        documents={
            'brief': (
                '某电商想评估优惠券发放对用户下单金额的影响。运营只在部分用户发券，没有随机。'
                '风控部门指出，“用户消费能力”这个因素我们从来没有测量过，'
                '它同时决定用户会不会被发券，也决定下单金额。'
                '除了发券本身，没有任何介于发券和下单之间的中间行为被记录。'
                '我们想要的是：如果强制给所有用户发券，下单金额的分布。'
            ),
            'data_note': (
                '数据是 2026 年上半年的订单流水，覆盖全部注册用户，'
                '分析时按该总体的完整联合分布使用。'
            ),
        },
        question='强制给所有用户发券后，下单金额的分布是什么？',
        expected='REVIEW_REQUIRED',
    ),
    # Unreviewed input. The outcome measure is still being argued about and
    # the material contradicts itself, so the run must ask instead of guessing.
    'missing_conditions': dict(
        documents={
            'brief': (
                '我们想评估新的排班方式对门店表现的影响。门店表现我们还在讨论，'
                '销售额、客单价、人效三个口径都有人提，目前没有定下来。'
                '排班方式会不会影响店长自己安排班次的自由度，运营和人力给的说明也不一致，'
                '一边说有影响，一边说没有。'
                '如果能确认，我们想知道把排班方式统一换成新方案之后会变成什么样。'
            ),
        },
        question='把门店排班方式统一换成新方案后，门店表现会怎样？',
        expected='REVIEW_REQUIRED',
    ),
}


def bundle_for(case_id, case):
    return dict(case_id=case_id, documents=case['documents'], question=case['question'])


def save_directory():
    override = os.getenv('CFM_ID_LLM_SAVE_DIR')
    return Path(override) if override else Path(__file__).resolve().parent.parent / 'outputs' / 'dag_id_reading'


def save(record):
    """Write one record; failing to keep a log must not hide the result above it."""
    directory = save_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4
        path = directory / (record['case_id'] + '_' + uuid4().hex[:12] + '.json')
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + '\n',
                        encoding='utf-8')
    except (OSError, TypeError, ValueError) as error:
        print('saved    : FAILED', error)
        return None
    print('saved    :', path)
    return path


def diagnostics(provider):
    """Counters the transport already allowlists; never credentials, never content."""
    observed = getattr(provider, 'last_diagnostics', None)
    return dict(observed) if isinstance(observed, dict) else {}


def redact(text, provider):
    """Transport messages may echo the request; the key must not reach the log."""
    key = getattr(provider, 'api_key', None)
    if isinstance(key, str) and key and key in text:
        text = text.replace(key, '***')
    return text[:600]


def _available_models(base_url, key):
    """Ask the gateway which models it serves; no request is sent to a model."""
    import urllib.request
    request = urllib.request.Request(
        base_url.rstrip('/') + '/models', headers={'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return [entry['id'] for entry in payload.get('data', []) if entry.get('id')]


def online_provider():
    """Build the configured provider, or explain what is missing and stop."""
    key = os.getenv('CFM_ID_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key:
        print('CFM_ID_LLM_API_KEY is not set.')
        print('Set it in your own shell, then rerun this script:')
        print('   export CFM_ID_LLM_API_KEY=<your token>')
        print('   export CFM_ID_LLM_BASE_URL=https://api.deepseek.com/v1   (any OpenAI-compatible endpoint)')
        print('   export CFM_ID_LLM_MODEL=deepseek-chat   (skips model discovery)')
        print('Nothing was sent anywhere.')
        return None
    base_url = os.getenv('CFM_ID_LLM_BASE_URL', 'https://newapi.sufe.edu.cn/v1')
    model = os.getenv('CFM_ID_LLM_MODEL')
    if not model:
        try:
            served = _available_models(base_url, key)
        except Exception as error:
            print('Could not list models at {}: {}'.format(base_url, error))
            print('Set CFM_ID_LLM_MODEL explicitly and rerun.')
            return None
        if not served:
            print('The gateway returned no model list; set CFM_ID_LLM_MODEL explicitly.')
            return None
        model = served[0]
        print('gateway serves {} models; using {}'.format(len(served), model))
        print('available:', ', '.join(served[:10]))
    from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
    print('endpoint : {} | model: {}'.format(base_url, model))
    # The gateway serves reasoning models: a full reading answer takes far
    # longer than a one-line reply, so the default 60s budget is too tight for
    # this walkthrough. The bound is still finite and no retry is attempted.
    timeout = float(os.getenv('CFM_ID_LLM_TIMEOUT', '180'))
    # Some OpenAI-compatible endpoints reject response_format json_object. The
    # switch exists so that case can be tested without editing the provider;
    # local schema validation still applies either way.
    json_mode = os.getenv('CFM_ID_LLM_JSON_MODE', '1').lower() not in ('0', 'false', 'no')
    return OpenAICompatibleChatProvider(model=model, base_url=base_url, timeout=timeout,
                                        json_mode=json_mode)


def _respond_to(text):
    """Compatibility helper: a note is never a scientific approval."""
    return UnresolvedResponse(
        item=text, decision='UNRESOLVED',
        reason='需要独立审核者根据实际材料回应；程序不按关键词替研究者作决定。')


def review_for(problem, supplied_review=None):
    """Accept only a separately supplied typed review; default stays pending.

    The route checks the exact problem digest and every scientific decision.
    Synthetic callers may supply a frozen reference review, but the model's
    answer is never the source of its own approval.
    """
    if supplied_review is not None:
        return GeneralIdReview.model_validate(supplied_review)
    return GeneralIdReview(
        version='dag-general-id-1', problem_sha256=digest(problem),
        reviewer='pending independent reviewer',
        evidence='No independent scientific approval has been supplied for this candidate.',
        authority='EXTERNAL_RESEARCH_REVIEW',
        decisions={name: 'PENDING' for name in DECISIONS},
        unresolved_responses=[_respond_to(text) for text in problem.unresolved],
        restriction_responses=[_respond_to(text) for text in problem.additional_restrictions])


def confirmation(reading, approved_graph=None):
    """Match an independently approved graph, including a genuinely empty graph."""
    if approved_graph is None:
        return False, 'INDEPENDENT_GRAPH_CONFIRMATION_REQUIRED'
    graph = declared_graph(reading)
    def normal(g):
        return (sorted(g['nodes']), sorted(tuple(e) for e in g['directed']),
                sorted(tuple(sorted(e)) for e in g['bidirected']))
    if normal(graph) != normal(approved_graph):
        return False, 'READING_DIFFERS_FROM_APPROVED_GRAPH'
    return True, None


def run_case(provider, case_id, case):
    """Run one case and keep a record of it, including the cases that stop early.

    Two calls at most: the first answer, then -- only when the first answer
    failed a structural check -- one re-read whose user prompt carries the
    validator's own message. Both answers are recorded. The re-read is the
    "复查" column of the walkthrough table; it corrects form, never the
    question, and it is not performed for stops that are legitimate outcomes
    (a material with no causal structure, an open question for the researcher,
    a verified non-identification) -- asking again there would just be
    pressure to change an answer that was already right.
    """
    record = {
        'case_id': case_id,
        'expected': case['expected'],
        'question': case['question'],
        'documents': case['documents'],
        'run_at': time.strftime('%Y-%m-%d %H:%M:%S %z'),
        'provider': {'name': provider.name, 'base_url': provider.base_url,
                     'model': provider.model},
    }
    state = _run(provider, case_id, case, record)
    trigger = _reread_trigger(state, record)
    if trigger:
        record['first_attempt'] = {
            'state': state,
            'reason_code': record.get('reason_code'),
            'reading_rejected': record.get('reading_rejected'),
            'reading_audit': record.get('reading_audit'),
        }
        feedback = ('你上一次的回答没有通过结构检查：{}。'
                    '请重新阅读材料原文，修正该问题后给出完整回答；'
                    '只有材料本身确实没有依据时才维持原判。'.format(trigger))
        record['reread'] = {'performed': True, 'trigger': trigger,
                            'feedback': feedback}
        print('-- reread :', trigger)
        state = _run(provider, case_id, case, record, feedback=feedback)
    record['observed'] = state
    record['as_expected'] = state == case['expected']
    record.setdefault('reread', {'performed': False,
                                 'reason': 'the run stopped before an answer was usable'})
    record.setdefault('outcome', {'state': state, 'reason_code': record.get('reason_code')})
    save(record)
    return state


def _reread_trigger(state, record):
    """The one-line reason for a re-read, or None when the first answer stands.

    Only two kinds of stop mean the model misread the material's form: a
    reading the parser rejected, and an information status the material's own
    data note should have settled. Everything else is either a legitimate
    result or a question only a researcher can answer.
    """
    if state == 'READING_REJECTED':
        return record.get('reading_rejected')
    return None


def _run(provider, case_id, case, record, feedback=None):
    bundle = bundle_for(case_id, case)
    print('=' * 72)
    print(case_id, '| expected:', case['expected'],
          '| re-read' if feedback else '| first answer')

    request = make_request(bundle)
    if feedback:
        request = dict(request, user=request['user'] + '\n\n' + feedback)
    # Which prompt produced this answer, by digest rather than by copy: the
    # record should be able to answer "same prompt as last time?" without
    # carrying the whole text. The contract name ties it to
    # cfm_id_llm/dag_id_reading.SYSTEM, which is this route's own reading
    # contract, not the shared target-first Skill (see docs/DAG_ID_MATH_ZH.md 7).
    answer_key = 'first_answer' if feedback is None else 'reread_answer'
    record['prompt' if feedback is None else 'reread_prompt'] = {
        'contract': 'dag-id-reading-1',
        'system_sha256': sha(request['system']),
        'system_characters': len(request['system']),
        'user_characters': len(request['user'])}
    started = time.monotonic()
    try:
        wire = provider.generate_json(system_prompt=request['system'],
                                      user_prompt=request['user'])
    except ProviderError as error:
        # A transport or protocol failure is its own outcome, not a reading
        # problem and not a missing input. Print the bounded diagnostics so the
        # cause can be told apart without reading the model's content.
        print('provider : FAILED', error.code or 'UNSPECIFIED', '|', error)
        print('elapsed  : {:.1f}s'.format(time.monotonic() - started))
        for name, value in sorted((error.diagnostics or {}).items()):
            print('           {} = {}'.format(name, value))
        record['answer_seconds'] = round(time.monotonic() - started, 3)
        record['provider_error'] = {'code': error.code or 'UNSPECIFIED',
                                    'message': redact(str(error), provider),
                                    'raised_diagnostics': dict(error.diagnostics or {})}
        record['transport'] = diagnostics(provider)
        return 'PROVIDER_ERROR'
    record['answer_seconds'] = round(time.monotonic() - started, 3)
    record[answer_key] = wire
    record['transport'] = diagnostics(provider)
    print('answered : {:.1f}s, {} characters'.format(
        record['answer_seconds'], len(json.dumps(wire, ensure_ascii=False))))
    receipt = record['transport']
    if 'returned_model' in receipt or 'usage' in receipt:
        print('receipt  :', receipt.get('returned_model'), receipt.get('usage'),
              '| finish:', receipt.get('finish_reason'))
    try:
        reading = parse(bundle, wire)
    except ReadingError as error:
        print('reading  : REJECTED', error)
        record['reading_rejected'] = redact(str(error), provider)
        return 'READING_REJECTED'
    record['reading'] = reading.model_dump(mode='json')
    print('variables:', [(v.name, v.observation, v.domain) for v in reading.variables])
    print('directed :', [(r.cause, r.effect, r.kind) for r in reading.relations])
    print('shared   :', [(c.first, c.second) for c in reading.common_causes])
    print('target   :', reading.target.kind, reading.target.treatment, '->',
          reading.target.outcome)
    print('scope    :', {name: getattr(reading.scope, name) for name in Scope.model_fields})
    for note in reading.unresolved:
        print('unresolved:', note.text)

    confirmable, blocker = confirmation(reading, case.get('approved_graph'))
    record['confirmation'] = {'confirmed': confirmable, 'blocker': blocker}
    if not confirmable:
        # Stopping here is the point of the gate: a draft nobody can confirm must
        # not be turned into a formula by the caller filling in the blanks.
        print('confirm  : REVIEW_REQUIRED', blocker)
        record['reason_code'] = blocker
        for note in reading.unresolved:
            print('  ask    :', note.text)
        return 'REVIEW_REQUIRED'

    try:
        declared = to_problem(
            reading,
            graph_source='researcher-confirmed reading of the material in this example',
            materials_sha256=sha(bundle),
            researcher_confirmed=True,
        )
    except ReadingError as error:
        print('problem  : NEEDS_INPUT', error)
        record['problem_rejected'] = redact(str(error), provider)
        return 'NEEDS_INPUT'

    problem = GeneralIdProblem(**declared)
    record['problem'] = problem.model_dump(mode='json')

    # The comment above still holds for information and additional_restrictions:
    # those stop here. Undecided items now travel to the review, which must
    # answer each one explicitly; the answers are recorded below next to the
    # items they answer.
    route = DagGeneralIdRoute()
    review = review_for(problem, case.get('review'))
    gate = run_route(route, problem, review=None, research_protocol_selected=False)
    worksheet = gate.get('worksheet') or {}
    questions = list(worksheet.get('clarification_questions') or [])
    record['reading_audit'] = {
        'state': gate['state'],
        'reason_code': gate.get('reason_code'),
        'information': problem.information,
        'unresolved': list(problem.unresolved),
        'additional_restrictions': list(problem.additional_restrictions),
        'clarification_questions': questions,
    }
    print('gate     :', gate['state'], '|', gate.get('reason_code'))
    for question in questions:
        print('  ask    :', question)
    if gate['state'] != 'REVIEW_REQUIRED':
        record['reason_code'] = gate.get('reason_code')
        return gate['state']

    for response in review.unresolved_responses + review.restriction_responses:
        print('  review : {} -> {}'.format(response.decision, response.item))
        print('           {}'.format(response.reason))
    record['review'] = {'authority': review.authority, 'human_review': False,
                        'note': 'Separately supplied review, or pending independent review; '
                                'not inferred from the model response.',
                        'decisions': dict(review.decisions),
                        'unresolved_responses': [
                            response.model_dump(mode='json')
                            for response in review.unresolved_responses],
                        'restriction_responses': [
                            response.model_dump(mode='json')
                            for response in review.restriction_responses]}
    result = run_route(route, problem, review=review,
                       research_protocol_selected=True)
    print('state    :', result['state'], '|', result.get('reason_code'))
    print('replay   :', result['independent_replay'])
    record['reason_code'] = result.get('reason_code')
    record['independent_replay'] = result['independent_replay']
    certificate = result.get('certificate')
    if certificate:
        print('formula  :', json.dumps(certificate['functional'], ensure_ascii=False)[:200])
        record['certificate'] = certificate
    witness = (result.get('native_result') or {}).get('witness')
    if witness:
        print('evidence :', witness.get('means'),
              '| materialised:', witness.get('hedge_materialised'))
        record['witness'] = witness
    native = result.get('native_result') or {}
    # The review asked for four things per case: first answer, re-read, review
    # result, and the final identification result. The fourth is this block. A
    # re-read, when one happened, was already recorded by the caller; here it
    # is only recorded as not performed rather than left to inference, because
    # a second call is a different observation and is not merged into this one.
    if feedback is None:
        record['reread'] = {'performed': False,
                            'reason': 'first answer used as-is; a re-read is a separate call'}
    record['outcome'] = {'state': result['state'],
                         'reason_code': result.get('reason_code'),
                         'independent_replay': result['independent_replay'],
                         'nonidentification_proved': native.get('nonidentification_proved',
                                                                 False)}
    return result['state']


def main():
    # Progress must be visible while the model call is still running: when the
    # output is redirected to a file, an unflushed buffer looks like a hang.
    sys.stdout.reconfigure(line_buffering=True)
    provider = online_provider()
    if provider is None:
        return 2
    observed = {}
    for case_id, case in CASES.items():
        observed[case_id] = run_case(provider, case_id, case)
    print('=' * 72)
    for case_id, case in CASES.items():
        got = observed[case_id]
        print('{:<20} expected {:<12} got {:<12} {}'.format(
            case_id, case['expected'], got, 'as expected' if got == case['expected'] else 'DIFFERS'))
    print('records  :', save_directory())
    return 0


if __name__ == '__main__':
    sys.exit(main())
