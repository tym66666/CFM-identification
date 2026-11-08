"""The old network entry must execute without importing research/fixture code."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import pickle
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['d1', 'd2', 'cluster', 'peers'])
def test_reviewed_execution_survives_forbidden_evaluation_and_examples(tmp_path, kind):
    from examples.legacy_network_acceptance_fixture import make_case
    case = make_case(kind)
    # Trusted test-owned objects only. No production entry accepts pickle.
    frozen = tmp_path / 'trusted_test_context.pickle'
    frozen.write_bytes(pickle.dumps(case, protocol=pickle.HIGHEST_PROTOCOL))
    program = '''
import importlib.abc,json,pickle,sys
from copy import deepcopy
from pathlib import Path
blocked=('evaluation','examples','student_work')
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in blocked:raise AssertionError('Runtime imported research code: '+fullname)
sys.meta_path.insert(0,Block());sys.path.insert(0,sys.argv[1])
from cfm_id import business_entry,intent_submission
with Path(sys.argv[2]).open('rb') as stream:c=pickle.load(stream)
b,r,e,env,p,context,review=[c[k] for k in ('bundle','raw','entry','envelope','packet','context','review')]
request=business_entry.prepare_request(b,e,env)
assert request['system'] and request['user']
def submit(raw,approval):
 return intent_submission.submit(b,raw,e,env,p,context=context,submission_review=approval,synthetic_protocol_selected=True)
unreviewed=submit(r,None)
assert not unreviewed['core_called'] and not context.core_port.calls
wrong=deepcopy(r);wrong['intents'][next(iter(b['question_slots']))]['quote']='Unreviewed replacement'
assert not submit(wrong,review)['core_called'] and not context.core_port.calls
missing=deepcopy(r);missing['questions'][next(iter(b['question_slots']))]['first']['own']='不明确'
incomplete=business_entry.preview(b,missing,e,env)
assert not incomplete['core_called']
positive=submit(r,review)
assert positive['state']==('MIXED' if e=='STAGED_CORE_PEERS' else 'CORE_POINT')
if 'query_views' in positive:
 verified=[q for q in positive['query_views'] if q.get('certificate_replayed')]
 assert len(verified)==(2 if e in ('D1_EFFECTS','STAGED_CORE_PEERS') else 1)
else:assert positive['view']['core']['certificate_replayed']
assert context.core_port.calls
assert not any(n.split('.')[0] in blocked for n in sys.modules)
print(json.dumps({'state':positive['state'],'no_research_imports':True}))
'''
    run = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(ROOT), str(frozen)],
                         cwd=tmp_path, capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-6000:]
    assert json.loads(run.stdout)['no_research_imports'] is True


@pytest.mark.parametrize('old,new,names', [
    ('business_core_pilot_base', 'cfm_id.workflows.legacy_network.target_model', ('Closed', 'State', 'Target', '_target_blocker')),
    ('business_candidate_base', 'cfm_id.workflows.legacy_network.review_context', ('MaterialsCandidateApprovalV035', 'ReviewedMaterialsContextV035')),
    ('business_d1_submission', 'cfm_id.workflows.legacy_network.d1_submission', ('Study', 'project', 'compile_inquiry', 'identify_submission')),
    ('business_d2_submission', 'cfm_id.workflows.legacy_network.d2_submission', ('Question', 'project', 'identify_submission')),
    ('business_core_peers_base', 'cfm_id.workflows.legacy_network.core_peers_base', ('Study', 'project', 'identify_submission')),
    ('business_arm_submission', 'cfm_id.workflows.legacy_network.arm_submission', ('identify_arm_submission',)),
])
def test_old_imports_keep_runtime_types_and_functions(old, new, names):
    former = importlib.import_module('evaluation.' + old)
    current = importlib.import_module(new)
    for name in names:
        assert getattr(former, name) is getattr(current, name)


def test_legacy_hash_keeps_its_contract_without_merging_other_hashes():
    from cfm_id.serialization import canonical_hash
    from evaluation.business_core_pilot_base import canonical_hash as old
    from cfm_id_llm.orchestration_schemas import canonical_sha256
    assert old is canonical_hash
    assert canonical_hash({'乙': [1, None], '甲': True}) == canonical_sha256({'甲': True, '乙': [1, None]})
    # Legacy acceptance is kept; stricter new contracts must remain stricter.
    assert len(canonical_hash({'x': float('nan')})) == 64
    with pytest.raises(ValueError):
        canonical_sha256({'x': float('nan')})


def test_failed_replay_cannot_publish_point(monkeypatch):
    from examples.legacy_network_acceptance_fixture import make_case
    from cfm_id.intent_submission import submit
    c = make_case('d2')
    monkeypatch.setattr('pfn_pipeline.identification_business.replay_verified_business_outcome', lambda _: False)
    result = submit(c['bundle'], c['raw'], c['entry'], c['envelope'], c['packet'],
                    context=c['context'], submission_review=c['review'], synthetic_protocol_selected=True)
    assert result['state'] != 'CORE_POINT'
    assert not any(q.get('certificate_replayed') for q in result.get('query_views', []))
