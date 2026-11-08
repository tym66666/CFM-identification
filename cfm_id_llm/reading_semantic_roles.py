"""Experimental explanations of existing fields, without changing any reader.

Not imported by default request builders. Evaluation may explicitly wrap one
request before freezing it. No candidate editing, approval or mathematical API.
"""

PROFILE = 'reading-semantic-roles-1'

TARGET_BOUNDARIES = '''先确定用户请求的因果量，再划分queries；不要按句子数、问号数或回答形式划分。
一个目标由干预或比较、结果、人群、汇总口径和期间共同确定。同一个量的“是多少”“能否唯一确定”“若不能能确定到什么范围”“请解释所需条件”等，是对该量及其识别程度的请求，应在同一个goal中完整保留，不能仅因此再造OTHER目标；也不能删掉用户对范围或条件的要求。这里不回答是否识别。
反过来，原文明确分别请求不同人群、不同安排、不同结果或不同时点的量时，保留全部目标及各自口径，不能因为共用材料而合并。原文只请求两个安排的差值时，差值本身是一个目标，不自动增列两端均值；如果还分别请求两端均值，则按原文保留这些额外量。请求一个干预分布关于多个处理取值的表达也不自动变成两个均值目标。
若确实无法判断两句话是否指向同一个量，保留原文歧义而不猜测。判断的依据只能是当前来源；不根据现有识别库、预期结果或下面的读取说明增删目标。'''

FACT_ROLES = '''逐条区分原文的三种内容，再把内容放入已有字段；这里不判断可识别。
一是已有信息及其边界：哪些总体分布或均值、哪些对象/格子、总体还是样本。它们属于information。某种信息“未给出”描述的是研究者知道什么，不等于断言该数学对象不存在、结果相互独立或潜在结果满足新等式。逐对象分布不包含跨对象联合分布这一边界已由NODE_FULL_LAW表达，不把同一边界再写成额外科学限制；但原文给了更强的联合信息就必须保留，不能为适配较弱路线而删掉。
二是世界或模型必须满足的条件：随机化、一致性、均值充分性、界限等放在各自科学声明或bounded_model字段。其他字段没有表达的单调关系、跨对象/情境的等式或不等式、额外依赖结构、额外信息和指定方法要求，完整保留在additional_restrictions。它不是所有注意事项的汇总字段。已完整记录的同一事实不重复列入；一段话只有部分已被表达时，未表达部分仍须保留。不能确定是否完整表达时也保留，不按“应该能识别”来删除。
三是读取或材料尚未明确的内容：真实缺项、范围未知或声明冲突放在unresolved，并保留对应字段的未知状态。只有符号总体对象而没有数字，并不等于原文漏掉该总体对象。明确只给部分均值的完整有界模型可以留有未定均值；不要把用户请求的量或其解当成必须先补齐的输入。目标安排有无正支持、已知信息能否确定目标、界限是否sharp，都交数学模块检查，不在这里推算或宣判。
“没有给跨对象联合分布”与“明确没有其他模型限制”不是同一声明；不能从前者或原文沉默推定no_additional_coupling_constraints=true。若真实额外限制存在，不能同时把它消除或声称没有额外耦合；如原文声明冲突，保留双方并标明冲突。所有声明仍待独立来源与科学审核。'''

_STAGES = {'business': TARGET_BOUNDARIES, 'network_facts': FACT_ROLES}


def with_semantic_roles(request, *, stage):
    """Append stage-specific guidance; keep source/schema user bytes untouched."""
    if (type(request) is not dict or set(request) != {'system', 'user'} or
            any(type(v) is not str for v in request.values())):
        raise ValueError('EXACT_TEXT_REQUEST_REQUIRED')
    if stage not in _STAGES:
        raise ValueError('EXPLICIT_READING_STAGE_REQUIRED')
    return dict(system=request['system']+'\n\n'+_STAGES[stage], user=request['user'])
