"""Source proposition roles, shared by reading and review; no deduplication code."""
import json
from . import network_outcome_contract as previous
from .network_reading_contract import REMAINDER as OLD_REMAINDER, GAPS as OLD_GAPS

CONTRACT = 'network-source-selections-remainder-1'

REMAINDER = '''additional_restrictions只记录其他字段尚未完整表达的实质内容，不是整段资料的副本、所有条件的摘要或注意事项列表。按每项含义而非整段文字分类；同一原文段落可以分别支持多个字段，每个字段仍须引用支持自己的原文。
先保留各自专门字段中的原文含义：information记录总体/样本性质、已知量、范围和格子；bounded_model记录科学界限的含义、数值、对象、范围、结果尺度和两项声明；unresolved记录真正未明确或冲突的事项。上述字段已经完整表达的同一内容不再抄入本列表，即使它是重要的科学限制。原文仍保留在来源中，并不因此删掉该科学条件或削弱它。
一段资料若既说明已有界限，又提出跨对象或跨安排的相等、顺序、单调性等关系，只在本列表保留尚未由专门字段表达的关系及其全部适用范围、条件和采用态度；界限仍留在原字段。no_additional_coupling_constraints=false只表达存在额外关系，不能代替关系本身，因此额外关系必须保留。不要只凭同一句中的“除此之外无其他限制”把它删掉。
现有数值字段无法表达的总体区间、聚合方程、额外联合信息或特殊方法要求，也须保留原含义及来源；不能取中点、填点值、降格信息或改成科学界限。单纯缺少单位、编码或某项是否确认的状态放在对应字段及unresolved，不因此成为新增约束。若同一句还有真正额外内容，仍保留那部分。
只有明确全部被其他字段表达时，才不重复列入；是否完全表达无法确定时保留有关内容，并在unresolved说明具体疑点。不能为了得到POINT、PARTIAL、sharp或适配现有求解器删除未表达的条件。没有剩余内容才用[]。此规则是读取职责说明，程序不对候选执行语义去重，也不批准任何科学条件。'''

GAPS = '''unresolved记录原文目标、资料或条件的真实缺项、冲突，以及无法确认某项内容是否已完整表达的具体疑点；对应结构化字段仍保留null/UNKNOWN/空列表。原文只是不确定一个单位或声明时，不把这个缺口同时当成additional_restrictions中的新增关系；若还含真正的额外约束，约束仍须保留。
不填写答案、支持判断或识别判断，也不把“尚未人工审核”当作原材料缺项。符号总体对象无数字不是缺项；明确的完整模型只列部分均值、允许其余均值在界内变化时，未定均值是模型自由量，不要求用户补齐。用户要问的量尚未知、原设计是否支持目标安排，交数学模块检查。真实缺少对象、尺度、界限范围、完整性声明等材料时，保留未知并引用原文；沉默不是否定。来源编号存在不证明解释正确。'''

FIELD_RULES = (*previous.FIELD_RULES,
    ('/additional_restrictions', REMAINDER), ('/unresolved', GAPS))


def field_constraints(paths):
    return [dict(field_path=p, description=d) for p,d in FIELD_RULES
            if any(q=='' or p==q or p.startswith(q+'/') or q.startswith(p+'/') for q in paths)]


def make_request(bundle, *, binding, assignment_semantics=None):
    request=previous.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    system=request['system']
    for old,new in ((OLD_REMAINDER,REMAINDER),(OLD_GAPS,GAPS)):
        if system.count(old)!=1:
            raise ValueError('REMAINDER_DEFINITION_CHANGED')
        system=system.replace(old,new)
    body=json.loads(request['user']);props=body['output_schema']['properties']
    props['additional_restrictions']['description']=REMAINDER
    props['unresolved']['description']=GAPS
    return dict(system=system,user=json.dumps(body,ensure_ascii=False))
