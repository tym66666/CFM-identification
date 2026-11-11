"""Explicit AI-reviewed re-reading of an observed synthetic case; preserve both responses."""
import argparse
import getpass
import json
import os
from pathlib import Path

from cfm_id import business_intake, fact_reading_revision
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--previous', help='A previous fact reread directory, for an explicitly reviewed next round')
    args = p.parse_args()
    src, out = Path(args.source), Path(args.output)
    def read(name):
        return json.loads((src / (name + '.json')).read_text(encoding='utf8'))
    def write(name, value):
        (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf8')
    snapshot = business_intake._checked(read('intake_snapshot'))
    entry, candidate = read('fact_entry'), read('fact_candidate')
    revision = None
    if args.previous:
        previous = Path(args.previous)
        entry = json.loads((previous / 'fact_entry.json').read_text(encoding='utf8'))
        candidate = json.loads((previous / 'fact_candidate.json').read_text(encoding='utf8'))
        revision = entry['reading_revision']
    query_review = read('a0_submitted')['query_review']
    sheet_result = fact_reading_revision.prepare_recheck(snapshot, 'q1', query_review=query_review,
        candidate=candidate, request_sha256=entry['request_sha256'], reading_revision=revision)
    if sheet_result['state'] != 'REVIEW_REQUIRED':
        raise ValueError('Cannot prepare source review: ' + str(sheet_result.get('reason_code')))
    sheet = sheet_result['feedback_worksheet']
    document = 'assignment' if args.previous else 'science'
    path = '/assignment/probabilities' if args.previous else '/additional_restrictions/0'
    sources = [key for key, row in sheet['source_catalog'].items() if row.get('doc_id') == document]
    if len(sources) != 1 or path not in sheet['field_paths']:
        raise ValueError('Expected original source and candidate field not found')
    feedback = dict(version='fact-reading-feedback-1', binding_sha256=sheet['binding_sha256'],
        authority='SYNTHETIC_TEST', reviewer='Codex AI delegated review of fictional case',
        evidence='逐条对照虚构业务原文；此反馈由 AI 审核，既不是人工签审，也不构成科学批准。',
        issues=[dict(field_path=path, kind='UNSUPPORTED_ADDITION' if args.previous else 'POSSIBLE_DUPLICATION',
          source_ids=sources, reason=('原文是固定名额抽签，逐网点概率不是原文单独给出的分配参数；需按公开合同核对字段组合。' if args.previous else
          '该条内容来自科学条件材料，同一固定网络和一阶矩条件已在专用字段表达，应检查是否重复。'))])
    revised = fact_reading_revision.prepare_recheck(snapshot, 'q1', query_review=query_review,
        candidate=candidate, request_sha256=entry['request_sha256'], reading_revision=revision, feedback=feedback)
    if revised['state'] != 'READY_TO_READ' or revised['request_sha256'] == entry['request_sha256']:
        raise ValueError('Re-reading request not bound: ' + str(revised.get('reason_code')))
    out.mkdir(parents=True, exist_ok=False)
    write('feedback_worksheet', sheet); write('feedback', feedback); write('fact_entry', revised)
    key = getpass.getpass('API key (not echoed): ')
    if not key:
        raise SystemExit('Missing key')
    os.environ['CFM_ID_LLM_API_KEY'] = key
    provider = OpenAICompatibleChatProvider(model='deepseek-v4-flash', base_url='https://newapi.sufe.edu.cn/v1',
        timeout=120, max_tokens=16384, json_mode=True, thinking='disabled', require_finish_reason=True)
    try:
        response = provider.generate_json(system_prompt=revised['request']['system'], user_prompt=revised['request']['user'])
        write('fact_candidate', response)
        write('result', {'state': 'RETURNED', 'request_sha256': revised['request_sha256'], 'stage': 'FACT_RECHECK'})
        print('Fact re-reading returned; separate audit still required.')
    except Exception as exc:
        write('result', {'state': 'CALL_FAILED', 'exception_type': type(exc).__name__,
                         'error_code': getattr(exc, 'code', None), 'stage': 'FACT_RECHECK'})
        print('Fact re-reading failed:', type(exc).__name__)
    finally:
        write('diagnostics', provider.last_diagnostics)


if __name__ == '__main__':
    main()
