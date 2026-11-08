"""Public outcome-scale and independent declaration meanings; no fact inference.

Opt-in request profile on the unchanged source-selection wire and parser.
Earlier profiles, raw replies and mathematical admission remain unchanged.
"""
import json
from . import network_field_contract as previous

CONTRACT = 'network-source-selections-outcome-1'

OUTCOME_DEFINITION = '''outcome_definition记录单个研究对象在评价期内记录的结果变量及事件，与study.outcome一致；不把用户问的平均值、概率或政策价值改成每个对象的结果变量。原文明示的编码属于结果定义的一部分，不能借用处理变量的编码。bounded_model.source_ids须覆盖本项实际内容。'''

OUTCOME_UNIT = '''outcome_unit记录上述结果变量的计量单位或数值编码尺度，不是目标平均方式，也不是要求额外的物理单位。
原文明确结果为“事件发生记1，否则记0”时，保留这是0/1指标（无量纲）的口径；没有元、分钟等物理单位不表示编码尺度未知。指标的均值可以被业务称为发生概率，但单位字段不能因此改成百分数、百分比得分或0到100尺度。
金额、时长、数量或连续比例按原文明示的元/万元、分钟/小时、件数、0到1比例或百分数尺度保留；不换算精确均值或界限，也不从数值大小猜单位。只写“完成率”而未说明记录的是每个对象的0/1事件、对象内比例还是百分数时，不能自选口径。只说二元结果而没有编码，或金额/时长缺少单位时，保留null并说明真正缺项；冲突保留双方，不替作者选择。bounded_model.source_ids须覆盖结果的单位或编码依据；本说明不是原文，不能作为source_ids。'''

OUTCOME_PERIOD = '''outcome_period记录这份结果定义、总体信息和模型界限实际适用的评价期，与study及目标一致；原文明确不同时保留区别和疑点，不能把过去样本窗口当作未来评价期。未知保留null。bounded_model.source_ids须覆盖期间原文。'''

COUPLING_DECLARATION = '''no_additional_coupling_constraints单独记录原文对额外均值关系的声明。参照已声明的基础科学条件、均值充分性、精确总体均值和逐对象界限：明确不另加跨对象或跨完整安排的关系时为true；明确采用额外的相等、顺序、单调性或其他耦合关系时为false，额外关系完整保留在additional_restrictions，即使原文在列完该关系后说“除此以外没有其他限制”。是否另加关系未提及、尚未决定或原文冲突时为null；冲突在unresolved保留双方。
本项不问总体信息是否已经穷尽，也不问能否得到识别结论。相邻声明逐项读取：某项未知或否定，不使另一项明确声明也变成未知。仅因没有跨对象联合分布不能推定没有均值关系。source_ids须覆盖本项内容；读取true不是批准科学条件。已经由本项完整记录的“无额外关系”不再作为一条新限制重复写入additional_restrictions，真正额外关系不得删除。'''

FIELD_RULES = (*previous.FIELD_RULES,
    ('/bounded_model/outcome_definition', OUTCOME_DEFINITION),
    ('/bounded_model/outcome_unit', OUTCOME_UNIT),
    ('/bounded_model/outcome_period', OUTCOME_PERIOD),
    ('/bounded_model/no_additional_coupling_constraints', COUPLING_DECLARATION))


def field_constraints(paths):
    return [dict(field_path=p, description=d) for p,d in FIELD_RULES
            if any(q=='' or p==q or p.startswith(q+'/') or q.startswith(p+'/') for q in paths)]


def make_request(bundle, *, binding, assignment_semantics=None):
    request=previous.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    body=json.loads(request['user'])
    properties=body['output_schema']['$defs']['BoundedModel']['properties']
    for path,description in FIELD_RULES[len(previous.FIELD_RULES):]:
        properties[path.rsplit('/',1)[1]]['description']=description
    return dict(system=request['system'],user=json.dumps(body,ensure_ascii=False))
