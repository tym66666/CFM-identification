"""Task 05: the reading path, from a plain business description to a checked result.

Run from the repository root after setting CFM_ID_LLM_API_KEY:

    python examples/dag_id_llm_reading.py

Without a key the script prints what is missing and exits, exactly like the other
online entries in this repository: it never sends material anywhere by accident.

The expected outcome of every case is written down here before the model runs.
The prompt asks for a reading, not for an answer; the identification result comes
from the solver and is replayed by the independent checker.

Each run writes one JSON record per case to dagid_runs/ (override with
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
from cfm_id.dag_id_route import DagGeneralIdRoute, GeneralIdProblem, GeneralIdReview, digest
from cfm_id.research_route_workflow import run_route
from cfm_id_bridge.scientific_binding import sha


CASES = {
    # Expected: POINT. The material names a mediator and says the unmeasured
    # factor reaches both the treatment and the outcome, which is a front-door
    # graph; the formula must keep the mediator and sum the treatment out.
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
        expected='POINT',
    ),
    # Expected: UNSUPPORTED. A direct arrow plus a shared unmeasured cause and no
    # mediator at all: the bow arc. The evidence has to pass its own checks.
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
        expected='UNSUPPORTED',
    ),
    # Expected: NEEDS_INPUT. The outcome measure is still being argued about and
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
        expected='NEEDS_INPUT',
    ),
}


def bundle_for(case_id, case):
    return dict(case_id=case_id, documents=case['documents'], question=case['question'])


def save_directory():
    override = os.getenv('CFM_ID_LLM_SAVE_DIR')
    return Path(override) if override else Path(__file__).resolve().parent.parent / 'dagid_runs'


def save(record):
    """Write one record; failing to keep a log must not hide the result above it."""
    directory = save_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (record['case_id'] + '.json')
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


def review_for(problem):
    """A synthetic review record: this is a test path, not a research opinion."""
    return GeneralIdReview(
        version='dag-general-id-1', problem_sha256=digest(problem),
        reviewer='synthetic test reviewer',
        evidence='synthetic review used only by this walkthrough, not a research opinion',
        authority='SYNTHETIC_TEST',
        decisions={name: 'ACCEPTED' for name in DECISIONS},
    )


def confirmation(reading):
    """What the walkthrough may confirm, and what has to be asked first.

    The reading is a draft. Confirming it means asserting that this graph is the
    right causal graph for the population - a statement about the world, not
    about the document. A draft that extracted no relation at all is asserting
    that the population has no causal structure, which is the strongest claim of
    all and the least likely to be supported; it cannot be rubber-stamped here.
    """
    graph = declared_graph(reading)
    if not graph['directed'] and not graph['bidirected']:
        return False, 'NO_CAUSAL_STRUCTURE_READ'
    return True, None


def run_case(provider, case_id, case):
    """Run one case and keep a record of it, including the cases that stop early."""
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
    record['observed'] = state
    record['as_expected'] = state == case['expected']
    save(record)
    return state


def _run(provider, case_id, case, record):
    bundle = bundle_for(case_id, case)
    print('=' * 72)
    print(case_id, '| expected:', case['expected'])

    request = make_request(bundle)
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
    record['first_answer'] = wire
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

    confirmable, blocker = confirmation(reading)
    record['confirmation'] = {'confirmed': confirmable, 'blocker': blocker}
    if not confirmable:
        # Stopping here is the point of the gate: a draft nobody can confirm must
        # not be turned into a formula by the caller filling in the blanks.
        print('confirm  : NEEDS_INPUT', blocker)
        for note in reading.unresolved:
            print('  ask    :', note.text)
        return 'NEEDS_INPUT'

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
    record['review'] = {'authority': 'SYNTHETIC_TEST',
                        'note': 'synthetic review used only by this walkthrough, '
                                'not a research opinion'}
    result = run_route(DagGeneralIdRoute(), problem, review=review_for(problem),
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
