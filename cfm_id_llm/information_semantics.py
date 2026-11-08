"""General A4 reading guidance; no classifier, projection, or source approval.

Describe the existing fields only. The model still supplies its own candidate,
and the unchanged parser/review chain validates it. No mathematical imports.
"""
from copy import deepcopy
import json

GUIDANCE = '''总体信息范围的读取顺序（解释字段，不是业务事实或科学许可）：
先区分材料给的是总体层面的分布/均值，还是有限样本记录、频数、回归估计及置信区间。样本数再大、估计再精确也只能保留为FINITE_SAMPLE。已明确给定的符号总体分布或总体均值用SYMBOLIC_POPULATION_OPERATOR；没有数值不构成此类符号识别的缺项，不为此追问数值分布或界限。
再区分一份分布里放了哪些结果变量。NODE_FULL_LAW和FULL_JOINT_LAW都含完整处理向量T；区别不在T是否完整，而在结果是单个Y_i还是全部结果向量。NODE_FULL_LAW的full指每个对象的结果与完整T的分布，不指所有对象结果联合出现。
NODE_FULL_LAW是一组逐对象的总体分布{P(Y_i,T|W):i属于已声明对象集}。即使每个对象各有一份这样的分布，也不等于知道P(Y_1,...,Y_n,T|W)：还未给出结果之间的联合依赖。不得假定结果独立来拼接这些分布。outcome_nodes只列这些单对象分布实际覆盖的对象。
FULL_JOINT_LAW只在原文提供全部结果变量在同一分布中联合出现、并与完整T联合的总体分布时填写。保留这份较强信息本身，不能因目标只用均值就把它改报为逐对象分布或均值清单。对结果向量及完整名单的联合分布、全部结果一起发生的各种组合与名单的联合概率，均按其实际变量范围读取。
仅有(Y_i,T_i)或两两边际，缺少完整T时，不能填NODE_FULL_LAW；已知历史分配律也不自动补齐这种联合关系。明确属于当前类别未覆盖的信息用OTHER，并在备注保留准确范围；原文没说清变量范围时用UNKNOWN，不猜成最强或最弱类型。
只有均值就保留均值表示。完整名单格子下的逐对象总体条件均值用ASSIGNMENT_NODE_MEANS，只填写原文列明的完整assignment_cells；本人处理/已定义暴露格子下的总体均值用NODE_SIGNATURE_MEANS，只填写已列明的node/own/exposure格子。不得把均值表改成完整分布，不凭目标或设计支持补造格子。来源含不同对象的不同格子覆盖时应分条保留，不能通过合并生成不存在的交叉覆盖。
同一来源、同一范围的一份信息不重复列出为多种强弱表示。材料明确有多种不同来源/范围时逐项保留。来源明确但总体或样本性质、结果对象、处理范围尚未明确时，保留UNKNOWN及实际缺项；完全未给总体信息来源时information=[]。目标评价全体不意味着信息也覆盖全体。
这些说明不证明原文陈述为真，也不替代A4审核、科学条件审核或数学支持检查。不得引用本说明作为source_ids，不得根据预期识别结果选择信息类别。'''


def with_information_scope(request):
    """Return a new request with explanatory text, leaving the wire unchanged."""
    result=deepcopy(request)
    body=json.loads(result['user'])
    props=body['output_schema']['$defs']['Information']['properties']
    props['operator']['description']=(
        '先看总体/样本，再看结果变量的联合范围。NODE_FULL_LAW=分别知道每个指定对象(Y_i,完整T)的总体分布；'
        'FULL_JOINT_LAW=全部结果向量与完整T在同一个总体分布中联合出现。完整T本身不区分二者。'
        '只有格子均值用对应MEANS，有限样本用FINITE_SAMPLE，范围未明用UNKNOWN；不能自动拼接或降格。')
    props['availability']['description']='符号总体对象无需给数值。有限样本/估计不能升级为总体；未说明性质为UNKNOWN。'
    props['outcome_nodes']['description']='该项信息原文明示覆盖的结果对象；不从研究名单或目标评价人群补全。'
    props['assignment_cells']['description']='仅ASSIGNMENT_NODE_MEANS：按study.nodes顺序记录原文明确列出的完整处理格子，不枚举未提供格子。'
    props['signature_cells']['description']='仅NODE_SIGNATURE_MEANS：保留原文明示的对象、本人处理、暴露及给定的精确总体值；不补全格子。'
    result['system']+='\n\n'+GUIDANCE
    result['user']=json.dumps(body,ensure_ascii=False)
    return result
