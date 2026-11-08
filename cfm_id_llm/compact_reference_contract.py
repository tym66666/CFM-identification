"""Optional short A0 selectors with exact, separately bound response context.

Only wire identifiers change. No fuzzy match, candidate repair, entailment
decision, scientific admission, or mathematical backend belongs here.
"""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Literal

from .evidence_refs import build_catalog
from .quality_formulator import A0QualityValidationError

CONTRACT = 'compact-source-selectors-1'
PARAGRAPHS = 'compact-source-paragraphs-1'
PROFILES = (CONTRACT, PARAGRAPHS)
Profile = Literal['compact-source-selectors-1', 'compact-source-paragraphs-1'] | None
DELIMITER = '\n\n输出 Schema：\n'
GUIDE_DELIMITER = '\n\n输出填写说明：\n'
GUIDANCE = '''
本次使用短来源选择编号。refs只填写当前目录中的s0001等编号，不输出长哈希、不发明或修改编号。顶层reference_context须原样复制本次给定值；它只绑定请求，不是事实来源。编号存在只证明定位成功，不证明其支持你的表述。'''


def checked(contract):
    if contract is not None and contract not in PROFILES:
        raise ValueError('UNKNOWN_A0_REFERENCE_CONTRACT')
    return contract


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()


def canonical_catalog(case, contract=None):
    checked(contract)
    if contract == PARAGRAPHS:
        from .source_paragraphs import build_catalog as paragraphs
        return paragraphs(case)
    return build_catalog(case)


def catalog(case, contract=None):
    rows=canonical_catalog(case,contract)
    return rows if contract is None else [dict(r,ref=f's{i:04d}') for i,r in enumerate(rows,1)]


def split_user(user):
    delimiter = GUIDE_DELIMITER if GUIDE_DELIMITER in user else DELIMITER
    prefix,rest=user.split(delimiter,1)
    header,body=prefix.split('\n',1)
    payload=json.loads(body)
    schema,end=json.JSONDecoder().raw_decode(rest)
    return header,payload,schema,rest[end:]


def set_context(user, context):
    header,payload,schema,suffix=split_user(user)
    payload['reference_context']=context
    delimiter = GUIDE_DELIMITER if GUIDE_DELIMITER in user else DELIMITER
    if delimiter == GUIDE_DELIMITER:
        schema['reference_context']=context
    else:
        schema['properties']['reference_context']={'type':'string','const':context}
        schema['required']=list(dict.fromkeys([*schema.get('required',[]),'reference_context']))
    return (header+'\n'+json.dumps(payload,ensure_ascii=False,separators=(',',':'))
        +delimiter+json.dumps(schema,ensure_ascii=False,separators=(',',':'))+suffix)


def request_context(user):
    return split_user(user)[1]['reference_context']


def adapt_request(case, system, user, *, contract=None, scope=None):
    if checked(contract) is None:return system,user,build_catalog(case)
    context='c'+digest(dict(contract=contract,system=system,user=user,scope=scope))
    header,payload,schema,suffix=split_user(user)
    rows=catalog(case,contract)
    payload['source_catalog']=rows
    # Both claim definitions are used by this compact schema.
    for name in ('CompactClaim','GroundedOrUnknownClaim'):
        schema['$defs'][name]['properties']['refs']['items']={'type':'string','enum':[r['ref'] for r in rows]}
    modified=(header+'\n'+json.dumps(payload,ensure_ascii=False,separators=(',',':'))
        +DELIMITER+json.dumps(schema,ensure_ascii=False,separators=(',',':'))+suffix)
    addition = ('\n目录按原始非空行保留相邻句子的上下文，过长行按固定长度分段；不是整份文档的自动引用。'
        '每个字段仍须自行选择实际支持其全部含义的来源，不借别的字段的引用；不要把整份目录全部选上。'
        '片段中的否定、未决定及相反条件都必须保留，定位成功不代表表述正确。') if contract == PARAGRAPHS else ''
    return system+GUIDANCE+addition,set_context(modified,context),rows


def rebind_revision(request, base, revision_sha256):
    """Called for each explicit reread; never changes its feedback or sources."""
    context='c'+digest(dict(contract=CONTRACT,base_context=request_context(base['user_prompt']),
        reading_revision_sha256=revision_sha256))
    return dict(request,user_prompt=set_context(request['user_prompt'],context))


def decode(case, raw, *, contract=None, expected_context=None):
    """Resolve an exact selector to the existing canonical evidence identifier."""
    if checked(contract) is None:return raw
    if (type(raw) is not dict or type(raw.get('reference_context')) is not str
            or raw['reference_context']!=expected_context or expected_context is None):
        missing = type(raw) is dict and 'reference_context' not in raw
        raise A0QualityValidationError('Invalid current-request reference context',
            code='A0_REFERENCE_CONTEXT_MISMATCH', diagnostics=dict(stage='reference_context',
                issues=[dict(code='missing' if missing else 'REFERENCE_CONTEXT_MISMATCH',
                             path=['reference_context'])]))
    aliases={a['ref']:b['ref'] for a,b in zip(catalog(case,contract),canonical_catalog(case,contract))}
    def walk(value):
        if isinstance(value,dict):
            out={k:walk(v) for k,v in value.items()}
            if 'refs' in value and isinstance(value['refs'],list):
                if any(type(r) is not str or r not in aliases for r in value['refs']):
                    raise A0QualityValidationError('Invalid current-case selector',code='A0_REFERENCE_NOT_FOUND')
                out['refs']=[aliases[r] for r in value['refs']]
            return out
        if isinstance(value,list):return [walk(v) for v in value]
        return deepcopy(value)
    result=deepcopy(raw);result.pop('reference_context')
    return walk(result)
