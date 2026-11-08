"""Opt-in, reversible wire notation for a controlled reading experiment.

No source-text classification, theorem, semantic correction or approval lives
here. The default business request and Core entry points are unchanged.
"""
from copy import deepcopy
import hashlib
import json
import re
from cfm_id import mean_order_reading as reading,question_bound_assignment as ids

SYMBOL_VERSION='mean-order-symbol-reading-1'
TO_SYMBOL={'NONDECREASING':'>=','NONINCREASING':'<=','NO_EFFECT':'=',
           'NOT_ASSUMED':'NOT_ASSUMED','UNKNOWN':'UNKNOWN'}
FROM_SYMBOL={v:k for k,v in TO_SYMBOL.items()}
COMMON_DIRECTION=('relation 的方向统一为 axis 所指本人或一个邻居从不用(0)改为使用(1)，其余安排保持不变。'
    '比较改变后的结果数值相对于改变前的数值；不随结果是收益还是成本、业务目标是甲减乙还是乙减甲而翻转。')
_RELATION_LINE=('relation: NONDECREASING=数值均值不降低，NONINCREASING=不提高，NO_EFFECT=没有影响/相等，'
    'NOT_ASSUMED=原文明确不作该假设，UNKNOWN=含糊。')

def _encoding(value):
    if value not in ('english','symbol'):raise ValueError('EXPLICIT_WIRE_ENCODING_REQUIRED')

def make_request(bundle,*,encoding):
    _encoding(encoding)
    system,user=reading.make_request(bundle);payload=json.loads(user)
    if system.count(_RELATION_LINE)!=1:raise ValueError('BASE_RELATION_GUIDE_CHANGED')
    system=system.replace(_RELATION_LINE,COMMON_DIRECTION+_RELATION_LINE)
    # Both arms quote the labels and receive the exact same directional guide.
    labels=TO_SYMBOL if encoding=='symbol' else {k:k for k in TO_SYMBOL}
    pattern=r'\b(NONDECREASING|NONINCREASING|NO_EFFECT)\b'
    system=re.sub(pattern,lambda m:json.dumps(labels[m[0]],ensure_ascii=False),system)
    if encoding=='symbol':
        old='version 为 '+reading.VERSION+'。'
        if system.count(old)!=1:raise ValueError('BASE_VERSION_GUIDE_CHANGED')
        system=system.replace(old,'version 为 '+SYMBOL_VERSION+'。')
        definitions=payload['output_schema']['$defs']
        enum=definitions['OrderClaim']['properties']['relation']['enum']
        definitions['OrderClaim']['properties']['relation']['enum']=[TO_SYMBOL[v] for v in enum]
        version=payload['output_schema']['properties']['order_reading']['properties']['version']
        if version.get('const')!=reading.VERSION:raise ValueError('BASE_VERSION_SCHEMA_CHANGED')
        version['const']=SYMBOL_VERSION
    return system,json.dumps(payload,ensure_ascii=False)

def _validate(bundle,canonical):
    comp,orders=reading.split(canonical)
    ids.resolve_reading(bundle,comp)
    reading.project(bundle,orders)

def to_wire(bundle,canonical,*,encoding):
    _encoding(encoding);_validate(bundle,canonical);out=deepcopy(canonical)
    if encoding=='symbol':
        out['order_reading']['version']=SYMBOL_VERSION
        for row in out['order_reading']['claims']:row['relation']=TO_SYMBOL[row['relation']]
    return out

def from_wire(bundle,raw,*,encoding):
    _encoding(encoding);reading.split(raw);out=deepcopy(raw)
    if encoding=='symbol':
        orders=out['order_reading']
        if type(orders) is not dict or orders.get('version')!=SYMBOL_VERSION:
            raise ValueError('EXACT_SYMBOL_VERSION_REQUIRED')
        if type(orders.get('claims')) is not list:raise ValueError('CLAIM_LIST_REQUIRED')
        for row in orders['claims']:
            if type(row) is not dict or type(row.get('relation')) is not str or row['relation'] not in FROM_SYMBOL:
                raise ValueError('EXACT_SYMBOL_LABEL_REQUIRED')
            row['relation']=FROM_SYMBOL[row['relation']]
        orders['version']=reading.VERSION
    _validate(bundle,out)
    if to_wire(bundle,out,encoding=encoding)!=raw:raise ValueError('LOSSLESS_WIRE_ROUNDTRIP_REQUIRED')
    return out

def codec_receipt(bundle,raw,canonical,*,encoding):
    if from_wire(bundle,raw,encoding=encoding)!=canonical:raise ValueError('CODEC_PAIR_MISMATCH')
    def sha(value):
        return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    return dict(kind='LOSSLESS_LABEL_CODEC_ONLY',encoding=encoding,raw_sha256=sha(raw),canonical_sha256=sha(canonical),
        label_mapping=deepcopy(FROM_SYMBOL) if encoding=='symbol' else {},scientific_approval=False,
        mathematical_certificate=False,raw_roundtrip_verified=True)
