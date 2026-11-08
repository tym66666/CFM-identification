"""Runtime relocation must preserve old callers and separate reference scoring."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
PAIRS=[
 ('business_fixed_intent_base','cfm_id_llm.readers.fixed_policy_base',('Conditions','Reading','project','_nodes')),
 ('business_fixed_intent_partial','cfm_id_llm.readers.fixed_policy_partial',('make_request','project')),
 ('business_fixed_intent','cfm_id_llm.readers.fixed_policy',('make_request','preview')),
 ('mean_order_factored_reading','cfm_id_llm.readers.mean_order',('FactoredOrder','FactoredClaim','to_canonical','projection_receipt')),
 ('mean_order_count_guidance','cfm_id_llm.readers.mean_order_count_guidance',('make_request',)),
 ('mean_order_factored_review','cfm_id.workflows.mean_order_review',('ReviewedFactoredReading','worksheet','validate_review','submit')),
 ('mean_order_workflow','cfm_id.workflows.mean_order',('WorkflowError','public_bundle','make_request','inspect_candidate','submit_reviewed','_view')),
]


@pytest.mark.parametrize('old_name,new_name,names',PAIRS,ids=[p[0] for p in PAIRS])
def test_old_imports_share_actual_runtime_functions_and_types(old_name,new_name,names):
    old=importlib.import_module('evaluation.'+old_name);new=importlib.import_module(new_name)
    for name in names:assert getattr(old,name) is getattr(new,name)


def test_references_and_scoring_are_not_runtime_reader_exports():
    from cfm_id_llm.readers import mean_order as runtime
    from evaluation import mean_order_factored_reading as evaluation
    from examples.mean_order_business_fixture import make_case
    assert not hasattr(runtime,'reference_wire') and not hasattr(runtime,'wire_metrics')
    case=make_case();wire=evaluation.reference_wire(case['bundle'],case['candidate'])
    assert runtime.to_canonical(case['bundle'],wire)==case['candidate']
    assert evaluation.wire_metrics(case['bundle'],wire,wire)['passed']


def run_isolated(tmp_path,program,*args):
    result=subprocess.run([sys.executable,'-I','-B','-c',program,str(ROOT),*map(str,args)],
        cwd=tmp_path,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    return result.stdout.strip()


def test_fixed_policy_reading_runs_without_any_evaluation_package(tmp_path):
    program='''
import importlib.abc,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='evaluation' or fullname.startswith('evaluation.'):
   raise AssertionError('Pure reader imported evaluation')
sys.meta_path.insert(0,Block());sys.path.insert(0,sys.argv[1])
from cfm_id_llm.readers import fixed_policy
bundle=dict(node_order=['北站','南站'],documents={'需求':'只评价北站，比较两站都使用和两站都不使用。'},question_slots={'q1':'只评价北站，比较两站都使用和两站都不使用。'})
raw=dict(intents={'q1':dict(kind='比较',quote=bundle['question_slots']['q1'])},questions={'q1':dict(first={'北站':1,'南站':1},second={'北站':0,'南站':None},population=['北站'],aggregation='等权平均')})
assert fixed_policy.make_request(bundle)
result=fixed_policy.preview(bundle,raw)
assert result['state']=='NEEDS_INPUT' and not result['core_called']
assert result['reading_candidate']['questions']['q1']['second']['南站'] is None
assert not any(n=='evaluation' or n.startswith('evaluation.') for n in sys.modules)
print('isolated_reader_passed')
'''
    assert run_isolated(tmp_path,program)=='isolated_reader_passed'


def test_new_workflow_does_not_load_relocated_evaluation_facades(tmp_path):
    from evaluation.mean_order_factored_reading import reference_wire
    from examples.mean_order_business_fixture import make_case
    case=make_case();wire=reference_wire(case['bundle'],case['candidate'])
    wire['order_reading']['claims'][1]['scope']='UNKNOWN'
    data=tmp_path/'input.json';data.write_text(json.dumps(dict(bundle=case['bundle'],wire=wire)),encoding='utf8')
    program='''
import importlib.abc,json,sys
from pathlib import Path
blocked=set(json.loads(sys.argv[3]))
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in blocked:raise AssertionError('Runtime used relocated compatibility facade: '+fullname)
sys.meta_path.insert(0,Block());sys.path.insert(0,sys.argv[1])
from cfm_id.workflows import mean_order
v=json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
assert mean_order.make_request(v['bundle'])
r=mean_order.inspect_candidate(v['bundle'],v['wire'])
assert r['state']=='NEEDS_INPUT' and not r['result']['core_called']
assert r['wire_candidate']==v['wire'] and not r['result']['bounded_backend_called']
assert not blocked.intersection(sys.modules)
print('isolated_workflow_passed')
'''
    names=json.dumps(['evaluation.'+p[0] for p in PAIRS])
    assert run_isolated(tmp_path,program,data,names)=='isolated_workflow_passed'


def test_registered_mean_order_entry_resolves_to_current_runtime_and_cli():
    import tomllib
    from cfm_id import capability_registry
    from cfm_id.workflows import mean_order
    row=next(r for r in capability_registry.registrations() if r.capability.route_id=='MEAN_ORDER_D2_E1')
    assert importlib.import_module(row.business_entry) is mean_order
    metadata=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))
    assert metadata['project']['scripts']['cfm-id-mean-order']=='cfm_id.workflows.mean_order:main'
