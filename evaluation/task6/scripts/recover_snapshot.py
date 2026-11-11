"""Recover a missing candidate copy from a saved intake snapshot; no model calls.

The runner saved session.candidate both as raw_response.json and in the snapshot.
The restored JSON preserves the parsed candidate, not its original file bytes or
the provider's HTTP response. It is written separately, never into private/.
"""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover(source, output, peer_runs):
    source, output = Path(source), Path(output)
    snapshot = load(source/'intake_snapshot.json')
    request = load(source/'request.json')
    result = load(source/'result.json')
    if (source/'raw_response.json').exists():
        raise ValueError('Original candidate file exists; recovery is unnecessary')
    if not result.get('raw_response_saved') or not isinstance(snapshot.get('candidate'), dict):
        raise ValueError('Missing recorded candidate or success marker')
    if not snapshot['request_sha256'] == request['request_sha256'] == result['request_sha256']:
        raise ValueError('Snapshot, request and result bindings differ')
    matches = mismatches = 0
    for base in peer_runs:
        for p in Path(base).glob('private/*/intake_snapshot.json'):
            raw = p.parent/'raw_response.json'
            if raw.exists():
                if load(p).get('candidate') == load(raw): matches += 1
                else: mismatches += 1
    if not matches or mismatches:
        raise ValueError(f'Cannot validate peer snapshot equivalence: {matches=} {mismatches=}')
    output.mkdir(parents=True, exist_ok=False)
    candidate = output/'candidate_recovered_from_snapshot.json'
    candidate.write_text(json.dumps(snapshot['candidate'], ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    metadata = dict(case_id=result['case_id'], profile=result['profile'], repeat=result['repeat'],
        run_id=result['id'], source_snapshot_sha256=sha(source/'intake_snapshot.json'),
        recovered_candidate_sha256=sha(candidate), request_sha256=result['request_sha256'],
        peer_candidates_equal=matches, peer_candidates_different=mismatches,
        status='RECOVERED_PARSED_CANDIDATE_NOT_ORIGINAL_FILE_OR_HTTP_BYTES',
        new_api_calls=0)
    (output/'recovery_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(metadata,ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--peer-runs',nargs='+',required=True)
    a=p.parse_args()
    recover(a.source,a.output,a.peer_runs)
