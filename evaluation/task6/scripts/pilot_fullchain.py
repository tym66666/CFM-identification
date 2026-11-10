"""Small paired real-model pilot. Model input never includes reference answers.

Each arm starts with the project's maintained Prompt, Skill and schema. The
candidate adds a short source-conflict instruction, with a separate effective
prompt hash. All artifacts are private; this command never grants approval.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
import platform
import pydantic

from cfm_id import project, business_intake
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
from cfm_id_llm.target_first_skill import skill_manifest

PROMPT_ADDENDUM = ('补充检查：先区分原文未提及、材料之间明确冲突、材料已经确定三种情况；'
    '准确保留评价对象、时点与比较方向。不要把有限样本当作总体信息，'
    '不要替研究者接受科学假设。仍严格按给定JSON合同输出，引用必须支持对应字段。')
TARGETED_ADDENDUM = ('补充检查：变量因果图仅指变量之间的因果箭头；随机化、潜在结果独立、'
    '一致性、网络结构或均值充分性都不是变量因果图。原文没有变量图时该字段填UNKNOWN。'
    '每个字段的引用必须支持该字段的完整值：如果值列出具体网点名单或0/1编码，'
    '引用明确列出名单或编码的来源；不要依赖其他字段的引用。'
    '对所有材料逐项核对，业务问题与附件对目标政策相反且未协调时，不要擅自断言某一方案已确定；'
    '遵循既有合同表达不确定或冲突，不要补造事实或批准假设。')


def sha(s):
    return hashlib.sha256(s.encode('utf8')).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')


def case(name):
    # Inputs are versioned separately from references and never include answers.
    root=Path(__file__).resolve().parents[1]
    path=(root/'corrected_cases'/'materials'/(name+'.json') if name.startswith('T6v2-')
          else root/'pilot_cases'/'materials'/(name+'.json'))
    return json.loads(path.read_text(encoding='utf8'))


def run(out, model, base_url, timeout=120, cases=None, arms=None, candidate_version='v1'):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    private=out/'private';private.mkdir()
    config=project.reading_config().model_dump(mode='json')
    cases=cases or ('point','partial','missing','conflict')
    arms=arms or ('baseline','candidate')
    addendum=TARGETED_ADDENDUM if candidate_version=='v2' else PROMPT_ADDENDUM
    if candidate_version=='bound':
        from cfm_id_llm.target_first_skill_guarded import ADDITION
        addendum=ADDITION
    summary=[]
    save(out/'configuration.json',config)
    inputs={name:sha(json.dumps(case(name),ensure_ascii=False,sort_keys=True,separators=(',',':'))) for name in cases}
    save(out/'freeze.json',{'model':model,'base_url':base_url,'timeout':timeout,
        'python_version':platform.python_version(),'pydantic_version':pydantic.__version__,
        'profiles':list(arms),'cases':list(cases),'material_sha256':inputs,
        'candidate_version':candidate_version,'candidate_addendum_sha256':sha(addendum),
        'config':config,'skill':skill_manifest()})
    for name in cases:
        for arm in arms:
            folder=private/(name+'_'+arm);folder.mkdir()
            business=case(name)
            arm_config=dict(config)
            if arm=='candidate' and candidate_version=='bound':
                arm_config['a0_response_contract']='target-first-skill-guarded-1'
            s=business_intake.start_configured(business,arm_config)
            request=business_intake.prepare_request(s)
            effective=request['system_prompt'] + ('\n\n'+addendum if arm=='candidate' and candidate_version!='bound' else '')
            save(folder/'business.json',business)
            save(folder/'request.json',dict(request,effective_system_prompt=effective,
                effective_system_sha256=sha(effective),addendum_loaded=arm=='candidate'))
            p=OpenAICompatibleChatProvider(model=model,base_url=base_url,timeout=timeout,
                max_tokens=16384,thinking='disabled',json_mode=True,require_finish_reason=True)
            row=dict(case=name,arm=arm,api_attempted=True,model=model,
                project_request_sha256=request['request_sha256'],effective_system_sha256=sha(effective),
                addendum_loaded=arm=='candidate',response_received=False,format_valid=False,
                semantic_review='NOT_YET_REVIEWED',citation_review='NOT_YET_REVIEWED',
                final_state='NOT_RUN',independent_replay=False)
            try:
                candidate=p.generate_json(system_prompt=effective,user_prompt=request['user_prompt'])
                save(folder/'model_candidate.json',candidate)
                row['response_received']=True
                # Candidate-arm prompts are not the project's bound request. Do not
                # submit them as if the project had bound the modified prompt.
                s=business_intake.receive_candidate(s,candidate,request_sha256=request['request_sha256'])
                inspected=business_intake.inspect(s)
                save(folder/'inspection.json',inspected)
                save(folder/'intake_snapshot.json',s.model_dump(mode='json'))
                row.update(wire_state=inspected.get('state'),reason_code=inspected.get('reason_code'),
                    format_valid='report' in inspected,
                    internal_binding_is_unmodified_request=(arm=='baseline' or candidate_version=='bound'))
            except Exception as e:
                row.update(wire_state='CALL_OR_PARSE_FAILED',error_type=type(e).__name__,
                           error_code=getattr(e,'code',None))
            row['usage']=p.last_diagnostics.get('usage',{})
            row['transport_calls']=p.last_diagnostics.get('transport_calls',0)
            row['provider_stage']=p.last_diagnostics.get('stage')
            row['provider_status']=p.last_diagnostics.get('status')
            save(folder/'result.json',row);summary.append(row)
            save(out/'partial_summary.json',summary)
            print(json.dumps({k:row.get(k) for k in ('case','arm','wire_state','reason_code','usage')},ensure_ascii=False),flush=True)
    save(out/'manifest.json',{'model':model,'base_url':base_url,'timeout':timeout,
        'config':config,'skill':skill_manifest(),'runs':len(summary),
        'cases':len(cases),'attempts':len(cases)*len(arms),'candidate_version':candidate_version,
        'candidate_addendum_sha256':sha(addendum),
        'candidate_binding_warning':('Bound experimental profile; independent field/science review still required.'
            if candidate_version=='bound' else 'Experimental prompt differs from project request binding; A0 inspection only.'),
        'fact_and_full_chain':'NOT_EXECUTED', 'reference_independent_review':'PENDING'})
    save(out/'summary.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--cases',nargs='+',choices=['point','partial','missing','conflict']+
        ['T6v2-'+case+'-'+variant for case in ('N03','N04','N08','D12') for variant in ('missing','conflict')])
    parser.add_argument('--arms',nargs='+',choices=['baseline','candidate'])
    parser.add_argument('--candidate-version',choices=['v1','v2','bound'],default='v1')
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--key-stdin',action='store_true',help='Read a key from stdin without storing it')
    args=parser.parse_args()
    if args.key_stdin:
        if sys.stdin.isatty():
            import getpass
            key=getpass.getpass('API key (not echoed): ')
        else:
            key=sys.stdin.readline().strip()
        if not key: raise ValueError('API key not supplied')
        os.environ['CFM_ID_LLM_API_KEY']=key
    run(args.output,args.model,args.base_url,args.timeout,args.cases,args.arms,args.candidate_version)
