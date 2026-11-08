"""Stateful browser adapter. A browser supplies reviews, never proofs or approvals by default."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
import base64
import json
import threading
import time

from .runtime import PROJECT_ROOT, identification_modules
from .provider import PROVIDERS, make_provider, generate

project, intake, dispatch = identification_modules()
from cfm_id import business_field_review
from cfm_id_llm.document_intake import create_intake, AttachmentRequestV07
from .review_summary import summarize
from . import capabilities

PUBLIC = PROJECT_ROOT / 'demo'
MAX_UPLOAD = 20 * 1024 * 1024


def plain(value):
    return value.model_dump(mode='json') if hasattr(value, 'model_dump') else value


def pending(sheet, authority):
    value = {**capabilities.identity(sheet), **{k: deepcopy(sheet[k]) for k in ('decisions', 'material_decisions') if k in sheet}}
    value.update(authority=authority, reviewer='', evidence='')
    if sheet['version'].startswith(('network-information-evidence', 'network-contrast-information-evidence')):
        value.update(disposition='PENDING', table_source_ids=[], supporting_source_ids=[])
    return value


@dataclass
class Run:
    owner: str
    id: str = field(default_factory=lambda: uuid4().hex)
    created: float = field(default_factory=time.time)
    stage: str = 'PREPARING'
    busy: bool = False
    error: dict | None = None
    case: dict | None = None
    intake: object = None
    query_id: str | None = None
    query_review: dict | None = None
    entry: dict | None = None
    submission: dict | None = None
    plan: dict | None = None
    reviews: dict = field(default_factory=dict)
    review_kind: str | None = None
    review_sheets: dict = field(default_factory=dict)
    review_templates: dict = field(default_factory=dict)
    result: dict | None = None
    estimate: dict | None = None
    queries: list = field(default_factory=list)
    events: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    attachment_report: dict | None = None
    data: object = None
    network: object = None
    synthetic: bool = False
    provider: str = 'longcat'
    automatic_review: bool = False
    automatic_rechecks: int = 0
    automatic_audit_repairs: int = 0
    automatic_a0_format_repairs: int = 0
    automatic_fact_format_repairs: int = 0
    automatic_focused_stages: set = field(default_factory=set)
    user_question: dict | None = None
    lock: object = field(default_factory=threading.RLock)

    @property
    def authority(self):
        return 'SYNTHETIC_TEST' if self.synthetic else 'EXTERNAL_RESEARCH_REVIEW'


class Engine:
    def __init__(self, storage, *, max_api_calls=20, provider_factory=make_provider):
        self.storage = Path(storage).resolve(); self.storage.mkdir(parents=True, exist_ok=True)
        self.runs = {}; self.credentials = {}; self.calls = 0; self.max_api_calls = max_api_calls
        self.provider_factory = provider_factory; self.lock = threading.RLock()
        self.examples = json.loads((PUBLIC/'examples.json').read_text('utf8'))
        self.web_capabilities = capabilities.inventory()

    def credential(self, owner, provider, key):
        if provider not in PROVIDERS: raise ValueError('UNKNOWN_PROVIDER')
        if not isinstance(key, str) or len(key)>2048 or any(c.isspace() for c in key):
            raise ValueError('INVALID_API_KEY')
        with self.lock:
            if key: self.credentials[owner] = (provider, key, time.time())
            else: self.credentials.pop(owner, None)
        return {'configured': bool(key), 'provider': provider, 'stored': 'PROCESS_MEMORY_ONLY'}

    def health(self, owner):
        with self.lock:
            credential=self.credentials.get(owner)
            if credential and time.time()-credential[2]>8*3600:
                self.credentials.pop(owner,None); credential=None
            return dict(ready=True, configured=credential is not None,
                provider=credential[0] if credential else 'longcat', providers=PROVIDERS,
                features=['located_fact_recheck','background_reading_review','typed_assumption_choices','typed_reading_audit',
                          'information_data_descriptions','explicit_audit_findings','network_file_input','local_input_preview'],
                reading_config=capabilities.reading_config().model_dump(mode='json'),
                identification_capabilities=self.web_capabilities,
                condition_terms=capabilities.presentation_catalog(),
                model_calls=self.calls, call_limit=self.max_api_calls)

    def get(self, owner, run_id):
        with self.lock:
            run=self.runs.get(run_id)
        if run is None or run.owner!=owner: raise ValueError('RUN_NOT_FOUND')
        return run

    def _clean(self, value, extra_keys=()):
        # Neither raw provider failures nor imported keys enter saved results.
        with self.lock: keys=[*extra_keys,*[c[1] for c in self.credentials.values()]]
        def clean(v):
            if isinstance(v,str):
                for key in keys: v=v.replace(key,'[REDACTED]')
                return v
            if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
            if isinstance(v,list): return [clean(x) for x in v]
            return v
        return clean(value)

    def save(self, run, name, value):
        value=self._clean(plain(value)); run.artifacts[name]=value
        folder=self.storage/run.id; folder.mkdir(exist_ok=True)
        (folder/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

    def event(self, run, stage, message):
        run.stage=stage; run.events.append(dict(stage=stage,message=message,time=time.time()))

    def view(self, owner, run_id):
        run=self.get(owner,run_id)
        with run.lock:
            from . import recovery
            return deepcopy(dict(id=run.id,stage=run.stage,busy=run.busy,error=run.error,
                created=run.created,events=run.events,queries=run.queries,query_id=run.query_id,
                case=run.case,attachment_report=run.attachment_report,
                review_kind=run.review_kind,review_sheets=run.review_sheets,review_templates=run.review_templates,
                plan=run.plan,result=run.result,estimate=run.estimate,
                synthetic=run.synthetic,provider=run.provider,review_summary=summarize(run),
                recheck_preview=recovery.public(recovery.prepare(run)),
                automatic_review=run.automatic_review,user_question=run.user_question,
                automatic_audit_repairs=run.automatic_audit_repairs,
                automatic_a0_format_repairs=run.automatic_a0_format_repairs,
                can_retry_reading=bool(run.automatic_review and run.error and run.review_kind in ('query','source','changes')),
                can_estimate=False,
                downloads=list(run.artifacts)))

    def launch(self, run, function, *args):
        with run.lock:
            if run.busy: raise ValueError('RUN_ALREADY_BUSY')
            run.busy=True; run.error=None
        def work():
            try:
                function(run,*args)
                if run.automatic_review:self._continue_automatically(run)
            except Exception as exc:
                code=getattr(exc,'code',None) or getattr(exc,'reason',None) or type(exc).__name__
                # Provider exceptions have deliberately bounded messages. Do not
                # serialize arbitrary exception text which may include credentials.
                message=str(exc)[:2000] if isinstance(exc,ValueError) else '本阶段未完成，请查看诊断或补充材料后新建读取。'
                run.error=self._clean(dict(code=code,message=message))
                self.event(run,'STOPPED','本阶段停止，未生成新的识别结论。')
                self.save(run,'error',run.error)
            finally:
                with run.lock:run.busy=False
        threading.Thread(target=work,daemon=True).start()

    def start(self, owner, payload):
        if payload.get('use_example_data'):
            raise ValueError('ESTIMATION_NOT_IN_IDENTIFICATION_DEMO')
        if payload.get('allow_send') is not True:raise ValueError('EXTERNAL_DOCUMENT_SHARING_CONSENT_REQUIRED')
        question=payload.get('question','')
        if not isinstance(question,str) or not 3<=len(question.strip())<=25000:raise ValueError('BUSINESS_QUESTION_REQUIRED')
        run=Run(owner=owner,synthetic=payload.get('synthetic') is True,
                automatic_review=payload.get('automatic_review') is True)
        if len(self.runs)>=100:raise ValueError('LOCAL_RUN_LIMIT_RESTART_SERVER')
        with self.lock:
            selected=payload.get('provider');credential=self.credentials.get(owner)
            if selected is not None:
                if selected not in PROVIDERS:raise ValueError('UNKNOWN_PROVIDER')
                if credential is None or time.time()-credential[2]>8*3600:raise ValueError('API_KEY_REQUIRED')
                if selected!=credential[0]:raise ValueError('PROVIDER_CREDENTIAL_MISMATCH')
            run.provider=selected or (credential[0] if credential else 'longcat')
            self.runs[run.id]=run
        # Input is snapshotted; later edits in the browser start a different run.
        self.launch(run,self._start,deepcopy(payload));return run.id

    def preview_uploads(self, owner, payload):
        run=Run(owner=owner)
        self._start(run,payload,preview_only=True)
        return dict(receipt=run.attachment_report['receipt'],
            factual_data=run.attachment_report.get('factual_data'),
            table_import=run.artifacts.get('table_import_manifest'),
            sources=[s for s in run.case['sources'] if s['source_id'].startswith('att_')])

    def _start(self, run, payload, *, preview_only=False):
        self.event(run,'PREPARING','读取业务原文与上传材料')
        uploads=payload.get('files',[])
        if not isinstance(uploads,list) or len(uploads)>10:raise ValueError('AT_MOST_TEN_UPLOADS')
        folder=self.storage/run.id/'uploads';folder.mkdir(parents=True,exist_ok=True)
        requests=[]; total=0; network_paths={}; table_path=None
        for i,item in enumerate(uploads):
            name=item.get('name','')
            if not isinstance(name,str) or name!=Path(name).name or any(c in name for c in '/\\:'):
                raise ValueError('UPLOAD_NAME_INVALID')
            raw=base64.b64decode(item['content'],validate=True);total+=len(raw)
            if total>MAX_UPLOAD or len(raw)>8*1024*1024:raise ValueError('UPLOAD_SIZE_LIMIT')
            path=folder/(str(i)+'_'+name);path.write_bytes(raw)
            role=item.get('role','document')
            if role in ('network_nodes','network_edges'):
                if role in network_paths:raise ValueError('每类网络表只上传一份；对象表和关系表各一份。')
                network_paths[role]=path
            elif role=='table_data':
                if table_path:raise ValueError('数值表格每次只上传一份。')
                table_path=path
            elif role=='data_dictionary':
                requests.append(AttachmentRequestV07(path=str(path),label=name,purpose='DATA_DICTIONARY',
                    sheet=item.get('sheet'),header_row=item.get('header_row',1)))
            elif role=='document':requests.append(AttachmentRequestV07(path=str(path),label=name))
            else:raise ValueError('IDENTIFICATION_DOCUMENT_UPLOAD_ONLY')
        report=create_intake(case_id=run.id,business_question=payload['question'].strip(),attachments=requests)
        case=report.case.model_dump(mode='json');run.attachment_report=report.model_dump(mode='json',exclude={'case'})
        example_id=payload.get('example_id')
        if example_id:
            example=next((x for x in self.examples if x['id']==example_id),None)
            if example is None:raise ValueError('EXAMPLE_NOT_FOUND')
            originals={s['source_id']:s for s in example['case']['sources']}
            selected=deepcopy(example['case']['sources'])
            if 'source_edits' in payload:
                edits=payload['source_edits']
                if not isinstance(edits,list) or len(edits)>len(originals):raise ValueError('INVALID_EXAMPLE_SOURCES')
                selected=[];seen=set();characters=0
                for edit in edits:
                    sid=edit.get('source_id');text=edit.get('text')
                    if sid not in originals or sid in seen or not isinstance(text,str) or not text.strip():
                        raise ValueError('INVALID_EXAMPLE_SOURCE_EDIT')
                    characters+=len(text)
                    if len(text)>25000 or characters>80000:raise ValueError('EXAMPLE_SOURCE_SIZE_LIMIT')
                    seen.add(sid);selected.append({**originals[sid],'text':text})
            case['sources']=selected+case['sources']
        if network_paths:
            if set(network_paths)!={'network_nodes','network_edges'}:raise ValueError('请同时上传对象表和关系表。')
            from cfm_id_llm.network_files import load_network
            run.network=load_network(network_paths['network_nodes'],network_paths['network_edges'],payload.get('network'))
        elif payload.get('network') is not None:raise ValueError('填写网络说明时，请同时上传对象表和关系表。')
        if table_path:
            from cfm_id_llm.record_files import read_records
            records=read_records(table_path,payload.get('table_mapping'),run.network)
            self.save(run,'table_import_manifest',records['manifest'])
            self.save(run,'factual_data_inventory',records['inventory'])
            for sid,label,value in (
                ('uploaded_data_schema','数据说明（用户提供）',records['schema']),
                ('uploaded_data_inventory','上传文件的实际记录范围（本地检查）',records['inventory'])):
                if any(x['source_id']==sid for x in case['sources']):raise ValueError('DATA_SOURCE_ID_COLLISION')
                case['sources'].append(dict(source_id=sid,kind='OTHER',label=label,text=json.dumps(value,ensure_ascii=False)))
            run.attachment_report['factual_data']=dict(nodes=len(records['schema']['node_ids']),
                features=len(records['schema']['feature_names']),observed=len(records['observed_indices']),
                note='只传字段说明与实际记录范围；不由样本推定总体信息，不调用估计。')
        elif payload.get('table_mapping') is not None:raise ValueError('有列映射但没有表格数据，请重新选择文件。')
        if run.network:
            if any(x['source_id']=='uploaded_network' for x in case['sources']):raise ValueError('NETWORK_SOURCE_ID_COLLISION')
            case['sources'].append(run.network.source());self.save(run,'network_file_manifest',run.network.manifest())
            run.attachment_report['network']=dict(reference=run.network.token,nodes=len(run.network.nodes),
                edges=len(run.network.edges),completeness=run.network.completeness)
        from cfm_id_llm.upload_receipt import receipt
        run.attachment_report['receipt']=receipt(run.attachment_report)
        run.case=case;self.save(run,'case',case)
        if preview_only:return
        if not run.attachment_report['receipt']['ready']:
            run.result=dict(state='NEEDS_INPUT',reason_code='ATTACHMENT_EXTRACTION_INCOMPLETE',backend_called=False,
                independent_replay=False,message='部分附件未读完整，请按上传回执修正文件，再开始读取。',
                clarification_questions=run.attachment_report['receipt']['issues'])
            self.event(run,'STOPPED','附件未完整读取，尚未调用模型；请修正上传文件后重新提交。')
            return
        self._read_case(run)

    def _read_case(self,run):
        config=capabilities.reading_config()
        run.intake=intake.start_configured(run.case,config);self.save(run,'reading_config',config)
        request=intake.prepare_request(run.intake)
        self.event(run,'READING','LLM 正在读取用户目标、两端和评价对象')
        candidate=self.call(run,request,'a0')
        run.intake=intake.receive_candidate(run.intake,candidate,request_sha256=request['request_sha256'])
        self.save(run,'intake',run.intake)
        inspected=intake.inspect(run.intake);self.save(run,'reading_inspection',inspected)
        if (run.automatic_review and inspected.get('reason_code') in ('COMPACT_SCHEMA_REJECTED','A0_SCHEMA_REJECTED','A0_REFERENCE_CONTEXT_MISMATCH')
                and run.automatic_a0_format_repairs<1):
            # Include canonical cross-field validation after wire projection.
            # A new model answer must pass the same contract and semantic review;
            # this never repairs the candidate or overrides a valid rejection.
            # Retain the original response and intake; no deterministic unwrapping,
            # source completion or change of the original business is performed.
            self.save(run,'a0_initial_intake',run.intake)
            self.save(run,'a0_initial_inspection',inspected)
            run.automatic_a0_format_repairs+=1
            repair=deepcopy(request)
            feedback=dict(code=inspected.get('reason_code'),diagnostics=inspected.get('diagnostics',{}),previous_response=candidate,
                instruction='上次输出未通过本次Schema。请按原输出合同重新返回完整答案，保持原材料中的目标、条件和未知状态。不要修改Schema或为了格式通过而删减业务内容；不批准科学条件。')
            repair['user_prompt']+='\n\n本次格式检查反馈（不是新的业务材料）：\n'+json.dumps(feedback,ensure_ascii=False)
            self.event(run,'READING','业务读取的输出格式有误，后台进行一次格式复查；原材料保持不变')
            candidate=self.call(run,repair,'a0_format_retry')
            run.intake=intake.receive_candidate(run.intake,candidate,request_sha256=request['request_sha256'])
            self.save(run,'intake',run.intake)
            inspected=intake.inspect(run.intake);self.save(run,'reading_inspection',inspected)
        if inspected['state']!='SEMANTIC_REVIEW_REQUIRED':
            run.result=inspected;self.event(run,'STOPPED','读取未通过程序检查；请查看具体原因。');return
        run.queries=inspected['report']['draft']['queries']
        self.event(run,'SELECT_QUERY','业务目标已整理，请选择本次要检查的问题。')
        if len(run.queries)==1:self._select(run,run.queries[0]['query_id'])

    def call(self,run,request,stage):
        with self.lock:
            cred=self.credentials.get(run.owner)
            if cred is None or time.time()-cred[2]>8*3600:raise ValueError('API_KEY_REQUIRED')
            if self.calls>=self.max_api_calls:raise ValueError('LOCAL_API_CALL_LIMIT')
            alias,key,_=cred;self.calls+=1
        run.provider=alias;options=PROVIDERS[alias]
        self.save(run,stage+'_request',request)
        # Clearing a browser key during an in-flight request must not remove
        # that request's redaction boundary.
        def observe(text):self.save(run,stage+'_raw_response',self._clean({'content':text},(key,)))
        client=self.provider_factory(**options,api_key=key,timeout=300,max_tokens=16384,observer=observe)
        try:
            value=generate(client,request,fact=stage=='facts')
            value=self._clean(value,(key,));self.save(run,stage+'_candidate',value);return value
        finally:
            self.save(run,stage+'_transport',dict(provider=alias,model=options['model'],
                diagnostics=client.last_diagnostics,automatic_retries=0))
            client.api_key=None;key=None

    def _set_review(self,run,kind,sheets):
        run.review_kind=kind;run.review_sheets=deepcopy(sheets)
        run.review_templates={name:pending(sheet,run.authority) for name,sheet in sheets.items()}
        self.event(run,'REVIEW_REQUIRED',{'query':'核对模型读到的问题与原文','source':'核对事实和实际引用',
            'notes':'处理模型提出的缺项或备注','information':'核对总体信息的来源范围',
            'science':'确认识别目标与本研究采用的科学条件','changes':'核对复查回答的全部变化','data':'核对数据与估计目标的对应'}[kind])

    def _select(self,run,qid):
        if qid not in [q['query_id'] for q in run.queries]:raise ValueError('UNKNOWN_QUERY')
        if run.submission is not None:raise ValueError('START_NEW_RUN_FOR_ANOTHER_COMPLETED_QUERY')
        run.query_id=qid
        sheet=business_field_review.prepare(run.intake,qid,authority=run.authority)['field_worksheet']
        self._set_review(run,'query',{'query':sheet})

    def action(self,owner,run_id,action,payload):
        run=self.get(owner,run_id)
        if action=='select':self.launch(run,self._select,payload['query_id'])
        elif action=='review':self.launch(run,self._review,payload)
        elif action=='estimate':raise ValueError('ESTIMATION_NOT_IN_IDENTIFICATION_DEMO')
        elif action=='clarify':
            text=payload.get('text','')
            if not isinstance(text,str) or not 3<=len(text.strip())<=8000:raise ValueError('CLARIFICATION_TEXT_REQUIRED')
            self.launch(run,self._clarify,text.strip())
        elif action=='retry_reading':
            if not run.automatic_review or not run.error or run.review_kind not in ('query','source','changes'):
                raise ValueError('NO_RETRYABLE_READING')
            self.launch(run,self._retry_reading)
        elif action=='recheck':
            from . import recovery
            with run.lock:
                if run.busy:raise ValueError('RUN_ALREADY_BUSY')
                entry,feedback=recovery.request(run,payload.get('binding_sha256'))
                self.launch(run,self._recheck,entry,feedback)
        else:raise ValueError('UNKNOWN_ACTION')

    def _retry_reading(self,run):
        self.event(run,'PREPARING','按用户请求重新进行后台读取复核，原材料保持不变')

    def _clarify(self,run,text):
        number=1+sum(k.startswith('input_revision_') for k in run.artifacts)
        self.save(run,f'input_revision_{number}',dict(case=run.case,intake=plain(run.intake),
            submission=run.submission,reviews=run.reviews,plan=run.plan,result=run.result))
        run.case=deepcopy(run.case)
        run.case['sources'].append(dict(source_id=f'user_reply_{uuid4().hex[:8]}',kind='OTHER',label='用户补充说明',text=text))
        self.save(run,'case',run.case)
        run.intake=None;run.entry=None;run.submission=None;run.query_review=None;run.query_id=None
        run.queries=[];run.reviews={};run.plan=None;run.result=None;run.estimate=None
        run.review_kind=None;run.review_sheets={};run.review_templates={};run.user_question=None
        run.automatic_rechecks=0;run.automatic_audit_repairs=0;run.automatic_a0_format_repairs=0;run.automatic_fact_format_repairs=0
        run.automatic_focused_stages.clear()
        self.event(run,'PREPARING','已保存补充说明，重新核对本次问题；旧审核不直接沿用')
        self._read_case(run)

    def _recheck(self,run,entry,feedback):
        number=len(entry['reading_revision']['steps'])
        self.save(run,f'facts_before_recheck_{number}',run.submission)
        self.save(run,f'feedback_recheck_{number}',feedback)
        for name in ('facts_request','facts_candidate','facts_raw_response','facts_transport'):
            if name in run.artifacts:self.save(run,f'{name}_before_recheck_{number}',run.artifacts[name])
        self.event(run,'READING_RECHECK','正在按原材料复核标出的说明；不会自动增加条件或接受改动')
        raw=self._read_facts(run,entry)
        # New candidate invalidates old source/science/change approvals.
        run.entry=entry
        run.submission=dict(query_review=run.query_review,candidate=raw,
            request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'])
        run.reviews={};run.result=None;run.estimate=None
        self._plan(run)

    def _read_facts(self,run,entry):
        """One explicit schema retry; never edit candidate data or grant review."""
        from pydantic import ValidationError
        from cfm_id_llm.fact_wire_models import model_for
        from cfm_id_llm import file_coordinates as fact_coordinates
        from cfm_id_llm import network_file_binding
        from cfm_id_llm.network_files import NetworkFileError
        tables=None
        if run.network is not None:
            entry,tables=fact_coordinates.prepare_for_graph(entry,list(run.network.nodes),run.network.edges)
        entry,network_binding=network_file_binding.prepare(entry,run.network)
        def read(request):
            answer=self.call(run,request,'facts')
            candidate=fact_coordinates.expand(answer,tables)
            candidate=network_file_binding.expand(candidate,network_binding)
            if tables is not None or network_binding is not None:
                self.save(run,'facts_expanded',candidate)
            if network_binding is not None:
                self.save(run,'network_file_binding',dict(reference=run.network.token,
                    source_ids=network_binding['source_ids'],arrays_match=True,scientific_approval=False))
            return candidate
        model=model_for(entry)
        try:
            raw=read(entry)
            if model is not None:model.model_validate(deepcopy(raw))
            return raw
        except (fact_coordinates.CoordinateError,NetworkFileError) as exc:
            raw=run.artifacts['facts_candidate']
            diagnostics=[dict(code=str(exc),path='/study or /information/arm_cells')]
        except ValidationError as exc:
            if tables is not None or network_binding is not None:
                raw=run.artifacts['facts_candidate']
            diagnostics=[dict(path='/'+'/'.join(map(str,e['loc'])),code=e['type'],message=e['msg'])
                         for e in exc.errors(include_input=False,include_url=False)]
        self.save(run,'facts_format_validation',dict(valid=False,errors=diagnostics))
        if run.automatic_fact_format_repairs>=1:
            raise ValueError('FACT_READING_FORMAT_INVALID_AFTER_RETRY')
        run.automatic_fact_format_repairs+=1
        for name in ('facts_request','facts_candidate','facts_raw_response','facts_transport'):
            if name in run.artifacts:self.save(run,name+'_before_format_retry',run.artifacts[name])
        repair=deepcopy(entry);request=repair['request']
        key='user' if 'user' in request else 'user_prompt'
        request[key]+='\n\n'+json.dumps(dict(format_feedback=dict(errors=diagnostics,previous_response=raw,
            instruction='上次输出违反本次Schema/字段组合规则。请根据同一份原材料重新读取并输出完整候选；不添加条件、不自动补事实、不批准假设。后续来源与科学审核仍须执行。')),ensure_ascii=False)
        self.event(run,'READING_FACTS','读取输出存在字段组合错误，后台进行一次格式复查；原材料保持不变')
        raw=read(repair)
        if model is not None:model.model_validate(deepcopy(raw))
        self.save(run,'facts_format_retry_validation',dict(valid=True,scientific_approval=False))
        return raw

    def _continue_automatically(self,run):
        from . import automatic_review as audit
        from . import recovery
        run.user_question=None
        for _ in range(8):
            # A query gate can stop before a fact reader is available. Do not
            # audit that already-final result again merely because the former
            # query worksheet is still present.
            if run.result is not None:return
            if run.review_kind not in audit.STAGES:return
            # Audit first: residual notes can be genuine restrictions. Spend
            # the bounded reread only on a located model-reading error.
            self.event(run,'REVIEWING_READING','正在后台核对业务解释与原文来源，不需要逐字段操作')
            request,fields,sources=audit.request(run)
            number=1+sum(k.startswith('reading_audit_') and k.endswith('_request') for k in run.artifacts)
            stage=f'reading_audit_{number}'
            raw=self.call(run,request,stage)
            try:
                answer=audit.check(raw,fields,sources,require_current=True)
            except ValueError as exc:
                # At most one explicit audit-contract retry per run. This does
                # not retry transport, repair the reading, or overturn a valid
                # adverse audit. Preserve both replies and all current evidence.
                code=str(exc)
                self.save(run,stage+'_validation',dict(valid=False,code=code))
                if code=='READING_AUDIT_PERMISSION_INVALID' or run.automatic_audit_repairs>=1:raise
                run.automatic_audit_repairs+=1
                repair=deepcopy(request);body=json.loads(repair['user_prompt'])
                body['audit_contract_feedback']=dict(code=code,previous_response=raw,
                    instruction='上次复核输出不符合本次合同。原材料和待审候选未变；请重新核对并按output_schema提交完整复核。不能因格式修复默认通过，不得改业务候选或批准科学条件。')
                repair['user_prompt']=json.dumps(body,ensure_ascii=False)
                self.event(run,'REVIEWING_READING','后台复核的回复格式有误，正在进行一次格式复查；业务材料保持不变')
                stage=f'reading_audit_{number+1}'
                answer=audit.check(self.call(run,repair,stage),fields,sources,require_current=True)
            self.save(run,stage+'_validated',answer)
            focus_scope = 'query' if run.review_kind == 'query' else 'source'
            if answer['verdict']=='READING_ERROR' and focus_scope not in run.automatic_focused_stages:
                focused,disputed=audit.focused_request(request,fields,answer)
                # Query and fact audits inspect different candidates. Each gets
                # at most one follow-up, including failures; rereads do not reset it.
                run.automatic_focused_stages.add(focus_scope)
                focus_stage = 'focused_audit' if not run.artifacts.get('focused_audit_completed') else 'focused_audit_'+focus_scope
                self.save(run,focus_stage+'_completed',dict(started=True,scope=focus_scope,fields=list(disputed)))
                self.event(run,'REVIEWING_READING','后台正在定位复核有分歧的解释；原文和候选保持不变')
                followup=audit.check_focused(self.call(run,focused,focus_stage),disputed,sources)
                self.save(run,focus_stage+'_validated',followup)
                answer=audit.reconcile(answer,followup,disputed)
                self.save(run,'reconciled_reading_audit',answer)
            if answer['verdict']=='PASS':
                run.stage='REVIEW_REQUIRED'
                self._review(run,audit.records(run,answer));continue
            # Reuse validated field/source locations, not a generic note sweep.
            # Feedback remains a request to reread, never a replacement answer.
            if answer['verdict']=='READING_ERROR' and run.automatic_rechecks<1:
                preview=recovery.prepare(run,allow_busy=True,audit_findings=answer['issues'])
                if preview['available']:
                    entry,feedback=recovery.request(run,preview['binding_sha256'],allow_busy=True,
                                                    audit_findings=answer['issues'])
                else:entry=None
                if entry:
                    run.automatic_rechecks+=1;self._recheck(run,entry,feedback);continue
            if answer['verdict']=='READING_ERROR':
                run.user_question=None
                run.error=dict(code='READING_REVIEW_DISAGREEMENT',message='Independent model review could not confirm the reading; see saved audit issues.')
                self.event(run,'STOPPED','系统对材料的解释仍有分歧，尚未开始识别；可重试复核，不必增加研究条件。')
                return
            questions=deepcopy(answer['issues'])
            for issue in questions:
                field=fields[issue['field']]
                path=field.get('change',{}).get('field_path',issue['field'])
                if 'additional_restrictions' in path:
                    issue['display_question']='下面这些说明是在描述已有资料与待确认事项，还是希望为本次计算另外增加条件？请说明你的原意。'
                issue['source_texts']=[sources[sid].get('text',sources[sid].get('quote',''))
                                      if isinstance(sources[sid],dict) else sources[sid] for sid in issue['source_ids']]
            run.user_question=dict(kind=answer['verdict'],items=questions,
                message='系统对下面的说明仍有理解分歧，请说明原意；不需要修改数据或为了通过而增加假设。' if answer['verdict']=='READING_ERROR' else '原材料还不能确定以下内容。')
            self.event(run,'REVIEW_REQUIRED','需要补充以下信息后才能继续')
            return
        raise ValueError('AUTOMATIC_REVIEW_STEP_LIMIT')

    def _review(self,run,payload):
        if run.stage not in ('REVIEW_REQUIRED','STOPPED') or not run.review_kind:raise ValueError('NO_CURRENT_REVIEW')
        if payload.get('kind')!=run.review_kind:raise ValueError('STALE_REVIEW_STAGE')
        records=payload['records']
        if set(records)!=set(run.review_templates):raise ValueError('EXACT_REVIEW_SET_REQUIRED')
        for name,sheet in run.review_sheets.items():
            r=records[name]
            if capabilities.identity(r)!=capabilities.identity(sheet) or r.get('authority')!=run.authority:
                raise ValueError('STALE_OR_WRONG_AUTHORITY_REVIEW')
        kind=run.review_kind;self.save(run,kind+'_review',records)
        if kind=='query':
            result=business_field_review.submit(run.intake,run.query_id,records['query'],authority=run.authority)
            if result['state']!='READY_TO_READ':
                run.result=result;self.save(run,'query_gate_result',result)
                self.event(run,'STOPPED','当前读取尚不能进入后续方法；停止原因已保留，不重复调用后台复核。');return
            run.result=None
            run.query_review=result['query_review']
            run.entry=project.prepare_reader(run.intake,run.query_id,query_review=run.query_review)
            self.event(run,'READING_FACTS','LLM 正在读取设计、总体信息和科学条件')
            raw=self._read_facts(run,run.entry)
            run.submission=dict(query_review=run.query_review,candidate=raw,request_sha256=run.entry['request_sha256'])
            self._plan(run)
        elif kind in ('source','notes','information','changes'):
            key={'source':'source_review','notes':'note_review','information':'information_evidence_review','changes':'change_review'}[kind]
            run.submission[key]=records[kind];self._plan(run)
        elif kind=='science':
            confirmed_summary=summarize(run)
            run.reviews['plan_review']=records['plan']
            run.reviews['native_reviews']={row['method']:{name:records[row['method']+'.'+name]
                for name in ('reading_review','science_review')} for row in run.plan['methods']
                if 'reading_worksheet' in row and 'science_worksheet' in row}
            self.event(run,'IDENTIFYING','应用已有定理并独立重放证书')
            execution_reviews={**run.reviews,'native_reviews':dispatch.native_reviews_from_json(run.plan,run.reviews['native_reviews'])}
            run.result=project.execute(run.intake,run.query_id,**run.submission,**execution_reviews,research_protocol_selected=True)
            # Presentation metadata only; native claims and certificates stay intact.
            if run.result.get('independent_replay') is True and confirmed_summary.get('contract')==capabilities.CONTRACT:
                run.result['web_review_summary']=confirmed_summary
            self.save(run,'identification',run.result);run.review_kind=None;run.review_sheets={};run.review_templates={}
            self.event(run,'RESULT','本问题的识别执行已结束。')
        else:
            raise ValueError('UNKNOWN_IDENTIFICATION_REVIEW_STAGE')

    def _plan(self,run):
        run.result=None
        run.plan=project.inspect_methods(run.intake,run.query_id,**run.submission);self.save(run,'plan',run.plan)
        for key,kind in [('reading_change_worksheet','changes'),('source_review_worksheet','source'),('note_review_worksheet','notes'),('information_evidence_worksheet','information')]:
            if key in run.plan:
                self._set_review(run,kind,{kind:run.plan[key]});return
        if 'plan_worksheet' in run.plan:
            sheets={'plan':run.plan['plan_worksheet']}
            for row in run.plan.get('methods',[]):
                for field,name in [('reading_worksheet','reading_review'),('science_worksheet','science_review')]:
                    if field in row:sheets[row['method']+'.'+name]=row[field]
            self._set_review(run,'science',sheets);return
        run.result=run.plan;run.review_kind=None;run.review_sheets={};run.review_templates={}
        self.event(run,'RESULT','材料缺项或当前方法不适用；按实际停止原因报告。')
