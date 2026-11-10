"""Source-bound review of one observed fictional missing-condition response.

The expected values are explicit, not generated from the response. Fails closed
on any change. Synthetic research authority is required for this fictional case;
the reviewer is identified as AI. This is not independent human sign-off.
"""
import argparse
import json
from pathlib import Path
from cfm_id import business_intake,business_field_review,project

# value, exact actual citation refs, source evidence and decision rationale.
CHECKS={
 'common.analysis_unit':('7个服务网点：中心、网点1、网点2、网点3、网点4、网点5、网点6',['s0002'],'study确实逐一列出七个服务网点。'),
 'common.treatment':('使用AI助手记1，不使用记0',['s0002'],'study明确使用AI和二元编码。'),
 'common.outcome':('本周任务是否按时完成，完成记1、未完成记0',['s0002'],'study明确本周任务和二元结果定义。'),
 'common.assignment_family':('COMPLETE_RANDOMIZATION',['s0004'],'assignment说明恰好抽三个且等概率。'),
 'common.assignment_law':('每轮均匀随机抽取恰好3个网点使用AI；所有同人数名单等概率',['s0004'],'assignment明确固定名额及均匀概率。'),
 'common.unit_network':('固定处理前简单无向网络：中心—网点1、中心—网点2、中心—网点3、中心—网点4、中心—网点5、中心—网点6，没有其他边',['s0003'],'network明确处理前无向星形网络和完整边。'),
 'common.variable_causal_graph':('UNKNOWN',[],'材料是对象网络，未给变量因果图，保留未知。'),
 'queries.q1.goal':('如果这7个网点都使用AI助手，评价全部这些网点、每个网点权重相同，平均按时完成率能否由现有总体信息唯一确定？',['s0001'],'业务问题完整给出目标和评价方式。'),
 'queries.q1.kind':('FIXED_POLICY_VALUE',['s0001'],'业务问题要求单个全启用政策的平均水平。'),
 'queries.q1.semantics.target_population':('全部这些网点（7个：中心、网点1、网点2、网点3、网点4、网点5、网点6）',['s0001','s0002'],'问题要求全部网点，study给出完整名单。'),
 'queries.q1.semantics.neighbor_exposure':('UNKNOWN',[],'问题给定完整政策，没有单独提出同伴状态。'),
 'queries.q1.semantics.aggregation':('每个网点权重相同，等权平均',['s0001'],'业务问题明确全部网点权重相同的平均。'),
 'queries.q1.semantics.time_horizon':('本周',['s0002'],'study明确考察本周任务是否完成。'),
 'queries.q1.semantics.standardization_distribution':('UNKNOWN',[],'业务问题未要求跨背景标准化。'),
 'queries.q1.comparison_order':('NOT_APPLICABLE',['s0001'],'业务问题是单个水平，不是两个政策之差。'),
 'queries.q1.semantics.first_arrangement':('全部7个网点都使用AI助手（处理=1）',['s0001','s0002'],'问题明确全体使用，study提供使用记1的编码。'),
 'queries.q1.semantics.second_arrangement':('NOT_APPLICABLE',[],'业务问题没有第二政策，不适用。'),
 'queries.q1.semantics.conditioning_context':('UNKNOWN',[],'业务问题未给出额外条件背景。'),
 'queries.q1.semantics.outcome':('本周按时完成',['s0002','s0016'],'study和bounds说明本周任务按时完成。'),
 'queries.q1.semantics.decision_constraints':('UNKNOWN',[],'业务问题没有额外决策限制。'),
}

POINT_CHECKS=dict(CHECKS, **{
 'common.analysis_unit':('5个服务网点：中心、网点1、网点2、网点3、网点4',['s0002'],'study逐一列出五个网点。'),
 'common.treatment':('使用AI助手记1、不使用记0',['s0002'],'study明确AI二元编码。'),
 'common.assignment_family':('INDEPENDENT_BERNOULLI',['s0004'],'assignment明确各网点独立以1/2概率抽签。'),
 'common.assignment_law':('每个网点各自独立以1/2概率使用AI，所有网点的抽签相互独立',['s0004'],'assignment明确独立分配。'),
 'common.unit_network':('固定的处理前简单无向网络，边为中心—网点1、中心—网点2、中心—网点3、中心—网点4，没有其他边',['s0003'],'network明确完整星形边。'),
 'queries.q1.goal':('如果这5个网点都使用AI助手，评价全部这些网点、每个网点权重相同，平均按时完成率能否由现有总体信息唯一确定？',['s0001'],'问题明确评价范围、政策和目标。'),
 'queries.q1.semantics.target_population':('全部这些网点：中心、网点1、网点2、网点3、网点4',['s0001','s0002'],'问题要求全部网点，study提供名单。'),
 'queries.q1.semantics.aggregation':('每个网点权重相同，平均按时完成率',['s0001'],'问题明确等权平均。'),
 'queries.q1.semantics.first_arrangement':('5个网点都使用AI助手',['s0001'],'问题明确五网点均使用AI，此处未使用编码。'),
 'queries.q1.semantics.outcome':('本周任务是否按时完成，完成记1、未完成记0',['s0002'],'study明确结果及编码。'),
})

