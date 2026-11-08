"""Readable extraction receipts, independent of LLM review."""
def receipt(report):
    entries=[]; issues=[]
    for a in report['attachments']:
        notes=[]
        if a['mode']=='SCHEMA_ONLY': notes.append('仅读取列名和行数；字段解释请选择“字段说明表”，数值请选择“表格数据”。')
        for code in a['warnings']:
            if code=='DICTIONARY_OTHER_SHEETS_NOT_SELECTED':
                notes.append('只读取你选定的字段说明工作表，其他工作表未选入。'); continue
            if code.startswith('PDF_PAGE_NO_TEXT:'): msg='第'+code.rsplit('_',1)[-1]+'页没有可提取文字（可能是扫描或空白页）；请提供文字版，或移除确实无关的页。'
            elif code.startswith('PDF_IMAGE_CONTENT_NOT_READ:'): msg='第'+code.rsplit('_',1)[-1]+'页含未读取的图片；如是方案、图表或批注，请补充文字版。'
            elif 'DOCX' in code: msg='Word含未完整读取的合并表格、图片、修订或批注；请提供对应文字或平整表格。'
            elif code=='SCANNED_OR_IMAGE_ONLY_PDF_NO_OCR': msg='这份PDF未提取到正文，当前未执行OCR。'
            elif code in ('CONTENT_TRUNCATED','PDF_REMAINING_PAGES_NOT_READ','PAGE_LIMIT_REACHED'): msg='文件超出读取长度或页数，后半部分尚未读取；请拆分或仅上传本次相关部分。'
            else: msg='文件部分内容未完整读取，请核对后提供较小、完整的材料。'
            notes.append(msg)
            issues.append(a['display_name']+'：'+msg)
        entries.append(dict(name=a['display_name'],mode=a['mode'],characters=a['extracted_chars'],notes=notes))
    return dict(files=entries,issues=list(dict.fromkeys(issues)),ready=not issues,
                message='这是本地文件读取检查，不批准科学条件，也不表示因果目标已识别。')
