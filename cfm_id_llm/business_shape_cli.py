"""Optional natural-language intake using the business-shaped one-call schema.

For budgeted experiments use the audited local runner; this general CLI uses
the existing environment-based credential and explicit sharing switches.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .schemas import BusinessCase
from .document_intake import AttachmentRequestV07
from .material_integrity import create_grounded_intake
from .providers import MockProvider, OpenAICompatibleChatProvider
from .providers.cli_options import add_chat_arguments, chat_options
from .business_formulator import BusinessFormulator
from .reviewed_intake import append_business_reply, render_confirmation_html


def main(argv=None, *, flow_class=BusinessFormulator, render=render_confirmation_html, mock_factory=MockProvider,
         description='普通话问题与附件 → 按问题形式整理 → 中文理解稿（一次模型调用）'):
    p=argparse.ArgumentParser(description=description)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--question');g.add_argument('--question-file');g.add_argument('--resume')
    r=p.add_mutually_exclusive_group();r.add_argument('--reply');r.add_argument('--reply-file')
    p.add_argument('--case-id',default='business_intake');p.add_argument('--attachment',action='append',default=[])
    p.add_argument('--output-dir',required=True);p.add_argument('--preview',action='store_true')
    p.add_argument('--provider',choices=['mock','openai-chat'],default='mock');p.add_argument('--mock-response')
    p.add_argument('--model');p.add_argument('--base-url',default='https://api.openai.com/v1')
    p.add_argument('--allow-external',action='store_true');p.add_argument('--allow-document-sharing',action='store_true')
    p.add_argument('--allow-json-fence',action='store_true');add_chat_arguments(p)
    a=p.parse_args(argv)
    def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        if a.resume:
            if a.attachment or not (a.reply or a.reply_file):raise ValueError('Resume needs a reply, no replacement attachments')
            old=Path(a.resume);case=BusinessCase.model_validate(read(old/'public_input.json'))
            reply=a.reply if a.reply is not None else Path(a.reply_file).read_text(encoding='utf-8-sig')
            case=append_business_reply(case,read(old/'review_result.json')['confirmation_card'],reply)
        else:
            if a.reply or a.reply_file:raise ValueError('Reply requires resume')
            question=a.question if a.question is not None else Path(a.question_file).read_text(encoding='utf-8-sig')
            case=create_grounded_intake(case_id=a.case_id,business_question=question,
                attachments=[AttachmentRequestV07(path=x) for x in a.attachment],response_language='zh').case
        out=Path(a.output_dir)
        if out.exists():raise ValueError('Output directory already exists')
        if not a.preview and a.provider=='openai-chat':
            if not a.model or not a.allow_external or (case.sources and not a.allow_document_sharing):
                raise ValueError('Online model and explicit external/source consent required')
            provider=OpenAICompatibleChatProvider(model=a.model,base_url=a.base_url,
                allow_json_fence=a.allow_json_fence,**chat_options(a))
        elif not a.preview:
            if not a.mock_response:raise ValueError('Offline response fixture required')
            provider=mock_factory(read(a.mock_response))
        out.mkdir(parents=True,exist_ok=False)
        def save(name,x):(out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        save('public_input.json',case.model_dump(mode='json'))
        if a.preview:
            print('已保存自然语言材料；没有调用模型或数学库。');return 0
        flow=flow_class(provider)
        try:result=flow.formulate(case)
        finally:
            if flow.last_wire is not None:save('model_draft.json',flow.last_wire)
        save('review_result.json',result)
        (out/'business_confirmation.html').write_text(render(case,result),encoding='utf8')
        print(f'已生成业务理解稿：{out / "business_confirmation.html"}')
        print('可用 --resume 和 --reply/--reply-file 补充普通话，并指定新的输出目录。尚未批准科学条件或调用数学 Core。')
        return 0
    except Exception as exc:
        print(f'处理停止：{type(exc).__name__}；未授予识别或估计权限。')
        return 2


if __name__=='__main__':raise SystemExit(main())
