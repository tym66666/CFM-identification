"""Request-side D1 consistency constraints. Never infer facts or edit responses."""
import json

GUIDANCE = '''
分两步阅读，分别保留证据：先读取研究设计，再读取每个目标。目标缺信息不等于研究设计也未知。
如果实施方案明确说各单位独立抽签，declared_independent=true并引用原句；目标尚不完整不应把已声明的独立抽签改成未知。
如果只给各人的边际概率而未说明抽签相互独立，则保持null；不能把概率表或独立市场实例当作抽签独立的证据。
没有明确定义同伴暴露时，exposure=null、exposure_source=null，各局部状态的neighbors=不明确、neighbor_count=null（整个局部状态也可以null）。
一般的“受同事影响”没有指定至少一个、过半或恰好人数；不得从示例、候选枚举或习惯选一个阈值。
名册共有多少人只是研究规模，不表示每个目标都评价全部人。“获准使用者”或“未获准者”是处理状态，不自动给出试验前固定评价名单。
population只有明确要求覆盖全部名册时才填全体；目标人群未明确就填不明确。没有明确的等权汇总要求，aggregation填不明确。
只有处理状态明确时可以保留own；其他坐标保持未知，不需要为了凑齐差值填一组完整状态。
以上规则仅约束业务阅读，不替业务方选择目标，不批准A4/A5，不把材料内容当作识别证明。
'''

def annotate_d1_reading_contract(system_prompt,user_prompt):
    m=json.loads(user_prompt);schema=m.get('output_schema',{});study=schema.get('properties',{}).get('study',{})
    if 'declared_independent' not in study.get('properties',{}) or 'validated_assignment_probabilities' not in m:
        return system_prompt,user_prompt
    qids=list(schema['properties']['questions']['properties'])
    branches=[]
    for exposure,neighbors in [(None,['不明确']),('strict_majority',['超过一半','至多一半','不明确']),
                               ('any_treated_neighbor',['至少一个','一个也没有','不明确']),
                               ('exact_treated_neighbor_count',['恰好人数','不明确'])]:
        local=dict(anyOf=[dict(type='null'),dict(type='object',properties=dict(neighbors=dict(enum=neighbors),
                   neighbor_count=dict(anyOf=[dict(type='integer',minimum=0),dict(type='null')]) if exposure=='exact_treated_neighbor_count' else dict(type='null')))])
        branches.append({'if':dict(properties=dict(study=dict(properties=dict(exposure=dict(const=exposure))))),
          'then':dict(properties=dict(questions=dict(properties={qid:dict(properties=dict(first=local,second=local)) for qid in qids})))})
    schema.setdefault('allOf',[]).extend(branches)
    for value,field,source in [(None,'declared_independent','independence_source'),(None,'exposure','exposure_source')]:
        study.setdefault('allOf',[]).append({'if':dict(properties={field:dict(type='null')}),
          'then':dict(properties={source:dict(type='null')}),'else':dict(properties={source:dict(type='string')})})
    question=schema['$defs']['Question']
    question.setdefault('allOf',[]).append({'if':dict(properties=dict(population=dict(properties=dict(selection=dict(const='不明确'))))),
                                           'then':dict(properties=dict(aggregation=dict(const='不明确')))})
    return system_prompt+GUIDANCE,json.dumps(m,ensure_ascii=False)

class D1ReadingContractProviderV0481:
    def __init__(self,provider):self.provider=provider;self.name=getattr(provider,'name','wrapped')
    def generate_json(self,*,system_prompt,user_prompt):
        s,u=annotate_d1_reading_contract(system_prompt,user_prompt)
        return self.provider.generate_json(system_prompt=s,user_prompt=u)
