"""Complete synthetic R3 businesses; hand-authored readings, not LLM scores."""
from pathlib import Path
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.network_observational_policy_reading import reference_catalog,VERSION
from .business_dispatch_reference import approve
from .network_dispatch_reference import approval_records


def material(scene='care', *, exchangeability=True, sample_only=False, zero_support=False):
    if scene=='care':
        nodes=['青桥护理站','柳岸护理站','南园护理站'];edges=[nodes[:2],nodes[1:]];population=nodes[:]
        unit='社区护理站';treatment='使用排班辅助工具';outcome='下周是否按时完成全部预约护理';outcome_kind='BINARY'
        question='这三家护理站经常互相调派护士。如果下周三家都使用排班辅助工具，三家站点按时完成全部预约护理的平均比例会是多少？评价全部三家，每家等权。'
        context='下周护理安排';conditioning='推广前已登记的同一服务片区和护理需求背景'
    elif scene=='depots':
        nodes=['青禾仓','白桥仓','云台仓','河东仓'];edges=[nodes[i:i+2] for i in range(3)];population=[nodes[0],nodes[-1]]
        unit='仓库';treatment='使用配载辅助工具';outcome='本周每单平均配载分钟数';outcome_kind='CONTINUOUS'
        question='四个仓库沿固定合作线路共享车辆。如果本周四仓都使用配载辅助工具，青禾仓与河东仓每单平均配载要多少分钟？只评价这两仓，两仓等权。'
        context='本周仓储作业';conditioning='工具采用前已登记的同一区域和配送需求背景'
    else:raise ValueError('UNKNOWN_SCENE')
    first=[1]+[0]*(len(nodes)-1);second=[1-x for x in first]
    masses=[([0]*len(nodes),'1/4'),(first,'1/8'),(second,'1/8'),([1]*len(nodes),'1/2')]
    if zero_support:masses=[([0]*len(nodes),'1/2'),(first,'1/4'),(second,'1/4')]
    docs=dict(study='完整研究名单为'+'、'.join(nodes)+'。研究单位为'+unit+'；'+treatment+'记1，不使用记0。结果为'+outcome+'。'+('是记1，否记0。' if outcome_kind=='BINARY' else '')+'研究背景为'+context+'。',
        network='存在对象间影响。合作网络在采用工具前固定，本期不变。完整简单无向合作边为'+'、'.join('与'.join(e) for e in edges)+'；没有其他边，无自环或重复边。',
        regime='过去由各负责人根据经营情况自行决定是否使用工具，没有随机抽签。',
        conditioning='本研究固定在'+conditioning+'，全部条件在采用工具前确定；本题不跨背景层平均。',
        science='本合成研究拟采用：观察结果等于实际完整使用安排下的潜在结果；处理前合作网络固定；所有相关条件一阶矩有限。',
        exchangeability=('本合成研究拟采用：在上述固定处理前背景下，全部对象在所有完整二元安排下的潜在结果表，与实际完整使用向量条件独立。' if exchangeability is True else
            '是否采用在该处理前背景下全部潜在结果表与完整使用向量条件独立的条件，尚未决定。' if exchangeability is None else
            '本研究明确不采用在该处理前背景下全部潜在结果表与完整使用向量条件独立的条件。'))
    if sample_only:
        docs['information']='现有的使用名单和经营结果仅为有限回访记录。下列比例是样本频数，不是已知总体概率，条件均值也只是估计。'
    else:
        docs['information']='本合成理论研究明确给定同一个符号总体信息算子：在上述同一网络、结果定义和固定处理前背景下，包含完整使用向量的条件总体分布，并覆盖所有正概率安排下每个研究对象的结果条件总体均值。均值不给数值，不是样本估计。下表列全所有正概率安排，未列安排的总体概率为零。'
    docs['table']='对象顺序为'+'、'.join(nodes)+'。\n'+'\n'.join('完整使用向量'+str(z)+'，'+('样本比例' if sample_only else '总体条件概率')+'为'+p+'。' for z,p in masses)
    case=BusinessCase(case_id='observational_policy_'+scene,business_question=question,sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return case,dict(nodes=nodes,edges=edges,population=population,assignment=[1]*len(nodes),unit=unit,treatment=treatment,
        outcome=outcome,outcome_kind=outcome_kind,context=context,conditioning=conditioning,masses=masses,
        sample_only=sample_only,exchangeability=exchangeability)


def a0_reference(case,data):
    catalog=build_catalog(case)
    def claim(value,source='business_question'):
        return dict(state='STATED',value=value,refs=[r['ref'] for r in catalog if r['source_id']==source])
    question=claim(case.business_question)
    return dict(common=dict(analysis_unit=claim(data['unit'],'study'),treatment=claim(data['treatment'],'study'),
        outcome=claim(data['outcome'],'study'),unit_network=claim(case.source_map()['network'],'network'),
        assignment_family='OBSERVATIONAL',assignment_law=claim(case.source_map()['regime'],'regime')),
        queries=[dict(kind='FIXED_POLICY_VALUE',goal=question,semantics=dict(target_population=question,
            intervention=question,policy_assignment=question,aggregation=question,time_horizon=claim(data['context'],'study')))])


def fact_reference(entry,data):
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    def declaration(value,source):return dict(value=value,source_ids=ids(source))
    return dict(version=VERSION,reference_context=refs['context'],
        study=dict(nodes=data['nodes'],edges=data['edges'],graph_kind='SIMPLE_UNDIRECTED',edge_list_complete=True,
            treatment=data['treatment'],outcome=data['outcome'],outcome_kind=data['outcome_kind'],context=data['context'],source_ids=ids('study')+ids('network')),
        regime=dict(kind='OBSERVATIONAL',source_ids=ids('regime')),
        conditioning=dict(kind='FIXED_PRETREATMENT_CONTEXT',definition=data['conditioning'],source_ids=ids('conditioning')),
        target=dict(kind='FIXED_POLICY_MEAN',assignment=dict(zip(data['nodes'],data['assignment'])),population=data['population'],aggregation='EQUAL_MEAN',source_ids=ids('__question__')),
        assumptions=dict(full_vector_conditional_exchangeability=declaration(data['exchangeability'],'exchangeability'),
            **{name:declaration(True,'science') for name in ('consistency','fixed_pretreatment_network','finite_conditional_first_moments')}),
        information=[dict(operator='FINITE_SAMPLE' if data['sample_only'] else 'OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS',
            availability='FINITE_SAMPLE' if data['sample_only'] else 'SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=list(data['nodes']),
            assignment_masses=[dict(assignment=dict(zip(data['nodes'],z)),probability=p,source_ids=ids('table')) for z,p in data['masses']],
            **{name:declaration(None if data['sample_only'] else True,'information') for name in
               ('complete_positive_assignment_support','means_for_all_positive_assignments','same_study_and_conditioning')},source_ids=ids('information')+ids('table'))],
        additional_restrictions=[],unresolved=[])


def setup(scene='care', **kwargs):
    case,data=material(scene,**kwargs);s=intake.start(case)
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    query_review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=query_review)
    options=dict(query_review=query_review,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])
    return s,entry,options


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for name,scene,kwargs,expected in (
        ('care','care',{},'POINT'),('depots','depots',{},'POINT'),
        ('unknown_exchangeability','care',dict(exchangeability=None),'NEEDS_INPUT'),
        ('refused_exchangeability','care',dict(exchangeability=False),'ADAPTER_NOT_CONNECTED'),
        ('sample_only','care',dict(sample_only=True),'NEEDS_INPUT'),
        ('zero_support','care',dict(zero_support=True),'UNSUPPORTED')):
        s,e,o=setup(scene,**kwargs);p=dispatch.inspect_methods(s,'q1',**o)
        approvals=approval_records(p) if p.get('methods') else dict(research_protocol_selected=True)
        r=dispatch.execute(s,'q1',**o,**approvals);assert r['state']==expected,r
        whole=None
        if expected=='POINT':
            whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})},
                case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
            assert whole['results'][0]['result']['independent_replay']
        intake.save(s,out/(name+'_intake.json'));intake.write_json(out/(name+'_case.json'),s.case.model_dump(mode='json'))
        intake.write_json(out/(name+'_result.json'),dict(plan=p,result=r,whole_case=whole))
        rows.append(dict(case=name,state=r['state'],independent_replay=r['independent_replay'],backend_called=r['backend_called']))
    intake.write_json(out/'SUMMARY.json',dict(api_calls=0,hand_authored_readings=True,synthetic_reviews_only=True,rows=rows))
    return rows


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true');a=p.parse_args()
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic fixture review selection required')
    print(json.dumps(run(a.output),ensure_ascii=False))
