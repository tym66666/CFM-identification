"""Generate a genuine Core-backed, offline Identification-only supervisor gallery.

Source: six existing synthetic business scenarios and one frozen minimal ablation;
the Star7 interval is deliberately isolated research, not formal PARTIAL.
No LLM, estimation, policy or external services required.

    python -m examples.build_identification_only_demo --output-dir assets/identification_only_templates
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from examples.run_common_business_benchmark import BUSINESSES, VARIANTS, _build_inquiry
from examples.minimal_correct_core_golden import SCENARIOS, ablated_task, independent_support
from identification_only import from_verified_core, research_partial_card
from pfn_pipeline import ArmInquiryV21, identify_network_business_query
from research_partial.star7_bounded_r2_policy_demo import generate as partial_generate

STEM = 'CFM_ID_Identification_Only_Supervisor_Demo'


def build_data() -> dict:
    by_business = {x[0]: x for x in BUSINESSES}
    cases = []
    for scenario, variant, expected, explanation in VARIANTS:
        sid, title, business_area, design, exposure, route, question = by_business[scenario]
        if variant == 'point_e4':
            exposure = 'E4'
            question = '在线独立 A/B 下，用户 a 使用新功能且恰有一名关联用户使用时的设计标准化平均结果'
        if sid == 'S2' and variant == 'zero_support':
            question = '固定三名员工试用 AI 时，星型中心 a 自己试用且五位邻居中恰有三位试用的均值是否可识别？'
        inquiry = _build_inquiry(scenario, 'point' if variant == 'point_e4' else variant)
        out = identify_network_business_query(inquiry)
        report = from_verified_core(out, case_id=f'{scenario}-{variant}', business_question=question,
            setting=title, design=design, exposure=exposure,
            information_description=('研究人员额外声明的合成 typed 总体算子；未从有限样本推定'),
            assumptions_description=(
                '观测研究：明确接受的 exposure sufficient potential outcomes 与局部条件均值交换性'
                if sid == 'S6' else '随机实验：已知分配律、full-vector randomization、consistency、固定处理前网络；D6 另需第一阶段排除限制'),
        )
        report['scenario_id'] = scenario
        report['variant'] = variant
        report['original_expected_status'] = expected
        report['source_case_explanation'] = explanation
        if report['identification']['status'] != expected:
            raise AssertionError(f'{scenario}/{variant}: formal result changed from documented expectation')
        cases.append(report)

    for change in SCENARIOS:
        task = ablated_task(change)
        out = identify_network_business_query(ArmInquiryV21(task))
        report = from_verified_core(out, case_id=f'GOLDEN-{change}',
            business_question=f'三节点路径：D2 固定两人、节点 0 的指定 Arm；单因素消融 {change}',
            setting='三节点最简 Golden Case', design='D2', exposure=task.exposure_definition,
            information_description='合成 typed 人口总体节点 Arm 均值；消融时可移除',
            assumptions_description='仅按指定消融修改 randomization / consistency 等许可',
        )
        report['variant'] = change
        report['scenario_id'] = 'GOLDEN'
        cases.append(report)

    research = research_partial_card(partial_generate())
    if research['proof']['replay_verified'] or research['category'] != 'PARTIAL_RESEARCH_ONLY':
        raise AssertionError('Research-only bounds cannot acquire formal certification')
    counts = dict(sorted(Counter(x['identification']['status'] for x in cases).items()))
    return dict(
        schema_version='cfm-id-identification-only-gallery-v1',
        formal_case_count=len(cases),
        core_status_counts=counts,
        formal_case_ids=[x['case_id'] for x in cases],
        cases=cases, research_partial=research,
        source_kind='SYNTHETIC_HUMAN_STIPULATED_A4_A5',
        script_executes_original_core_and_replay=True,
        online_llm_called=False,
        real_scientific_assumptions_proven=False,
        numeric_estimation_performed=False,
        production_partial_certified=False,
        business_coverage_percentage='NOT_MEASURED',
        notes=[
            'Formal POINT are evaluated from current typed Core and independently replayed.',
            'NEEDS_INPUT and UNSUPPORTED are NOT proofs of mathematical non-identification.',
            'PARTIAL is a separate bounded-outcome Star7 research artifact, not an approved R4.',
            'Uploading business prose/files in the offline viewer NEVER triggers the Python theorem Core.',
            'A0 reviewed formulation and scientific admission must be performed in a separate audited workflow.',
        ],
    )


def run(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    data = build_data()
    data_path = directory / (STEM + '.json')
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    template = (Path(__file__).resolve().parents[1]/'assets/identification_only_templates'/'template.html').read_text(encoding='utf-8')
    safe_payload = json.dumps(data, ensure_ascii=False, sort_keys=True).replace('<', '\\u003c').replace('>', '\\u003e')
    if '<!-- EMBEDDED_CORE_DATA -->' not in template:
        raise RuntimeError('Missing fixed renderer data insertion marker')
    page = template.replace('<!-- EMBEDDED_CORE_DATA -->',
                            '<script id="certified-core-gallery" type="application/json">'+safe_payload+'</script>')
    html_path = directory / (STEM + '.html')
    html_path.write_text(page, encoding='utf-8')
    return data_path, html_path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='assets/identification_only_templates')
    args=parser.parse_args(argv)
    paths=run(Path(args.output_dir))
    data=json.loads(paths[0].read_text(encoding='utf-8'))
    print(json.dumps({'files':[str(p) for p in paths],
                      'formal_cases':data['formal_case_count'],
                      'statuses':data['core_status_counts'],
                      'partial':'RESEARCH_ONLY'},ensure_ascii=False))

if __name__=='__main__': main()
