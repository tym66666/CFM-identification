"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import json
from copy import deepcopy
import cfm_id.workflows.legacy_network.evidence_entries as entries
import cfm_id.workflows.legacy_network.staged_d1_d2 as staged


VERSION='business-frozen-reading-v0.55'


def make_request(bundle,entry,envelope=None):
    if entry=='D2_ARM' and envelope is not None:
        system,user=staged.target_request(bundle,entry,envelope)
    else:system,user=entries.make_request(bundle,entry,envelope)
    m=json.loads(user);question=m['output_schema']['$defs']['Question']
    if 'peer_scope' in question['properties']:
        question.setdefault('allOf',[]).append({
            'if':{'properties':{'peer_scope':{'const':'不适用'}},'required':['peer_scope']},
            'then':{'properties':{'operation':{'const':'选最优'},'first':{'type':'null'},'second':{'type':'null'}}}})
    system+='''
跨字段一致性：不明确表示所需信息尚未给出；不适用表示这种问题没有该字段。两者不能互换。
有局部情形的水平或差值问题，同伴范围未说明时peer_scope应为不明确，而非不适用；已经说清的范围仍须保留。
本入口仅选最优且first、second都为null时允许peer_scope=不适用。不要从同伴人数条件缺失推断范围缺失，反之亦然。
'''
    return system,json.dumps(m,ensure_ascii=False)


def cross_field_issues(raw):
    issues=[]
    if not isinstance(raw,dict) or not isinstance(raw.get('questions'),dict):return issues
    for qid,q in raw['questions'].items():
        if not isinstance(q,dict):continue
        if q.get('peer_scope')=='不适用' and not (q.get('operation')=='选最优' and q.get('first') is None and q.get('second') is None):
            issues.append(dict(query_id=qid,field='peer_scope',reason_code='UNKNOWN_SCOPE_IS_NOT_INAPPLICABLE'))
    return issues


def identify(bundle,raw,entry,envelope=None):
    issues=cross_field_issues(raw)
    if issues:
        return dict(version=VERSION,state='READING_REVIEW_REQUIRED',core_called=False,reading_candidate=deepcopy(raw),
            cross_field_issues=issues,query_views=[],candidate_model_calls=0,production_admission=False,
            estimation_called=False,policy_called=False,estimation_handoff_allowed=False)
    if entry=='D2_ARM' and envelope is not None:r=staged.identify(bundle,entry,envelope,raw)
    else:r=entries.identify(bundle,raw,entry,envelope)
    r.update(frozen_reading_version=VERSION,cross_field_issues=[])
    return r
