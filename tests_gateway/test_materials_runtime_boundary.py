"""Material parsing remains usable without importing any evaluation package."""
import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from cfm_id import materials

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def material_root(tmp_path):
    folder = tmp_path / 'delivery-teams'
    folder.mkdir()
    manifest = dict(case_id='delivery-teams', synthetic=True,
        business_question_file='question.md',
        supporting_files=['units.csv', 'network_edges.csv', 'outcomes.csv'])
    (folder / 'submission_manifest.json').write_text(json.dumps(manifest), encoding='utf8')
    (folder / 'question.md').write_text(
        '四个配送班组会相互支援。如果全部班组采用新排班工具，每单配送的平均延误时间是多少？', encoding='utf8')
    (folder / 'units.csv').write_text(
        'node_id,unit_group\n北站,A\n西站,A\n东站,B\n南站,B\n', encoding='utf8')
    (folder / 'network_edges.csv').write_text(
        'source_id,target_id,frozen_before_rollout\n北站,西站,1\n西站,东站,1\n东站,南站,1\n', encoding='utf8')
    (folder / 'outcomes.csv').write_text('node_id,delay_minutes\n北站,818181\n', encoding='utf8')
    return tmp_path


def test_runtime_parser_preserves_structure_and_does_not_expose_sample_outcomes(material_root):
    bundle = materials.load_bundle('delivery-teams', public_root=material_root)
    assert bundle['structure']['nodes'] == ['北站', '西站', '东站', '南站']
    assert len(bundle['structure']['edges']) == 3
    assert {frozenset(edge) for edge in bundle['structure']['edges']} == {
        frozenset(edge) for edge in [('北站', '西站'), ('西站', '东站'), ('东站', '南站')]}
    assert list(bundle['question_slots']) == ['q1']
    assert bundle['tables']['outcomes.csv']['rows'] == []
    prompt = materials.prompt_materials(bundle)
    assert '818181' not in json.dumps(prompt, ensure_ascii=False)
    assert prompt['source_catalog']['question.md:L1'] == bundle['documents']['question.md']
    assert not {'scientific_approval', 'production_admission', 'gold', 'reference'} & set(bundle)


def test_runtime_parser_has_no_implicit_benchmark_root():
    with pytest.raises(TypeError, match='public_root'):
        materials.load_bundle('NBIB-001')


def test_material_loading_still_works_when_evaluation_imports_are_forbidden(material_root):
    program = '''
import importlib.abc, json, sys
class RejectEvaluation(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'evaluation' or fullname.startswith('evaluation.'):
            raise AssertionError('Runtime parser imported evaluation code')
sys.meta_path.insert(0, RejectEvaluation())
sys.path.insert(0, sys.argv[1])
from cfm_id.materials import load_bundle, prompt_materials
bundle = load_bundle('delivery-teams', public_root=sys.argv[2])
assert len(bundle['structure']['nodes']) == 4
assert len(prompt_materials(bundle)['question_slots']) == 1
assert not any(n == 'evaluation' or n.startswith('evaluation.') for n in sys.modules)
print('standalone_material_loading_passed')
'''
    run = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(ROOT), str(material_root)],
        cwd=material_root, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == 'standalone_material_loading_passed'


@pytest.mark.parametrize('change', ['parent_escape', 'not_synthetic'])
def test_runtime_parser_preserves_existing_input_restrictions(material_root, change):
    path = material_root / 'delivery-teams/submission_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf8'))
    if change == 'parent_escape':
        manifest['supporting_files'].append('../outside.md')
        (material_root / 'outside.md').write_text('Outside the declared material folder', encoding='utf8')
        error = 'PUBLIC_FILE_PATH_INVALID'
    else:
        manifest['synthetic'] = False
        error = 'PUBLIC_SYNTHETIC_MANIFEST_REQUIRED'
    path.write_text(json.dumps(manifest), encoding='utf8')
    with pytest.raises(ValueError, match=error):
        materials.load_bundle('delivery-teams', public_root=material_root)


def test_legacy_nbib_entry_keeps_default_and_explicit_source_semantics(material_root):
    from evaluation import business_materials_intake as legacy
    assert legacy.load_bundle('NBIB-003') == materials.load_bundle('NBIB-003', public_root=legacy.PUBLIC)
    extra = dict(clarification='如果仅北站使用工具，所有班组的平均延误时间是多少？',
                 design_addendum='原分配方式尚未确认。')
    before = legacy.load_bundle('delivery-teams', public_root=material_root, **extra)
    current = materials.load_bundle('delivery-teams', public_root=material_root, **extra)
    assert before == current
    assert current['documents']['design_addendum.txt'] == extra['design_addendum']
    assert current['revision_kind'] == 'EXPLICIT_CLARIFICATION'


def test_runtime_evaluation_dependencies_match_reviewed_legacy_inventory():
    found = {}
    for directory in ('cfm_id', 'cfm_id_bridge', 'cfm_id_llm'):
        for path in (ROOT / directory).rglob('*.py'):
            names = set()
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                if isinstance(node, ast.Import):
                    names.update(a.name for a in node.names if a.name == 'evaluation' or a.name.startswith('evaluation.'))
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    module = node.module or ''
                    if module == 'evaluation':
                        names.update(module + '.' + a.name for a in node.names)
                    elif module.startswith('evaluation.'):
                        names.add(module)
            if names:
                found[path.relative_to(ROOT).as_posix()] = sorted(names)
    baseline = json.loads((Path(__file__).parent / 'runtime_dependency_baseline.json').read_text(encoding='utf8'))
    assert baseline['schema'] == 1
    assert found == baseline['legacy_imports'], (
        'Runtime/evaluation dependencies changed: review the layer boundary and retire obsolete exceptions; '
        'do not automatically refresh the inventory to permit new dependencies.')
