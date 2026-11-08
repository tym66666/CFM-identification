"""Wheel-in-a-separate-directory CLI acceptance; no online LLM or data APIs.

Run only after creating a wheel with pip wheel --no-deps.  Uses an isolated
PYTHONPATH pointing at wheel install target, not the source repository.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from tests.test_json_route_packets import JSONPacketRegression


def main(wheel_path):
    wheel=Path(wheel_path).resolve()
    if not wheel.is_file():raise ValueError('Wheel artifact required')
    test=JSONPacketRegression('test_all_nine_routes_and_negative_injection')
    test.setUp();test.test_all_nine_routes_and_negative_injection()
    with tempfile.TemporaryDirectory(prefix='v291_isolated_') as tmp:
        root=Path(tmp);site=root/'installed';site.mkdir()
        subprocess.run([sys.executable,'-m','pip','install','--no-deps',
                        '--no-compile','--target',str(site),str(wheel)],check=True,
                       capture_output=True,text=True,timeout=120)
        working=root/'outside_source';working.mkdir()
        env=os.environ.copy()
        env['PYTHONPATH']=str(site)
        env['OMP_NUM_THREADS']='1';env['MKL_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1'
        # Unlike the source-runner, do not inherit project PYTHONPATH entries.
        for family in ('R1B_FIXED_POLICY','R3_P_STANDARDIZED'):
            case,report,review,packet,intent,evidence=test.integrated_packet_by_route[family]
            def save(name,obj):
                p=working/(family+'_'+name+'.json')
                p.write_text(json.dumps(obj.model_dump(mode='json'),ensure_ascii=False),encoding='utf-8')
                return str(p)
            inputs=[save('case',case),save('report',report),save('review',review),save('packet',packet),
                    save('business',intent),save('evidence',evidence)]
            proc=subprocess.run([sys.executable,'-m','cfm_id_bridge','identify',
                '--case-json',inputs[0],'--report-json',inputs[1],
                '--human-review-json',inputs[2],'--typed-packet-json',inputs[3],
                '--business-intent-json',inputs[4],'--scientific-evidence-json',inputs[5]],
                cwd=working,env=env,capture_output=True,text=True,timeout=60)
            if proc.returncode:
                raise AssertionError(f'{family} installed CLI error: {proc.stderr[-600:]}')
            payload=json.loads(proc.stdout)
            assert payload['release_version']=='2.9.2'
            assert len(payload['results'])==1
            assert payload['results'][0]['status']=='POINT',payload['results'][0]
            assert payload['results'][0]['verification_level']=='CORE_REPLAY_VERIFIED'
            assert payload['results'][0]['estimation_handoff_allowed'] is False
            # Preparing a scientific crosswalk emits an UNAPPROVED worksheet;
            # it can never be mistaken for a certified theorem result.
            worksheet=subprocess.run([sys.executable,'-m','cfm_id_bridge','prepare-science',
                '--case-json',inputs[0],'--report-json',inputs[1],
                '--human-review-json',inputs[2],'--typed-packet-json',inputs[3],
                '--approved-route',payload['results'][0]['route']],
                cwd=working,env=env,capture_output=True,text=True,timeout=60)
            assert worksheet.returncode==0,worksheet.stderr[-500:]
            proposed=json.loads(worksheet.stdout)
            assert proposed['status']=='UNAPPROVED_SCIENTIFIC_REVIEW_WORKSHEET'
            assert 'certificat' not in proposed['status'].lower()
        path_check=subprocess.run([sys.executable,'-c',
            'import cfm_id_bridge, pathlib; print(pathlib.Path(cfm_id_bridge.__file__).resolve())'],
            cwd=working,env=env,capture_output=True,text=True,check=True)
        import_path=Path(path_check.stdout.strip())
        assert site.resolve() in import_path.parents,(site,import_path)
        print('v2.9.2 wheel/CLI outside source: PASS (2 scoped routes, 2 replayed POINT, no estimator)')
    return 0

if __name__=='__main__':raise SystemExit(main(sys.argv[1]))
