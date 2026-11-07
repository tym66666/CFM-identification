"""Task 6: auditable N01 real A0 -> A4/A5 -> math Core harness.
Run from the CFM-identification repo root; no automatic approvals or repairs.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from cfm_id import project, business_intake as intake
from cfm_id import business_field_review as fields
from cfm_id import fact_source_review as sources

BASE = Path('outputs/task6_n01_chain')
RUNS = Path('outputs/task6_dev_final_002/private')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'文件已存在，为保护原记录不覆盖：{path}')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda x: x.model_dump(mode='json')), encoding='utf-8')
    print('保存：', path)


def current_dir(args):
    d = Path(args.workdir)
    if not d.exists():
        raise FileNotFoundError(f'先运行 select：{d}')
    return d


def session(d):
    """Accept the Task 6 runner raw intake snapshot or an official checkpoint.

    The runner saves BusinessIntake.model_dump() as intake_snapshot.json,
    while business_intake.restore() only accepts the envelope created by save().
    Never rebuild an intake from scratch: that changes request/binding SHA values.
    """
    path = d / 'intake_snapshot.json'
    value = read(path)
    if isinstance(value, dict) and value.get('kind') == 'BUSINESS_INTAKE_CHECKPOINT':
        return intake.restore(path)
    # Validate the original runner snapshot against the project intake contract.
    return intake._checked(value)


def selected(d):
    return read(d / 'selection.json')


def a0_review(d):
    return read(d / 'a0_submitted.json')['query_review']


def entry_from_review(d):
    e = project.prepare_reader(session(d), 'q1', query_review=a0_review(d))
    if e.get('state') != 'READY_TO_READ':
        raise RuntimeError(f'A0 审核未放行：{e.get("state")} {e.get("reason_code")}')
    return e


def fact_candidate(d):
    return read(d / 'fact_candidate.json')


def source_review(d):
    return read(d / 'source_review_EDIT.json')


def information_review(d):
    p = d / 'information_review_EDIT.json'
    return read(p) if p.exists() else None


def a0_review_template(sheet, reviewer):
    return dict(version=fields.VERSION, binding_sha256=sheet['binding_sha256'],
                authority=sheet['expected_authority'], reviewer=reviewer,
                evidence='请审核者在此填写完整的实际复核依据和原始材料对照。',
                decisions=sheet['decisions'])


def source_review_template(sheet, reviewer):
    return dict(version=sheet['version'],binding_sha256=sheet['binding_sha256'],
                authority=sheet['expected_authority'],reviewer=reviewer,
                evidence='请审核者填写事实内容与原文及引用的真实对照结果。',
                decisions=sheet['decisions'])


def generic_dispatch_template(sheet, reviewer):
    # Keep every schema-owned worksheet field; native review classes may require them.
    d={k:v for k,v in sheet.items() if k not in ('is_approval','decisions')}
    d.update(reviewer=reviewer,evidence='请审核者填写此方法/科学条件的独立审查依据。',
             authority='EXTERNAL_RESEARCH_REVIEW', decisions=sheet.get('decisions', {}))
    return d


def do_select(args):
    if not RUNS.is_dir():
        raise FileNotFoundError(f'找不到开发集私有记录：{RUNS}')
    suffix = '-full' if args.variant=='full' else '-changed'
    available=[]
    for folder in RUNS.iterdir():
        if not folder.is_dir():continue
        rpath=folder/'result.json'; spath=folder/'intake_snapshot.json'
        if not rpath.exists() or not spath.exists():continue
        r=read(rpath)
        if r.get('case_id') != 'T6-N01'+suffix or r.get('profile') != args.profile:continue
        if r.get('format_parse_success') is not True:continue
        if args.repeat and r.get('repeat') != args.repeat:continue
        available.append((folder,r))
    if not available:
        raise ValueError('找不到指定的 N01 已解析记录。可调整 --profile、--repeat。')
    folder,r=sorted(available,key=lambda x:(x[1]['repeat'],x[1]['id']))[0]
    d = Path(args.workdir)
    d.mkdir(parents=True,exist_ok=False)
    shutil.copy2(folder/'intake_snapshot.json',d/'intake_snapshot.json')
    write(d/'selection.json',dict(run_id=r['id'],case_id=r['case_id'],profile=r['profile'],
                                  repeat=r['repeat'],wire_state=r['wire_state'],source_dir=str(folder),
                                  a0_is_independently_approved=False, a4_a5_is_run=False,
                                  core_is_run=False))
    print('选中：',folder)
    print('下一步：a0-worksheet')


def do_a0_worksheet(args):
    d=current_dir(args);s=session(d)
    check=intake.inspect(s)
    if 'report' not in check:
        raise RuntimeError(f'当前 A0 不可进入字段审核：{check.get("state")} {check.get("reason_code")}')
    w=fields.prepare(s,'q1',authority='EXTERNAL_RESEARCH_REVIEW')['field_worksheet']
    write(d/'a0_worksheet.json',w)
    write(d/'a0_review_EDIT.json',a0_review_template(w,args.reviewer))
    print('编辑 a0_review_EDIT.json：逐字段填写三项决定、reason 和真实 source_ids。')
    print('不要批量自动接受；错误应 REJECTED；有疑点应 PENDING。')


def do_a0_submit(args):
    d=current_dir(args)
    r=read(d/'a0_review_EDIT.json')
    result=fields.submit(session(d),'q1',r,authority='EXTERNAL_RESEARCH_REVIEW')
    write(d/'a0_submitted.json',result)
    print('A0审核状态：',result.get('state'),result.get('reason_code'))
    if result.get('state')!='READY_TO_READ':
        print('未通过 A0 门槛，不能继续。')


def do_fact_request(args):
    d=current_dir(args); entry=entry_from_review(d)
    write(d/'fact_entry.json',entry)
    print('reader_id:',entry.get('reader_id'))
    print('fact_request_sha256:',entry['request_sha256'])
    print('下一步 fact-call：会使用学校 API 产生一条新的真实 A4/A5 模型回答。')


def do_fact_call(args):
    if not (args.allow_external and args.allow_material_sharing):
        raise ValueError('真实 API 调用必须同时添加 --allow-external --allow-material-sharing')
    import os
    from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
    if not (os.getenv('CFM_ID_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')):
        raise RuntimeError('缺少 API Key 环境变量')
    d=current_dir(args);entry=read(d/'fact_entry.json')
    fresh=entry_from_review(d)
    if entry['request_sha256']!=fresh['request_sha256']:
        raise RuntimeError('事实请求已过期，不能重用旧 SHA')
    if (d/'fact_candidate.json').exists():
        raise FileExistsError('fact_candidate.json 已存在，不覆盖首次回答；请保留首次调用记录。')
    p=OpenAICompatibleChatProvider(model=args.model,base_url=args.base_url,
                 timeout=300,max_tokens=16384,json_mode=True,thinking='disabled',require_finish_reason=True)
    try:
        raw=p.generate_json(system_prompt=entry['request']['system'],user_prompt=entry['request']['user'])
        write(d/'fact_candidate.json',raw)
        write(d/'fact_call_diagnostics.json',p.last_diagnostics)
    except Exception:
        if not (d/'fact_call_diagnostics.json').exists():
            write(d/'fact_call_diagnostics.json',getattr(p,'last_diagnostics',{}))
        raise
    print('真实 A4/A5 候选已保存，尚未审核，也没有数学批准。')


def do_fact_worksheet(args):
    d=current_dir(args); entry=entry_from_review(d);raw=fact_candidate(d)
    w=sources.prepare(entry,raw)
    write(d/'fact_source_worksheet.json',w)
    write(d/'source_review_EDIT.json',source_review_template(w,args.reviewer))
    try:
        from cfm_id import network_information_evidence as info
        iw=info.prepare(entry,raw)
    except (ValueError,TypeError,KeyError,AttributeError):
        iw=None
    if iw is not None:
        write(d/'information_worksheet.json',iw)
        write(d/'information_review_EDIT.json',dict(version=iw['version'],binding_sha256=iw['binding_sha256'],
             authority=iw['expected_authority'],reviewer=args.reviewer,
             evidence='请审核同一原始总体表及其说明性来源，不得自动批准。',
             disposition='PENDING',table_source_ids=[],supporting_source_ids=[]))
    print('请编辑 source_review_EDIT.json，逐字段独立核对 A4/A5 的事实和引用。')
    if iw is not None:print('额外审核：information_review_EDIT.json')


def do_plan(args):
    d=current_dir(args); e=entry_from_review(d)
    kw=dict(query_review=a0_review(d),candidate=fact_candidate(d),request_sha256=e['request_sha256'],
            source_review=source_review(d))
    if information_review(d) is not None:kw['information_evidence_review']=information_review(d)
    result=project.inspect_methods(session(d),'q1',**kw)
    write(d/'plan.json',result)
    print('plan:',result.get('state'),result.get('reason_code'))
    if result.get('state')=='REVIEW_REQUIRED' and 'plan_worksheet' in result:
        reviews=dict(plan_review=generic_dispatch_template(result['plan_worksheet'],args.reviewer),native_reviews={})
        for method in result.get('methods',[]):
            reviews['native_reviews'][method['method']]=dict(
                reading_review=generic_dispatch_template(method['reading_worksheet'],args.reviewer),
                science_review=generic_dispatch_template(method['science_worksheet'],args.reviewer))
        reviews['research_protocol_selected']=False
        write(d/'scientific_reviews_EDIT.json',reviews)
        print('需要独立审核 scientific_reviews_EDIT.json，每个字段保留 PENDING 直到真实审定。')
    else: print('未进入数学计划审核；保留阻断原因，不能人为改写为 POINT。')


def do_execute(args):
    d=current_dir(args)
    plan=read(d/'plan.json')
    if plan.get('state')!='REVIEW_REQUIRED' or 'plan_worksheet' not in plan:
        print('未达到可审批的计划门槛，保持现有结果：',plan.get('state'),plan.get('reason_code'))
        return
    approvals=read(d/'scientific_reviews_EDIT.json')
    if approvals.get('research_protocol_selected') is not True:
        raise ValueError('独立研究方案尚未确认（research_protocol_selected != true），停止')
    opts=dict(query_review=a0_review(d),candidate=fact_candidate(d),
              request_sha256=entry_from_review(d)['request_sha256'],source_review=source_review(d))
    if information_review(d) is not None:opts['information_evidence_review']=information_review(d)
    result=project.execute(session(d),'q1',**opts,**approvals)
    write(d/'execution_result.json',result)
    print('数学执行:',result.get('state'),result.get('reason_code'),
          'backend_called=',result.get('backend_called'),
          'independent_replay=',result.get('independent_replay'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('step',choices=['select','a0-worksheet','a0-submit','fact-request','fact-call','fact-worksheet','plan','execute'])
    p.add_argument('--workdir',default=str(BASE/'full'))
    p.add_argument('--variant',choices=['full','changed'],default='full')
    p.add_argument('--profile',choices=['prompt_only','prompt_plus_skill'],default='prompt_plus_skill')
    p.add_argument('--repeat',type=int)
    p.add_argument('--reviewer',default='FILL_REAL_REVIEWER_NAME')
    p.add_argument('--model',default='deepseek-v4-flash')
    p.add_argument('--base-url',default='https://newapi.sufe.edu.cn/v1')
    p.add_argument('--allow-external',action='store_true')
    p.add_argument('--allow-material-sharing',action='store_true')
    args=p.parse_args()
    try:
        {
          'select':do_select,'a0-worksheet':do_a0_worksheet,'a0-submit':do_a0_submit,
          'fact-request':do_fact_request,'fact-call':do_fact_call,
          'fact-worksheet':do_fact_worksheet,'plan':do_plan,'execute':do_execute
        }[args.step](args)
    except Exception as e:
        print(f'步骤 {args.step} 未完成：{type(e).__name__}: {e}',file=sys.stderr)
        raise SystemExit(2)

if __name__=='__main__':main()
