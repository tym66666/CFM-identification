#!/usr/bin/env python3
"""Bounded, independent-process diagnosis for the historical PFN smoke.

This is a maintenance/ablation tool, not a training fix and not a causal theorem.
Each repetition uses a FRESH child process. Setting ``--thread-mode inherited``
removes only the tool's thread overrides; it does not promise true unconstrained
threads if the caller already defines OMP/MKL/OPENBLAS settings.

A process exit code of zero is NOT by itself a PASS: the requested unittest count
and both training/evaluation stage-end markers must also be observed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST = 'tests.test_pipeline_smoke.PipelineSmokeTest.test_migrated_checkpoint_evaluation'
THREAD_VARIABLES = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')

CHILD = r'''
import faulthandler, sys, time, unittest
faulthandler.enable()
faulthandler.dump_traceback_later(float(sys.argv[1]), repeat=False)
import tests.test_pipeline_smoke as m

def stage(name, fn):
    def wrapped(*args, **kwargs):
        ts=time.monotonic()
        print('CFM_PHASE_BEGIN '+name,flush=True)
        try:
            value=fn(*args,**kwargs)
            print('CFM_PHASE_END '+name+' '+str(round(time.monotonic()-ts,4)),flush=True)
            return value
        except BaseException:
            print('CFM_PHASE_ERROR '+name,flush=True)
            raise
    return wrapped
m.train_model=stage('train_model',m.train_model)
m.evaluate_checkpoint=stage('evaluate_checkpoint',m.evaluate_checkpoint)
name=sys.argv[2]
print('CFM_TEST '+name,flush=True)
test=unittest.defaultTestLoader.loadTestsFromName(name,module=None)
res=unittest.TextTestRunner(verbosity=2).run(test)
faulthandler.cancel_dump_traceback_later()
sys.exit(0 if res.wasSuccessful() else 1)
'''


def _child_command(trace_after: float, test_id: str):
    return [sys.executable, '-B', '-u', '-c', CHILD, str(trace_after), test_id]


def _extract_text(raw):
    if isinstance(raw, bytes):
        return raw.decode('utf-8', 'replace')
    return raw or ''


def _expected_markers(test_id: str):
    count = 1 if test_id == DEFAULT_TEST else 9
    return (
        'CFM_TEST '+test_id,
        'CFM_PHASE_BEGIN train_model',
        'CFM_PHASE_END train_model ',
        'CFM_PHASE_BEGIN evaluate_checkpoint',
        'CFM_PHASE_END evaluate_checkpoint ',
        f'Ran {count} test'+('' if count == 1 else 's')+' in ',
    )


def _run_one(*, test_id, timeout, stack_after, environment):
    start=time.monotonic()
    timed_out=False
    try:
        result=subprocess.run(_child_command(stack_after,test_id),cwd=ROOT,
            env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,timeout=timeout,check=False)
        output=_extract_text(result.stdout)
        code=result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out=True
        code=124
        output=_extract_text(exc.stdout)
        output+='\nCFM_WATCHDOG_TIMEOUT: child process terminated by parent timeout\n'
    duration=round(time.monotonic()-start,4)
    markers=_expected_markers(test_id)
    missing=[mark for mark in markers if mark not in output]
    if not re.search(r'(?m)^OK\s*$',output):
        missing.append('unittest OK terminal line')
    status='TIMEOUT' if timed_out else 'FAIL' if code!=0 or missing else 'PASS'
    events=[line[line.index('CFM_PHASE_'):] for line in output.splitlines() if 'CFM_PHASE_' in line]
    return dict(status=status,returncode=code,seconds=duration,phase_events=events,
                missing_success_markers=missing),output


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',choices=['checkpoint','full'],default='checkpoint')
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--stack-after',type=float,default=40)
    parser.add_argument('--repetitions',type=int,default=1)
    parser.add_argument('--thread-mode',choices=['controlled','inherited'],default='controlled')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.timeout<=0 or args.stack_after<=0:
        parser.error('timeouts must be positive')
    if not (1<=args.repetitions<=10):
        parser.error('repetitions must be between 1 and 10')
    test_id=DEFAULT_TEST if args.test=='checkpoint' else 'tests.test_pipeline_smoke'
    environment=os.environ.copy()
    if args.thread_mode=='controlled':
        environment.update({key:'1' for key in THREAD_VARIABLES})
    environment.update(PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1')
    environment['PYTHONPATH']=os.pathsep.join([str(ROOT/'tests'),str(ROOT),environment.get('PYTHONPATH','')])
    effective_threads={key:environment.get(key) for key in THREAD_VARIABLES}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    runs=[]
    logs=[]
    for i in range(args.repetitions):
        result,output=_run_one(test_id=test_id,timeout=args.timeout,
                               stack_after=args.stack_after,environment=environment)
        result['repetition']=i+1
        runs.append(result)
        logs.append(f'===== REPETITION {i+1} / {args.repetitions} ({result["status"]}) =====\n'+output)
    status=('TIMEOUT' if any(x['status']=='TIMEOUT' for x in runs) else
            'FAIL' if any(x['status']!='PASS' for x in runs) else 'PASS')
    summary={'schema_version':'cfm-id-smoke-isolated-diagnostic-v2',
             'test':test_id,'status':status,
             'returncode':124 if status=='TIMEOUT' else 1 if status=='FAIL' else 0,
             'seconds':round(sum(r['seconds'] for r in runs),4),
             'timeout_seconds':args.timeout,'stack_after_seconds':args.stack_after,
             'thread_mode':args.thread_mode,'thread_env':effective_threads,
             'repetitions':args.repetitions,'runs':runs,
             # Backward-compatible top-level location for one-run consumers:
             'phase_events':runs[0]['phase_events'] if len(runs)==1 else
                 [event for run in runs for event in run['phase_events']],
             'note':'One child per repetition; failure/timeout cannot count as PASS. '
                    'Scientific and causal claims are not tested here. '
                    'Controlled thread configuration is not a proven root-cause repair.'}
    args.report.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    args.report.with_suffix('.log').write_text('\n'.join(logs),encoding='utf-8')
    print(f'{status}: {test_id}; {len(runs)} fresh subprocess(es), '
          f'{summary["seconds"]:.2f}s; mode={args.thread_mode}; report={args.report}')
    for run in runs:
        print(f'  trial={run["repetition"]} {run["status"]} {run["seconds"]:.2f}s '
              f'phase_events={len(run["phase_events"])} '
              f'missing_markers={len(run["missing_success_markers"])}')
    return summary['returncode']


if __name__=='__main__':
    raise SystemExit(main())
