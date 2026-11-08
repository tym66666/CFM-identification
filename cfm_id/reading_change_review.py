"""Source-bound review of changed readings, without interpreting or editing facts."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .business_intake import _sha

VERSION='reading-change-review-1'


class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    disposition: Literal['ACCEPTED','REJECTED','PENDING']
    reason: str=Field(min_length=12)
    source_ids: list[str]=Field(min_length=1)


class ChangeReview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    version: Literal['reading-change-review-1']=VERSION
    binding_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW']
    reviewer: str=Field(min_length=3)
    evidence: str=Field(min_length=12)
    decisions: dict[str,Decision]


def changes(before,after):
    """Exact JSON differences; context nonce alone is not a semantic change.

    No meaning-based alignment of reordered lists, fuzzy equivalence or defaults.
    Source-reference changes are retained for review too.
    """
    result=[]
    def walk(a,b,path='',ap=True,bp=True):
        if ap and bp and type(a) is type(b) and type(a) not in (dict,list) and a==b:return
        if ap and bp and type(a) is dict and type(b) is dict:
            for key in sorted(set(a)|set(b)):
                if path=='' and key=='reference_context':continue
                walk(a.get(key),b.get(key),path+'/'+key.replace('~','~0').replace('/','~1'),key in a,key in b)
        elif ap and bp and type(a) is list and type(b) is list and len(a)==len(b):
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
        else:result.append(dict(field_path=path,before_present=ap,after_present=bp,
                                before=deepcopy(a),after=deepcopy(b)))
    walk(before,after)
    return {f'd{i:04d}':v for i,v in enumerate(result,1)}


def inspect_changes(*,binding,before,after,source_catalog,authority,review=None):
    delta=changes(before,after)
    sheet=dict(version=VERSION,binding_sha256=_sha(dict(version=VERSION,binding=binding,
        before=before,after=after,source_catalog=source_catalog,authority=authority)),
        expected_authority=authority,changes=delta,source_catalog=deepcopy(source_catalog),
        decisions={k:dict(disposition='PENDING',reason='',source_ids=[]) for k in delta},is_approval=False,
        scope='Review every changed field against original text and all retained conditions. Not scientific approval or a mathematical proof.')
    out=dict(state='REVIEW_REQUIRED',reason_code='INDEPENDENT_READING_CHANGE_REVIEW_REQUIRED',
             worksheet=sheet,receipt=None)
    if not delta:
        if review is not None:raise ValueError('CHANGE_REVIEW_WITHOUT_CHANGES')
        return dict(out,state='UNCHANGED',reason_code=None,worksheet=None)
    if review is None:return out
    raw=review.model_dump(mode='json') if type(review) is ChangeReview else review
    r=ChangeReview.model_validate(raw)
    if (r.binding_sha256!=sheet['binding_sha256'] or r.authority!=authority or
        set(r.decisions)!=set(delta) or not r.reviewer.strip() or not r.evidence.strip()):
        raise ValueError('INVALID_OR_STALE_READING_CHANGE_REVIEW')
    for d in r.decisions.values():
        if (not d.reason.strip() or len(d.source_ids)!=len(set(d.source_ids)) or
            any(s not in source_catalog for s in d.source_ids)):
            raise ValueError('INVALID_CHANGE_REVIEW_SOURCE')
    out['receipt']=dict(version=VERSION,binding_sha256=sheet['binding_sha256'],review=r.model_dump(mode='json'),
        changes=deepcopy(delta),candidate_modified=False,scientific_approval=False,mathematical_verification='NOT_PERFORMED')
    decisions={d.disposition for d in r.decisions.values()}
    if 'REJECTED' in decisions:return dict(out,state='READING_RECHECK_REQUIRED',reason_code='SOURCE_REVIEW_REJECTED_READING_CHANGE')
    if 'PENDING' in decisions:return out
    return dict(out,state='CHANGES_REVIEWED',reason_code=None)
