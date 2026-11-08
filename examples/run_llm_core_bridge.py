"""End-to-end synthetic integration demo using REAL v2.8 P1.1 theorem code.

No external LLM/API call. Gateway gets MOCK draft; A4/A5 are hypothetical,
independently declared *scientific* admissions; output is a symbolic population
POINT certification, not a numeric business effect or sample estimate.

python -m examples.run_llm_core_bridge --outdir showcase_llm_v29
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from cfm_id_bridge.bridge import run_verified_multiquery_v29
from examples.llm_core_fixture import reviewed_case, bindings, d1_arm_packet


def write_data(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    case, reviewed = reviewed_case()
    reviewed_bindings = bindings(case, reviewed)
    result = run_verified_multiquery_v29(case, reviewed, reviewed_bindings)
    if result.verified_query_count != 2 or any(r.verification_level != 'CORE_REPLAY_VERIFIED' for r in result.results):
        raise AssertionError('Synthetic real theorem bridge did not replay both target certificates')
    files = {
        'business_case.json': case.model_dump(mode='json'),
        'gateway_multiquery_report_MOCK.json': reviewed.report.model_dump(mode='json'),
        'gateway_multiquery_response_MOCK.json': reviewed.report.draft.model_dump(mode='json'),
        'human_business_review_SYNTHETIC.json': reviewed.human_review.model_dump(mode='json'),
        'scientific_d1_arm_packet_SYNTHETIC.json': d1_arm_packet(case, reviewed).model_dump(mode='json'),
        'approved_business_target_q1_SYNTHETIC.json': reviewed_bindings[0].business_intent.model_dump(mode='json'),
        'approved_business_target_q2_SYNTHETIC.json': reviewed_bindings[1].business_intent.model_dump(mode='json'),
        'scientific_evidence_q1_SYNTHETIC.json': reviewed_bindings[0].evidence_manifest.model_dump(mode='json'),
        'scientific_evidence_q2_SYNTHETIC.json': reviewed_bindings[1].evidence_manifest.model_dump(mode='json'),
        'integration_verified_math_SYNTHETIC.json': result.model_dump(mode='json'),
    }
    for name, contents in files.items():
        (out/name).write_text(json.dumps(contents,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    md='''# Causal-IDFM v2.9: 首条真实数学桥接演示（合成）

- Gateway v0.9 从一个完整业务描述中生成 **2 个候选数学查询**。LLM 返回使用**人工编写的 MOCK JSON**，不是在线 API 测试。
- q1：R1a — A 节点在 a=0、E1 暴露 s=0 下的 design-standardized arm mean。
- q2：R1b — 固定全员分配 z=(1,1,1)、等权整体政策价值。
- 数学 Core **实际执行**两个定理，并分别独立 replay 核验 POINT 证书。
- 该案例中的 A4 SYMBOLIC_POPULATION_OPERATOR 与 A5 随机化/一致性是**研究者另外假定的合成事实**，未从业务 CSV 自动推出。
- **没有业务数值估计、没有 Estimation 或 Policy 接口放行。**

CLI（从本目录所在项目根执行）：

```bash
python -m cfm_id_bridge identify \\
  --case-json showcase_llm_v29/business_case.json \\
  --report-json showcase_llm_v29/gateway_multiquery_report_MOCK.json \\
  --human-review-json showcase_llm_v29/human_business_review_SYNTHETIC.json \\
  --d1-packet-json showcase_llm_v29/scientific_d1_arm_packet_SYNTHETIC.json \
  --business-intent-json showcase_llm_v29/approved_business_target_q1_SYNTHETIC.json \
  --scientific-evidence-json showcase_llm_v29/scientific_evidence_q1_SYNTHETIC.json \\
  --output showcase_llm_v29/cli_d1_verified.json
```

该 CLI 当前只提供 D1 arm 的已审核 JSON 适配器，故 q1 经真实 Core 验证、q2 因缺少独立的已审核 R1b 适配声明而保持 NEEDS_INPUT。Python `run_verified_multiquery_v29` 可使用**显式构建的 typed R1b inquiry**，如本演示，完成 q2 的真实识别。
'''
    (out/'README_DEMO_ZH.md').write_text(md,encoding='utf-8')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outdir',default='showcase_llm_v29')
    a=p.parse_args(argv)
    result=write_data(Path(a.outdir))
    print(json.dumps({'case_id':result.case_id,
           'results':[{'query_id':q.query_id,'status':q.status,'route':q.route,
                       'verification':q.verification_level} for q in result.results],
           'no_numeric_business_outcome':True,'estimation_handoff_allowed':False},
           ensure_ascii=False,indent=2))


if __name__=='__main__': main()
