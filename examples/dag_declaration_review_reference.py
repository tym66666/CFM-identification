"""New declaration paraphrases, with one same-material old-prompt control."""
from copy import deepcopy
from examples.dag_entry_closeout_reference import _case,assess
from cfm_id_llm.dag_reading import documents
from cfm_id.source_locations import build_catalog

def _material(slot,kind,names,context,graph_statement,positive_statement):
    case=_case(slot,kind)
    old=build_catalog(documents(case['bundle']))
    x,y,w=names
    doc=case['bundle']['documents']
    doc['variables']='\n'.join(n+'为二元指标，发生为1、未发生为0，均有观测记录。' for n in names)
    doc['relations']=x+'直接影响'+y+'。\n'+x+'直接影响'+w+'。'
    doc['context']='研究对象与时期：'+context+'。'
    doc['model']='本研究采用固定且无时间反馈的有向无环结构模型。\n'+graph_statement+'\n所有共同原因都已列在变量清单中，不另有遗漏的共同原因。\n各结构方程的剩余随机噪声相互独立。\n干预只设定'+x+'，其他变量的结构机制保持不变。'
    doc['information']='全部观测变量的完整联合总体分布作为已知符号信息给出，不是样本频率。\n'+positive_statement
    case['bundle']['question']='在'+context+'中，如果把所有对象的“'+x+'”分别统一设为0和1，“'+y+'”的总体分布怎样用已有总体信息表示？业务方指定控制“'+w+'”，请检查这一方案。'
    new=build_catalog(documents(case['bundle']))
    assert [v['doc_id'] for v in old.values()]==[v['doc_id'] for v in new.values()]
    replacements=dict(zip(old,new))
    replacements.update(dict(zip(('设备校准','合格达标','查看记录','本月质检设备'),(*names,context))))
    def rebind(value):
        if type(value) is str:return replacements.get(value,value)
        if type(value) is list:return [rebind(v) for v in value]
        if type(value) is dict:return {k:rebind(v) for k,v in value.items()}
        return value
    case['reference']=rebind(case['reference'])
    case['expected_adjustment']=[w] if kind=='affirmed' else None
    case['prompt_variant']='current'
    return case

def cases():
    names=('启用分拣提示','准时发车','查看操作看板');context='本月配送站点'
    pending=_material('DR01_pending_a','proposed',names,context,
        '这版分析方案拟采用清单已列全直接因果关系的假设，方案已经写定，正等专家审核。',
        '方案拟采用每种观测变量联合0/1组合在总体中都有非零概率的假设，已写入方案，正等专家审核。')
    control=deepcopy(pending);control.update(slot='DR00_old_control',group='old_prompt_control',prompt_variant='before')
    pending['group']='new_pending_a'
    pending_b=_material('DR02_pending_b','proposed',('发送学习提醒','按时结课','打开学习页面'),'本季线上培训班',
        '清单有没有遗漏还没做实证核验，但我们已经决定在本次方案里先假设直接因果关系都列全了；科学审核尚无结论。',
        '每种观测联合0/1组合是否都有正总体概率尚无实证核验，但本次方案已决定先采用这一正性假设；科学审核尚无结论。')
    pending_b['group']='new_pending_b'
    unknown=_material('DR03_not_adopted','unknown',names,context,
        '有人建议把关系清单当作完整清单，但我们还没决定是否采用，也不知道有没有漏掉直接影响。',
        '有人建议假设所有观测联合0/1组合在总体中都有正概率，但我们还没决定是否采用，也不知道实际是否成立。')
    unknown['group']='new_not_adopted'
    denied=_material('DR04_denied','denied',names,context,
        '刚核查过，清单确实漏了一条直接因果影响，所以清单不完整。',
        '总体中明确存在概率为零的观测联合0/1组合，并非每种组合都有正概率。')
    denied['group']='new_denied'
    affirmed=_material('DR05_affirmed','affirmed',names,context,
        '本次采用的关系清单已列全模型中的直接因果影响，没有清单以外的直接边。',
        '本次模型明确采用严格联合正性：每种观测联合0/1组合的总体概率都大于零。')
    affirmed['group']='new_affirmed'
    return [control,pending,pending_b,unknown,denied,affirmed]

