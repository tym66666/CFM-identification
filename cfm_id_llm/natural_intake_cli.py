"""Plain-text intake and plain-text follow-up; two model calls, no Core calls.

The experiment's credential budget is enforced by its audited local runner.
This general CLI uses the existing environment credential and explicit external
sharing flags; use mock files for offline replay.
"""
from __future__ import annotations
import argparse, json
from copy import deepcopy
from pathlib import Path
from .schemas import BusinessCase
from .document_intake import AttachmentRequestV07
from .material_integrity import create_grounded_intake
from .providers import OpenAICompatibleChatProvider
from .providers.cli_options import add_chat_arguments, chat_options
from .reviewed_intake import ReviewedIntake, PatchedIntake, append_business_reply, render_confirmation_html


def main(argv=None):
    p=argparse.ArgumentParser(description='自然语言提问/补充 → 两次提取复核 → 中文确认单（无数学批准）')
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--question');g.add_argument('--question-file');g.add_argument('--resume')
    r=p.add_mutually_exclusive_group();r.add_argument('--reply');r.add_argument('--reply-file')
    p.add_argument('--case-id',default='natural_intake')
    p.add_argument('--attachment',action='append',default=[])
    p.add_argument('--output-dir',required=True)
    p.add_argument('--preview',action='store_true')
    p.add_argument('--provider',choices=['mock','openai-chat'],default='mock')
    p.add_argument('--mock-extraction');p.add_argument('--mock-review')
    p.add_argument('--review-mode',choices=['rewrite','patches'],default='patches',help='Field patches preserve untouched extraction; rewrite is an experimental comparison only')
    p.add_argument('--model');p.add_argument('--base-url',default='https://api.openai.com/v1')
    p.add_argument('--allow-external',action='store_true');p.add_argument('--allow-document-sharing',action='store_true')
    p.add_argument('--allow-json-fence',action='store_true');add_chat_arguments(p)
    a=p.parse_args(argv)
    def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        if a.resume:
            if a.attachment or not (a.reply or a.reply_file):raise ValueError('Resume needs a reply, no replacement attachments')
            old=Path(a.resume)
            case=BusinessCase.model_validate(read(old/'public_input.json'))
            card=read(old/'review_result.json')['confirmation_card']
            reply=a.reply if a.reply is not None else Path(a.reply_file).read_text(encoding='utf-8-sig')
            case=append_business_reply(case,card,reply)
        else:
            if a.reply or a.reply_file:raise ValueError('Reply requires resume')
            question=a.question if a.question is not None else Path(a.question_file).read_text(encoding='utf-8-sig')
            intake=create_grounded_intake(case_id=a.case_id,business_question=question,
                attachments=[AttachmentRequestV07(path=x) for x in a.attachment],response_language='zh')
            case=intake.case
        out=Path(a.output_dir)
        # Each round gets a separate directory; no previous evidence is overwritten.
        if out.exists():raise ValueError('Output directory already exists')
        if not a.preview and a.provider=='openai-chat':
            if not a.model or not a.allow_external or (case.sources and not a.allow_document_sharing):
                raise ValueError('Online model and explicit external/source consent required')
            provider=OpenAICompatibleChatProvider(model=a.model,base_url=a.base_url,
                allow_json_fence=a.allow_json_fence,**chat_options(a))
        elif not a.preview:
            if not a.mock_extraction or not a.mock_review:raise ValueError('Two offline response fixtures required')
            responses=[read(a.mock_extraction),read(a.mock_review)]
            class Replay:
                name='offline-two-pass-replay'
                def generate_json(self,**kwargs):return deepcopy(responses.pop(0))
            provider=Replay()
        out.mkdir(parents=True,exist_ok=False)
        def save(name,x):(out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        save('public_input.json',case.model_dump(mode='json'))
        if a.preview:
            print('已保存自然语言材料；没有调用模型或数学库。');return 0
        flow=(PatchedIntake if a.review_mode=='patches' else ReviewedIntake)(provider)
        try:
            result=flow.formulate(case)
        finally:
            if flow.initial_wire is not None:save('initial_draft.json',flow.initial_wire)
            if flow.review_wire is not None:save('model_draft.json',flow.review_wire)
        save('review_result.json',result)
        (out/'business_confirmation.html').write_text(render_confirmation_html(case,result),encoding='utf8')
        print(f'已生成中文确认单：{out / "business_confirmation.html"}')
        print('可以用 --resume 和 --reply/--reply-file 补充普通话；使用新的输出目录保留这一轮。')
        print('尚未批准业务或科学条件，未调用数学 Core。')
        return 0
    except Exception as exc:
        # Do not print model/source/provider values or credentials in failure text.
        print(f'处理停止：{type(exc).__name__}；未授予识别或估计权限。')
        return 2


if __name__=='__main__':raise SystemExit(main())
