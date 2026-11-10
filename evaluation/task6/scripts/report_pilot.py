"""Generate a redacted report from saved pilot runs; no model calls."""
import hashlib
import json
from pathlib import Path


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))


def report(first,targeted,rereads,output):
    first,targeted,output=Path(first),Path(targeted),Path(output)
    a=read(first/'summary.json');b=read(targeted/'summary.json')
    retries=[]
    for p in map(Path,rereads):
        r=read(p/'result.json')
        if r.get('response_received') and (p/'inspection.json').exists():
            inspection=read(p/'inspection.json');gate=inspection.get('wire_gate') or {}
            r['format_valid']=('report' in inspection or gate.get('status')=='DRAFT_FOR_EXTERNAL_REVIEW')
            r['format_note']='Reclassified using actual wire gate; change review remains required.'
        retries.append(r)
    if len(a)!=8 or len(b)!=3:raise ValueError('Unexpected pilot design; refusing fixed-case report')
    findings={
      ('point','baseline'):('待完整审核','不充分：评价名单列出名称但字段未引用名单来源'),
      ('point','candidate'):('错误：科学条件填入变量因果图','待完整审核'),
      ('partial','baseline'):('未测量','未测量'),
      ('partial','candidate'):('错误：科学条件填入变量因果图','待完整审核'),
      ('missing','baseline'):('待完整审核','不充分：目标值使用0/1编码但未引用编码来源'),
      ('missing','candidate'):('待完整审核','不充分：同伴暴露定义未被本字段引用支持'),
      ('conflict','baseline'):('错误：忽略未协调的反向政策','待完整审核'),
      ('conflict','candidate'):('错误：忽略未协调的反向政策','待完整审核'),
    }
    statuses=[]
    for r in a:
        d=first/'private'/(r['case']+'_'+r['arm'])
        reviews=list(d.glob('*rejection_review.json'))
        if r['response_received'] and len(reviews)!=1:raise ValueError('Missing or ambiguous source rejection record '+str(d))
        blocks=[read(x)['result'].get('state') for x in reviews]
        if r['response_received'] and blocks != ['CHECK_BLOCKED']:
            raise ValueError('Review result is not the expected blocked state '+str(d))
        semantic,citation=findings[(r['case'],r['arm'])]
        statuses.append(dict(case=r['case'],arm=r['arm'],format='PASS' if r['format_valid'] else 'FAIL',
            semantic=semantic,citation=citation,review_gate=blocks or ['CALL_OR_PARSE_FAILED'],
            final_state='NOT_EXECUTED',actual_result_verified=False,
            request_sha256=r['project_request_sha256'],effective_system_sha256=r['effective_system_sha256'],
            usage=r['usage'],provider_error=r.get('error_type')))
    for x in b:
        actual=targeted/'private'/(x['case']+'_'+x['arm'])
        x['actual_candidate_sha256']=(hashlib.sha256((actual/'model_candidate.json').read_bytes()).hexdigest()
                                     if (actual/'model_candidate.json').exists() else None)
    total=sum(x.get('usage',{}).get('total_tokens',0) for x in a+b+retries)
    output.mkdir(parents=True,exist_ok=False)
    data={'first_pass':statuses,'targeted_v2':b,'rereads':retries,'known_reported_tokens':total,
          'failed_call_token_usage':'UNKNOWN', 'full_chain_model_results':'NONE',
          'review_origin':'AI_ASSISTED_NOT_INDEPENDENT_HUMAN',
          'candidate_prompt_binding':'EXPERIMENTAL_UNBOUND_TO_PROJECT_REQUEST_DO_NOT_EXECUTE'}
    (output/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows='\n'.join(f"| {r['case']} | {r['arm']} | {r['format']} | {r['semantic']} | {r['citation']} | {'、'.join(r['review_gate'])} | 未执行 |" for r in statuses)
    rtext='；'.join(f"第{i+1}次 {x.get('wire_state')}（{x.get('error_code') or x.get('reason_code') or '无错误码'}）" for i,x in enumerate(retries))
    body=f'''# 任务6端到端试点：阶段结果

本次在用户授权下使用DeepSeek V4 Flash，基于`target-first-skill-1`推荐配置、4个业务题及附件，进行了8次A0首读：基线和候选各4次。另对3题进行了第二版提示对照，并对点识别题启动{len(retries)}次正式绑定的重读。失败、重读和首答分别保留；没有把人工编写的标准JSON当作模型回答。

## 首答：分层记录

| 业务 | 方案 | 格式 | 业务语义 | 引用 | 实际审核入口 | 最终识别 |
|---|---|---|---|---|---|---|
{rows}

7/8返回并通过项目A0格式入口；部分识别基线1次ProviderError，已保存其请求和状态，但当次错误细节不足以判定具体原因。7个有效首答均有已确认的字段或冲突问题；对这些问题使用实际项目字段审核入口提交拒绝，均返回`CHECK_BLOCKED / DISPATCH_REVIEW_REJECTED`。这里的字段复核为AI辅助，不是独立研究者签审。未全部逐字段审核的项目标为待审核，不将它们算作通过。

特别是冲突题：业务问题指定全体使用AI，附件要求全体不使用且明确未协调；两次首答都直接采用前者。系统读取状态要求审核，没有产生经验证结论；该审核拒绝也没有产生符合要求的澄清问题，不能记作完整的“正确停止”。

## 针对性提示对照

首版候选实际在原Prompt和Skill后追加区分冲突、字段、总体信息及假设的说明，合同与模型相同；完整有效system prompt及哈希保留在受控目录。第二版针对实测误读加入“科学假设不是变量因果图”和“字段引用需覆盖名单与编码”的说明。第二版点识别与部分识别返回格式合法，冲突题调用超时：点识别与部分识别的变量图字段由错误改为UNKNOWN，但点识别的名单值仍只引用业务问题，名单来源未被本字段引用。因此仅可称局部字段变化，不能宣称整题改进或优于基线。小样本、单次结果无统计推断。

**绑定限制：**实验追加的system文本没有被当前项目的原始request_sha256覆盖，故候选结果只能用于读取对照；`n01_fullchain.session()`拒绝将这类未绑定请求的结果送入完整链路。不能把它记成经过项目绑定的识别成绩，不能将该候选配置设为默认。需先实现并审核正式的配置/请求绑定方案。

## 最终识别与数学参考

点识别、部分识别及非点识别、缺项、冲突各有预期；非点识别通过限定模型下sharp区间 `[3/7, 4/7]` 的两个不同端点体现，程序不支持不等于数学非识别。原仓库离线教学例实际得到POINT、PARTIAL及NEEDS_INPUT，其中POINT/PARTIAL均有回放；该例使用固定草稿及合成审核，只是核对数学参考，**不是模型全链路成绩**。

本次7个可读首答均在A0字段审核被阻断，没有真实模型事实读取、科学条件审核、后端执行或证书重放；因此POINT、PARTIAL和非点识别的真实端到端结果均为**未完成**，不能据人工勾选或格式通过宣称成功。`verify_final.py`读取实际项目结果、预期目标、证书/摘要与已记录的回放状态；它本身不重跑证书，也不认证审核人身份。`fact_stage_ledger.py`现在要求相应模型候选、实际执行结果和参考文件；还须对照真正的来源及科学审核记录。

点识别基线的原字段拒绝后，使用项目原生`intake_reading_revision`根据原文定位生成新的绑定重读请求；{rtext}。第二次重读输出的项目wire gate为`DRAFT_FOR_EXTERNAL_REVIEW`，但最终停在变更审核：名单引用由`[s0001]`变为`[s0001,s0002]`，`s0002`确实列出名单；这只是对单一变更的来源核对，不等于已独立签审或完整链路成功。第二次重读的原记录将“尚未完成变更审核”误标为格式失败，本报告按实际wire gate纠正，没有覆盖原始记录。重读不是首答，也不是手工修订。模型响应、复审及人工修改必须分别保留。

## 材料、成本及后续

原题不覆盖，负例冲突/缺项复核见`docs/原题缺项与冲突复核.md`。`pilot_cases/`中的业务材料和参考分离；追问答复已在任何实际追问之前写好，但参考文件是在本次首次读取后整理成文件，不能称事前冻结的独立参考。实际尚无另一位研究者对参考和科学条件的签审。

本次累计 {len(a)+len(b)+len(retries)} 次尝试；已收到provider用量的请求合计 {total:,} token，失败请求的用量未知，不能当成0或推算最终费用。原始请求、候选和审核留在本地`outputs/`，本报告不包含密钥或原始回复。

尚需：取得可追溯的独立研究者审核；让符合原始绑定的真实模型读取得到可审来源；对事实读取、科学条件和数学结果逐级审核，执行后端并用实际证书重放；准备正式绑定的候选提示并按相同题重复对照。后续多模型比较须各自固定题目、标准和版本；当前只有一个模型，无法区分模型系列效应。
'''
    (output/'端到端试点报告.md').write_text(body,encoding='utf8')
    print(json.dumps({'first_attempts':len(a),'targeted_attempts':len(b),'rereads':len(retries),
                      'known_reported_tokens':total,'output':str(output)},ensure_ascii=False))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--first',required=True);p.add_argument('--targeted',required=True)
    p.add_argument('--rereads',nargs='+',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();report(a.first,a.targeted,a.rereads,a.output)
