"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import re
import cfm_id.workflows.legacy_network.condition_evidence_base as prior


VERSION='business-condition-evidence-v0.55.1'


_NUMBERING=re.compile(r'^问题(?:[0-9]+|[一二三四五六七八九十]+)[：:]\s*')


def project_evidence(bundle,raw):
    validation=deepcopy(raw);normalizations=[]
    if isinstance(validation,dict) and isinstance(validation.get('questions'),dict):
        for qid,q in validation['questions'].items():
            if not isinstance(q,dict) or not isinstance(q.get('peer_evidence'),dict):continue
            goal=bundle['question_slots'].get(qid)
            if not isinstance(goal,str):continue
            match=_NUMBERING.match(goal)
            if not match:continue
            unnumbered=goal[match.end():]
            for side,quote in q['peer_evidence'].items():
                if quote==unnumbered:
                    normalizations.append(dict(query_id=qid,field=side,raw_quote=quote,ignored_numbering=match.group()))
                    q['peer_evidence'][side]=goal
    projected,receipt=prior.project_evidence(bundle,validation)
    receipt.update(version=VERSION,quote_format_normalizations=normalizations,
        normalization_scope='question numbering only; no semantic words removed or added to the raw candidate')
    return projected,receipt


def guarded_dispatch(bundle,raw,consumer):
    projected,receipt=project_evidence(bundle,raw)
    if receipt['passed']:result=consumer(projected)
    else:result=dict(state='READING_REVIEW_REQUIRED',reason_code='TARGET_CONDITION_EVIDENCE_REJECTED',
        core_called=False,candidate_model_calls=0,production_admission=False,estimation_called=False,
        policy_called=False,estimation_handoff_allowed=False,query_views=[],semantic_candidate_accepted=False)
    result=deepcopy(result)
    result.update(reading_prompt_version=VERSION,reading_candidate=deepcopy(raw),peer_evidence_review=receipt)
    return result
