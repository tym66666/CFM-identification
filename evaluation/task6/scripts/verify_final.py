"""Score saved project outcomes against a separately authored case reference.

This is an evidence gate, not a substitute for independent semantic review or
mathematical verification. It never infers success from a reviewer checkbox.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from cfm_id_bridge.scientific_binding import sha as project_sha


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def verify(outcome, reference):
    expected=reference['expected_state']
    state=outcome.get('state')
    claim=outcome.get('mathematical_claim')
    replay=outcome.get('independent_replay') is True
    called=outcome.get('backend_called') is True
    certificate=outcome.get('certificate')
    reasons=[]
    if expected in ('POINT','PARTIAL','PROVEN_NON_POINT'):
        required_state='PARTIAL' if expected=='PROVEN_NON_POINT' else expected
        if state!=required_state:reasons.append('EXPECTED_MATHEMATICAL_STATE_NOT_REACHED')
        if not called:reasons.append('BACKEND_NOT_CALLED')
        if not replay:reasons.append('CERTIFICATE_REPLAY_NOT_RECORDED')
        if not isinstance(certificate,dict) or not certificate:reasons.append('CERTIFICATE_MISSING')
        elif certificate.get('status')!=required_state:
            reasons.append('CERTIFICATE_STATE_MISMATCH')
        elif not certificate.get('certificate_sha256'):
            reasons.append('CERTIFICATE_DIGEST_MISSING')
        elif required_state=='POINT' and certificate.get('verification_status')!='VERIFIED':
            reasons.append('POINT_CERTIFICATE_NOT_VERIFIED')
        elif required_state=='PARTIAL':
            if certificate.get('certificate_sha256') != project_sha({k:v for k,v in certificate.items() if k!='certificate_sha256'}):
                reasons.append('CERTIFICATE_DIGEST_MISMATCH')
            if isinstance(claim,dict) and claim.get('interval') != [certificate.get('lower'),certificate.get('upper')]:
                reasons.append('CERTIFICATE_INTERVAL_MISMATCH')
        if not isinstance(claim,dict) or claim.get('kind')!=required_state:
            reasons.append('MATHEMATICAL_CLAIM_MISSING_OR_WRONG')
        if isinstance(claim,dict) and required_state=='PARTIAL':
            try:
                lo,hi=map(Fraction,claim['interval'])
                if lo>=hi:reasons.append('NOT_A_NONDEGENERATE_INTERVAL')
                if claim.get('sharp') is not True:reasons.append('SHARPNESS_NOT_RECORDED')
                if 'expected_interval' in reference and [lo,hi]!=list(map(Fraction,reference['expected_interval'])):
                    reasons.append('INTERVAL_MISMATCH')
            except (KeyError,ValueError,TypeError,ZeroDivisionError):
                reasons.append('INVALID_INTERVAL')
        if isinstance(claim,dict) and reference.get('expected_target'):
            target=claim.get('target') or {}
            for field,value in reference['expected_target'].items():
                if target.get(field)!=value:reasons.append('TARGET_MISMATCH:'+field)
    elif expected in ('MISSING_STOP','CONFLICT_STOP'):
        if state not in ('NEEDS_INPUT','CLARIFICATION_REQUIRED'):
            reasons.append('EXPECTED_CLARIFICATION_NOT_REACHED')
        if called or certificate or claim or replay:reasons.append('STOP_INCORRECTLY_CERTIFIED')
        if not outcome.get('clarification_questions'):reasons.append('CLARIFICATION_QUESTION_MISSING')
        questions=' '.join(map(str,outcome.get('clarification_questions') or []))
        for group in reference.get('clarification_keyword_groups',[]):
            if not any(term in questions for term in group):
                reasons.append('CLARIFICATION_OMITS_REQUIRED_TOPIC:'+ '/'.join(group))
    else:
        raise ValueError('Unknown reference state: '+str(expected))
    return {'expected_state':expected,'actual_state':state,'execution_evidence_gate_passed':not reasons,
            'reasons':reasons,'backend_called':called,'independent_replay':replay,
            'final_correctness':'NOT_ESTABLISHED_BY_THIS_GATE',
            'warning':'Reads the recorded project result; does not independently rerun its certificate.',
            'requires_separate_target_source_and_science_review':True}


def verify_files(result_path,reference_path,output):
    result_path,reference_path=Path(result_path),Path(reference_path)
    outcome=load(result_path);reference=load(reference_path)
    report=verify(outcome,reference)
    report['result_sha256']=hashlib.sha256(result_path.read_bytes()).hexdigest()
    report['reference_sha256']=hashlib.sha256(reference_path.read_bytes()).hexdigest()
    target=Path(output)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();verify_files(a.result,a.reference,a.output)
