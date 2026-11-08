"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.frozen_reading as previous


VERSION = 'business-question-intent-v0.56'


OPERATIONS = {'比较': '差值', '水平': '水平', '选最优': '选最优', '不明确': '不明确'}


INSTRUCTION = '''
本次输出把“想问什么”与“条件给全了吗”分开，按新的output_schema返回：
1. 先写intents：每问一个kind和quote。quote完整照抄该question_slots原句。
kind=比较：问改变、影响、提高/降低或两个情形之差；即使比较哪两种情形、同伴人数或方向未说明，比较意图仍可明确。
kind=水平：只问某一情形下结果的均值/水平。kind=选最优：要求选择最好的安排。
kind=不明确：用户连要问哪种问题都未确定；不能仅因条件不齐就填不明确。
2. 再写questions中的具体条件；这里不再输出operation，程序仅按intents.kind映射旧字段。
比较问题可以有未知的first/second；已知的本人状态、评价人群仍保留，未知的同伴人数、顺序、安排规则保持不明确或null。
不能因为已确定比较意图，就自动补出“多数减少数”“使用减不使用”或原抽签安排。
如果只是问“有没有影响”，但没有确定两端条件，不是已经定义完整差值，不能进入识别。
水平问题不能为了凑两种情形而生成基线。真正未明确的意图也不能强行当比较。
所有旧operation规则仅作用于intents.kind映射后的内部表示；不得在questions重复operation。
此分离不判断因果假设、不生成数学证明，也不改变研究设计；缺项状态由程序根据字段检查。
'''


def make_request(bundle, entry, envelope=None):
    system, user = previous.make_request(bundle, entry, envelope)
    message = json.loads(user)
    schema = message['output_schema']
    question = schema['$defs']['Question']
    question['properties'].pop('operation')
    question['required'].remove('operation')
    # The original cross-field rule is still checked after exact projection.
    question.pop('allOf', None)
    intent = dict(type='object', additionalProperties=False, required=['kind', 'quote'],
                  properties=dict(kind=dict(type='string', enum=list(OPERATIONS)),
                                  quote=dict(type='string', minLength=1)))
    schema['properties'] = {'intents': dict(type='object', additionalProperties=False,
        required=list(bundle['question_slots']), properties={q: deepcopy(intent) for q in bundle['question_slots']}),
        **schema['properties']}
    schema['required'].insert(0, 'intents')
    return system + INSTRUCTION, json.dumps(message, ensure_ascii=False)


def project_intents(bundle, raw):
    if not isinstance(raw, dict) or set(raw) not in ({'intents', 'questions'}, {'intents', 'study', 'questions'}):
        raise ValueError('SEPARATE_INTENT_OBJECT_REQUIRED')
    qids = set(bundle['question_slots'])
    if (not isinstance(raw['intents'], dict) or not isinstance(raw['questions'], dict)
            or set(raw['intents']) != qids or set(raw['questions']) != qids):
        raise ValueError('INTENT_AND_CONDITION_COVERAGE_MISMATCH')
    projected = deepcopy(raw)
    intents = projected.pop('intents')
    receipt = {}
    for qid, intent in intents.items():
        if (not isinstance(intent, dict) or set(intent) != {'kind', 'quote'}
                or intent['kind'] not in OPERATIONS
                or intent['quote'] != bundle['question_slots'][qid]):
            raise ValueError('CURRENT_QUESTION_INTENT_REQUIRED')
        q = projected['questions'][qid]
        if not isinstance(q, dict) or 'operation' in q:
            raise ValueError('DUPLICATE_OR_INVALID_OPERATION')
        q['operation'] = OPERATIONS[intent['kind']]
        missing = []
        if intent['kind'] in ('比较', '水平'):
            for name in ('first', 'second') if intent['kind'] == '比较' else ('first',):
                state = q.get(name)
                if state is None:
                    missing.append(name)
                elif isinstance(state, dict):
                    for field in ('own', 'neighbors'):
                        if state.get(field) in (None, '不明确'):
                            missing.append(name + '.' + field)
                    if state.get('neighbors') == '恰好人数' and state.get('neighbor_count') is None:
                        missing.append(name + '.neighbor_count')
            if (q.get('population') or {}).get('selection') in (None, '不明确'):
                missing.append('population')
            if q.get('aggregation') in (None, '不明确'):
                missing.append('aggregation')
            if 'peer_scope' in q and q['peer_scope'] == '不明确':
                missing.append('peer_scope')
            if 'remaining' in q:
                if q['remaining'].get('rule') == '未确定': missing.append('remaining')
            elif q.get('remaining_source') is None:
                missing.append('remaining')
        receipt[qid] = dict(intent=deepcopy(intent), missing_conditions=missing,
            coordinate_status=('NOT_ASSESSED' if intent['kind'] in ('选最优', '不明确')
                               else 'INCOMPLETE' if missing else 'COMPLETE_REQUIRES_REVIEW'),
            scientific_approval=False)
    return projected, receipt


def identify(bundle, raw, entry, envelope=None):
    try:
        projected, receipt = project_intents(bundle, raw)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(version=VERSION, state='READING_REVIEW_REQUIRED', reason_code='INTENT_CONTRACT_INVALID',
            reading_candidate=deepcopy(raw), core_called=False, candidate_model_calls=0,
            estimation_called=False, policy_called=False, production_admission=False,
            estimation_handoff_allowed=False, intent_condition_review={})
    result = previous.identify(bundle, projected, entry, envelope)
    result.update(version=VERSION, reading_candidate=deepcopy(raw), projected_reading=projected,
                  intent_condition_review=receipt,
                  projection='intent_enum_to_operation_only; no filled coordinates',
                  evidence_is_semantic_proof=False)
    return result
