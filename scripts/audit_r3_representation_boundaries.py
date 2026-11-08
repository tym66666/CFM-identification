#!/usr/bin/env python3
"""Read-only R3 representation structure report. No change to theorem/verifier."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=(
    'identification_observational_effects.py',
    'identification_observational_factorized_a4.py',
    'identification_observational_mixture_a4.py',
    'identification_observational_exposure_adjustment.py',
    'identification_observational_nodewise_adjustment.py',
    'identification_observational_nodewise_mixture_a4.py',
    'identification_r3_target_a4_audit.py',
)
CATEGORIES={
 'identification_observational_effects.py':'FINITE_FULL_JOINT_LAW',
 'identification_observational_factorized_a4.py':'NODE_INDEPENDENT_LAW',
 'identification_observational_mixture_a4.py':'FINITE_MIXTURE_LAW',
 'identification_observational_exposure_adjustment.py':'SHARED_STRATUM_ADJUSTED_TARGET',
 'identification_observational_nodewise_adjustment.py':'NODEWISE_ADJUSTED_TARGET',
 'identification_observational_nodewise_mixture_a4.py':'NODEWISE_CONDITIONAL_MIXTURE_A4',
 'identification_r3_target_a4_audit.py':'READ_ONLY_COMPARISON_NOT_IDENTIFICATION',
}

def summarize(root:Path=ROOT):
    records=[]
    for name in FILES:
        p=root/'pfn_pipeline'/name
        text=p.read_text(encoding='utf-8')
        parsed=ast.parse(text)
        definitions={node.name:{'line':node.lineno,'lines':node.end_lineno-node.lineno+1}
            for node in parsed.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
        imports=set()
        for node in parsed.body:
            if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('identification_'):
                imports.add(node.module)
        records.append({'file':f'pfn_pipeline/{name}','role':CATEGORIES[name],
                        'lines':len(text.splitlines()),'main_definitions':definitions,
                        'local_identification_imports':sorted(imports)})
    return {'schema_version':'r3-structural-boundary-audit-v1',
            'records':records,
            'distinct_causal_target_classes':['OBSERVATIONAL_P_STANDARDIZED','EXPOSURE_ADJUSTED','NODEWISE_ADJUSTED'],
            'protected_boundary_rules':[
                'Keep different causal target classes distinct even when effects share a name',
                'Never remove exact independent replay in favor of solver reuse',
                'Full finite law, independent law, and finite mixture are A4 representations, not new causal theorems',
                'No production refactor until cross-representation equivalence and counterexamples pass',
            ],
            'decision':'FREEZE_ALGORITHMS_RETAIN_DISTINCT_VERIFIERS_FOR_NOW'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    obj=summarize()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('R3 read-only inventory:',len(obj['records']),'modules,',sum(r['lines'] for r in obj['records']),'lines')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
