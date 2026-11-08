"""Hard wall-clock bound for one audited local request process.

No authentication access. Only the explicitly created child process is killed.
Every reserved HTTP attempt survives cancellation; no automatic retry is made.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import sys
import time

LEDGERS = {'key1': 'online_round2_20261019', 'key2': 'online_key2_20261019'}

def bounded_process(command, seconds):
    if seconds <= 0:
        raise ValueError('Deadline must be positive')
    try:
        # subprocess.run kills and waits for exactly this child on timeout.
        return subprocess.run(command, timeout=seconds), False
    except subprocess.TimeoutExpired:
        return None, True

def _read(path):
    return json.loads(path.read_text(encoding='utf8'))

def _save(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    tmp.replace(path)

def run_slot(out, run, seconds=300):
    out=Path(out).resolve(); spec=_read(out/'EXPERIMENT_PLAN.json')['slots'][run]
    started=time.monotonic()
    result, expired=bounded_process([sys.executable,'-B',str(out/'run_case.py'),'--run',run], seconds)
    if not expired:
        return result
    # The child has exited before any ledger or lock repair.
    alias=spec['key']; directory=(out.parent/LEDGERS[alias]).resolve()
    assert directory.parent==out.parent
    path=directory/'REQUEST_LEDGER.json'; ledger=_read(path)
    records=[x for x in ledger['requests'] if x.get('run_id')==out.name+'_'+run]
    pointer=out/(run+'_pointer.json')
    if pointer.exists():
        # A fully saved result wins over a timeout while the process is exiting.
        if len(records)!=1 or records[0]['status']=='IN_FLIGHT':
            raise RuntimeError('Saved pointer without a completed reservation')
        folder=(directory/records[0]['artifact_directory']).resolve()
        assert folder.parent==directory and Path(_read(pointer)['folder']).resolve()==folder
        assert _read(folder/'result.json')['status']==records[0]['status']
        for lock in (out/'RUNNING.lock',directory/'RUNNING.lock'):
            assert lock.resolve().parent in (out,directory)
            if lock.exists(): lock.unlink()
        return subprocess.CompletedProcess([],0)
    if len(records)!=1:
        raise RuntimeError('Deadline before a unique request reservation; manual inspection required')
    record=records[0]; folder=(directory/record['artifact_directory']).resolve()
    assert folder.parent==directory and folder.is_dir()
    elapsed=round(time.monotonic()-started,3)
    record.update(status='REJECTED',error_code='PROCESS_WALL_DEADLINE',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=elapsed,transport_calls=1,
        killed_request_process=True,automatic_retries=False)
    meta=dict(run=run,case_id=spec['case'],key=alias,phase=spec['phase'],attempt=record['attempt'],
        status='REJECTED',error_code='PROCESS_WALL_DEADLINE',error_kind='RequestProcessDeadline',
        core_called=None if (folder/'model_draft.json').exists() else False,transport_calls=1,elapsed_seconds=elapsed,
        provider_diagnostics=dict(stage='process_deadline',stream=spec.get('stream',True),
                                  hard_wall_seconds=seconds,completed_identification_not_available=True,
                                  raw_model_draft_present=(folder/'model_draft.json').exists()))
    _save(folder/'result.json',meta); _save(path,ledger); _save(pointer,{'folder':str(folder)})
    for lock in (out/'RUNNING.lock',directory/'RUNNING.lock'):
        assert lock.resolve().parent in (out,directory)
        if lock.exists(): lock.unlink()
    print(json.dumps(meta,ensure_ascii=False),flush=True)
    return subprocess.CompletedProcess([],0)
