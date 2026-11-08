"""Opt-in field-role clarification using the unchanged source-selection wire.

Replaces overlapping instructions, rather than repairing model replies. Source
data, required fields, enums and parsers are unchanged. No scientific approval.
"""
import json

CONTRACT = 'network-source-selections-roles-1'

MODEL_FIELDS = '''若原文给出数值总体信息、界限或完整均值模型，用bounded_model读取界限的对象、含义、全安排适用范围、结果单位和期间。不能从二元结果自行补0到1界限。两项完整性声明相互独立：listed_means_are_complete_information问“列出的均值是否是全部已知总体信息”；no_additional_coupling_constraints问“除已声明的基础科学条件、均值充分性、所列均值和逐对象界限外，模型是否明确没有其他耦合约束”。
no_additional_coupling_constraints=true须有明确排除其他耦合的原文；原文采用跨对象、跨处理安排的额外关系（含单调性、相等或顺序关系）时为false，关系同时完整保留在additional_restrictions。即使原文在列完这项关系后说“除此之外没有其他限制”，也仍为false：该字段不是问“有没有未列出的限制”。没有声明是否排除时为null，不能由沉默或没有跨对象联合分布推定true。只有方法偏好或信息范围说明不等于模型耦合。原文自身矛盾时保留双方并在unresolved说明冲突，不替作者选一方。
界限含义CONDITIONAL_MEAN与ALMOST_SURE_OUTCOME分别是对潜在结果均值、潜在结果本身的限制，不可互换。科学状态和界限都只是原文声明，尚未获得审核许可；符号信息且没有数值模型或界限时bounded_model=null。'''

REMAINDER = '''additional_restrictions是现有专门字段未能完整表达的剩余内容，不是注意事项列表。先在information保留总体/样本性质、联合变量范围、覆盖对象和格子；已编码的“精确总体值不是样本”“仅有这些格子”“逐对象分布不含跨对象联合信息”不再重复列为限制。FULL_JOINT_LAW等更强信息必须原样保留在information，不得降格，也不因重要而重复列入此列表。
真实的额外单调性、跨对象或跨安排关系、无法表达的信息及指定方法要求仍须完整保留。若一段原文只有部分已被其他字段表达，只保留其未表达部分；无法确定时保留并说明疑点，不根据预期识别结果删除内容。任何明确的科学限制都不能当作同义说明去重删除。'''

GAPS = '''unresolved只记录原文目标、资料、条件的真实缺项或冲突，对应字段保留null/UNKNOWN/空列表；不填写答案、支持判断或识别判断。符号总体对象无数字不是缺项；完整模型仅给部分均值并允许其余均值在界内变化时，未定均值是模型自由量，不要求用户补齐它，也不补造它。用户问的量尚未知、原设计未支持某安排，都交数学模块处理。真正缺少界限范围、评价对象、完整性声明等材料时，仍保留未知并如实说明。来源编号存在不证明解释正确。'''


def make_request(bundle, *, binding, assignment_semantics=None):
    from .network_statement_reading import make_information_request
    request = make_information_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    replacements = {
        '若材料给出数值总体信息、科学界限或讨论完整均值模型': MODEL_FIELDS,
        'CONDITIONAL_MEAN限制潜在结果均值': REMAINDER,
        '不明确的字段用null/UNKNOWN/空列表': GAPS,
    }
    lines = request['system'].splitlines()
    for prefix, instruction in replacements.items():
        indices = [i for i, line in enumerate(lines) if line.startswith(prefix)]
        if len(indices) != 1:
            raise ValueError('READING_BASE_INSTRUCTION_CHANGED')
        lines[indices[0]] = instruction
    body = json.loads(request['user'])
    schema = body['output_schema']
    schema['properties']['additional_restrictions']['description'] = REMAINDER
    schema['properties']['unresolved']['description'] = GAPS
    bounded = schema['$defs']['BoundedModel']['properties']
    bounded['listed_means_are_complete_information']['description'] = '只问所列均值是否是全部可用总体信息；不表示没有额外模型约束。未知null。'
    bounded['no_additional_coupling_constraints']['description'] = (
        '参照基础条件、已声明均值充分性、所列均值和逐对象界限：明确无额外耦合才true；'
        '采用任何额外跨对象/跨安排关系则false，即使作者说列完它之后没有其他限制；未声明null。'
        '已有字段未能表达的真实关系仍保留在additional_restrictions。不是科学批准。')
    return dict(system='\n'.join(lines), user=json.dumps(body, ensure_ascii=False))
