"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.question_intent_base as base


VERSION='business-question-intent-v0.56.1'


def make_request(bundle,entry,envelope=None):
    system,user=base.make_request(bundle,entry,envelope)
    m=json.loads(user);schema=m['output_schema']
    for qid in bundle['question_slots']:
        for kind,sides in [('比较',('first','second')),('水平',('first',))]:
            schema.setdefault('allOf',[]).append({
                'if':{'properties':{'intents':{'properties':{qid:{'properties':{'kind':{'const':kind}}}}}}},
                'then':{'properties':{'questions':{'properties':{qid:{'properties':{
                    side:{'$ref':'#/$defs/Local'} for side in sides}}}}}}})
    system+='''
部分条件用对象保留：比较问题的first、second必须都是Local对象；水平问题的first必须是Local对象。
即使两端的具体同伴人数未决定，也填neighbors=不明确、neighbor_count=null，不把整个情形设为null。
如果本人状态已明确且适用于整项比较，两端都保留该本人状态；如果也未知，两端own=不明确。
这是未知坐标的占位，不是替用户决定比较两端、相减方向或补全事实。不要根据过去分组填未知邻居条件。
水平的second仍为null。只有问题类型不适用的情形才用null。
'''
    return system,json.dumps(m,ensure_ascii=False)


def project_intents(bundle,raw):
    projected,receipt=base.project_intents(bundle,raw)
    for qid,intent in raw['intents'].items():
        sides=('first','second') if intent['kind']=='比较' else ('first',) if intent['kind']=='水平' else ()
        if any(not isinstance(raw['questions'][qid].get(s),dict) for s in sides):
            raise ValueError('PARTIAL_CONDITION_OBJECT_REQUIRED')
    return projected,receipt


def identify(bundle,raw,entry,envelope=None):
    try:project_intents(bundle,raw)
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(version=VERSION,state='READING_REVIEW_REQUIRED',reason_code='INTENT_OR_PARTIAL_CONDITION_INVALID',
            reading_candidate=deepcopy(raw),core_called=False,candidate_model_calls=0,estimation_called=False,
            policy_called=False,production_admission=False,estimation_handoff_allowed=False,intent_condition_review={})
    r=base.identify(bundle,raw,entry,envelope);r['version']=VERSION
    return r
