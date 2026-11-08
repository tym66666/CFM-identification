"""Opt-in model-facing guide; the inline wire parser and review stay unchanged.

Generated from the same field schema. This changes presentation, never fills a
candidate, selects a theorem, or treats a reference as semantic approval.
"""
import json
from . import compact_inline_evidence_contract as inline
from .compact_reference_contract import split_user, GUIDE_DELIMITER

CONTRACT = 'inline-output-guide-1'
project = inline.project
review_items = inline.review_items
apply_gate = inline.apply_gate
EXTRA_STATE_RULES = inline.EXTRA_STATE_RULES


def describe(schema):
    return inline.describe(schema) + '\n本次inline-output-guide-1使用输出填写说明呈现字段，回答仍是上述claim JSON；填写说明本身不是答案。'


def render(system, user, catalog):
    header, payload, schema, suffix = split_user(user)
    defs = schema['$defs']
    # The repeated absence rule is already stated once in the system message.
    repeated = (' 本协议：原文明示本字段内容未提供/未定时用MISSING+reason+refs，不带value；'
                '仅未读到内容则UNKNOWN。确定值仍用STATED/INTERPRETED，不另写缺失清单。')
    def fields(model):
        return {name: prop.get('description', '').replace(repeated, '')
                for name, prop in defs[model]['properties'].items()}
    guide = {
        '说明': '以下是填写说明，不是待照抄的回答。返回业务取值，不返回字段说明或Schema。',
        '顶层': '只返回common对象和queries数组；短来源模式还须返回reference_context。',
        'common字段': fields('CompactCommon'),
        'query字段': fields('CompactQuery'),
        'semantics字段': fields('CompactSemantics'),
        '填写规则': [
            'common和每个query的semantics必须显式返回；每个query有goal、kind、semantics、comparison_order。',
            '除下面单列的字段外，每项已知值写为{"state":"STATED","value":"原文支持的短语","refs":["当前目录编号"]}；来源支持的解释将state改为INTERPRETED。goal必须是这种有来源的对象。',
            '未读到某字段的内容写字符串UNKNOWN或省略；原文明示该字段内容未定/未提供时写{"state":"MISSING","reason":"原文支持的缺失原因","refs":["当前目录编号"]}，不带value。MISSING只用于common和semantics里的单项claim。',
            'NOT_APPLICABLE仅用于无需比较的comparator或非政策目标的policy_assignment；其他字段不能使用。未知/不适用也可写仅有state的对象，不能带value或refs。',
            'assignment_family和kind只返回下列枚举中的一个字符串，不能返回枚举定义或claim对象。covariates是claim对象数组，没有相应背景变量就返回空数组。',
            'comparison_order写{"operation":"下列操作之一","refs":["实际问题的当前目录编号"]}；方向另填，aggregation只保留结果量、汇总与权重。',
            '不返回额外字段，不重复JSON键；不返回missing_information、type、title、default、enum、properties或$defs。',
        ],
        'assignment_family可选值': defs['AssignmentFamily']['enum'],
        'kind可选值': defs['TargetKind']['enum'],
        'comparison_order.operation可选值': defs['ComparisonOrder']['properties']['operation']['enum'],
        '长度限制': dict(queries_min=schema['properties']['queries']['minItems'],
            queries_max=schema['properties']['queries']['maxItems'],
            covariates_max=defs['CompactCommon']['properties']['covariates']['maxItems'],
            claim_text_max=2500, refs_max=defs['CompactClaim']['properties']['refs']['maxItems'],
            missing_or_order_refs_max=20),
        '引用规则': '每项已知值、MISSING及comparison_order必须有至少一个真实目录编号；编号不重复，且须支持整个表述。编号有效不代表读对，也不是科学批准。',
    }
    if 'reference_context' in payload:
        guide['reference_context'] = payload['reference_context']
        guide['绑定规则'] = '把上述reference_context原样作为回答的顶层字符串字段；不可省略或改写。它不是事实引用。'
    return (system, header+'\n'+json.dumps(payload,ensure_ascii=False,separators=(',',':'))
            +GUIDE_DELIMITER+json.dumps(guide,ensure_ascii=False,separators=(',',':'))+suffix, catalog)