PARTIAL_CHECKS=dict(CHECKS, **{
 'common.treatment':('使用AI助手，记1；不使用记0',['s0002'],'study明确使用AI的二元编码。'),
 'common.assignment_law':('原试点每轮均匀随机抽取恰好3个网点使用AI；所有同人数名单等概率',['s0004'],'assignment明确均匀固定名额。'),
 'common.unit_network':('固定处理前简单无向网络，边为中心—网点1、中心—网点2、中心—网点3、中心—网点4、中心—网点5、中心—网点6，没有其他边',['s0003'],'network明确固定且完整的星形边。'),
 'queries.q1.semantics.target_population':('全部这些网点：中心、网点1、网点2、网点3、网点4、网点5、网点6',['s0001','s0002'],'问题要求全部网点，study提供名单。'),
 'queries.q1.semantics.aggregation':('每个网点权重相同，平均',['s0001'],'业务问题明确等权平均。'),
 'queries.q1.semantics.outcome':('本周任务是否按时完成，完成记1、未完成记0',['s0002'],'study提供结果及编码。'),
 'queries.q1.semantics.first_arrangement':('所有7个网点都使用AI助手',['s0001'],'问题明确所有网点使用AI，此字段未使用二元编码。'),
})


def run(folder,output,case_name='missing'):
    folder,output=Path(folder),Path(output);output.mkdir(parents=True,exist_ok=False)
    s=business_intake._checked(json.loads((folder/'intake_snapshot.json').read_text(encoding='utf8')))
    if s.case.case_id!='T6-pilot-'+case_name:raise ValueError('Unexpected case')
    expected_material=json.loads((Path(__file__).resolve().parents[1]/'pilot_cases/materials'/f'{case_name}.json').read_text(encoding='utf8'))
    if s.case.model_dump(mode='json')!=expected_material:
        raise ValueError('Source materials changed; these explicit reviews do not apply')
    checks=POINT_CHECKS if case_name=='point' else PARTIAL_CHECKS if case_name=='partial' else CHECKS
    sheet=business_field_review.prepare(s,'q1',authority='SYNTHETIC_TEST')['field_worksheet']
    if set(sheet['fields'])!=set(checks):raise ValueError('Worksheet fields changed')
    decisions={}
    for field,(expected,refs,reason) in checks.items():
        row=sheet['fields'][field];v=row['candidate']
        actual=(v.get('value') if v.get('state') in ('STATED','INTERPRETED') else v.get('state')) if isinstance(v,dict) else v
        if isinstance(v,dict) and 'operation' in v:actual=v['operation']
        actual_refs=[x['ref'] for x in row['actual_citations']]
        if actual!=expected or actual_refs!=refs:raise ValueError('Candidate or citations differ: '+field)
        evidence=refs or ['s0001']
        if len(reason)<12:reason += ' 已逐项核对该字段的值与引用。'
        decisions[field]=dict(field_role='ACCEPTED',value_state='ACCEPTED',source_coverage='ACCEPTED',
                              reason=reason,source_ids=evidence)
    review=dict(version=business_field_review.VERSION,binding_sha256=sheet['binding_sha256'],
        authority='SYNTHETIC_TEST',reviewer='Codex AI delegated audit of fictional case',
        evidence='逐项对照虚构业务原文和本次真实模型候选；这不是独立人类签审或生产科学批准。',decisions=decisions)
    submitted=business_field_review.submit(s,'q1',review,authority='SYNTHETIC_TEST')
    if submitted['state']!='READY_TO_READ':raise ValueError('A0 review was not accepted: '+str(submitted['reason_code']))
    entry=project.prepare_reader(s,'q1',query_review=submitted['query_review'])
    for name,data in [('intake_snapshot',s.model_dump(mode='json')),('a0_review',review),('a0_submitted',submitted),('fact_entry',entry)]:
        (output/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'state':entry['state'],'reader_id':entry.get('reader_id'),
      'request_sha256':entry.get('request_sha256'),'audit':'SYNTHETIC_TEST_BY_CODEX_AI'},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',required=True);p.add_argument('--output',required=True)
    p.add_argument('--case',choices=['missing','point','partial'],default='missing')
    a=p.parse_args();run(a.folder,a.output,a.case)
