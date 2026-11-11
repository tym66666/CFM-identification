"""Author-generated, not independently reviewed: 12 situations x 2 variants.
Business inputs deliberately do not include the answer key. Python stdlib only.
"""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

COMMON_NETWORK=(
    '研究对象是门店甲、乙、丙、丁，合作关系是甲—乙、乙—丙、丙—丁；关系在试点前形成，试点期间不变。'
    '每店使用助手记T=1，不使用记T=0。结果Y是试点后第4周订单数。')
COMMON_A5='研究组在方案书中拟采用一致性、随机分配与潜在结果独立、结果均值有限三项科学条件；这些仍须由研究者独立批准。'

CASES=[
 dict(id='N01',split='dev',domain='network',tag='sample_not_population',
      question='如果甲乙丙丁四店全部启用助手，第4周四店订单数的等权平均是多少？',
      protocol='历史试点对每家门店独立以1/2概率决定启用。'+COMMON_NETWORK+COMMON_A5,
      information_full='已知完整总体联合分布P(Y_甲,Y_乙,Y_丙,Y_丁,T_甲,T_乙,T_丙,T_丁)，不是从有限回访样本估计。',
      information_changed='仅有随机选中的40条回访问卷记录，不知道完整总体分布或全部安排条件均值。',
      changed='missing_information',kind='FIXED_POLICY_VALUE',operation='NOT_APPLICABLE',
      note='故意把总体律替换成有限回访样本；不应自动升级为A4总体。',
      checks=['研究总体四店与评价四店未混淆','目标是固定全部启用政策的水平而非差值','有限样本不被改写成总体信息']),
 dict(id='N02',split='dev',domain='network',tag='contrast_direction',
      question='相对于原方案“仅甲乙启用”，新方案“仅丙丁启用”会让四店第4周平均订单数增加多少？计算新方案减原方案。',
      protocol=COMMON_NETWORK+'历史试点在四家店中等概率抽选恰好两店开通。'+COMMON_A5,
      information_full='研究者声明已经拥有每个门店结果与完整安排的总体联合律P(Y_i,T)，并将逐条核对。',
      information_changed='团队只确认两个名单，比较口径“增加多少”和“减少多少”均有人使用，尚未明确采用哪一个方向。',
      changed='conflicting_direction',kind='TOTAL_EFFECT',operation='FIRST_MINUS_SECOND',
      note='变体删掉明确的减法方向并加入方向冲突；不应擅自定号。',
      checks=['完整版被减数为新方案丙丁','完整版减数为原方案甲乙','冲突版应提示方向未定而非猜测']),
 dict(id='N03',split='dev',domain='network',tag='direct_effect',
      question='在乙的合作邻居甲和丙都不启用助手时，乙自己启用比不启用，第4周订单数期望相差多少？',
      protocol=COMMON_NETWORK+'历史试点四店独立公平抽签。'+COMMON_A5+'乙的同伴状态固定为甲=0、丙=0。',
      information_full='总体均值表逐一列出乙在本人T=0或1、邻居暴露为0时的条件均值。',
      information_changed='同伴采用人数尚未决定是0还是2；团队只保留“比较乙自己启用与否”的问题。',
      changed='missing_peer_condition',kind='DIRECT_EFFECT',operation='FIRST_MINUS_SECOND',
      note='变体撤掉共同同伴状态；不可用不考虑邻居替换。',
      checks=['自变量是乙本人T','甲丙同伴状态固定且不自动消失','变体的同伴条件未决定']),
 dict(id='N04',split='dev',domain='network',tag='spillover_vs_direct',
      question='保持乙自己不启用，在邻居甲丙都启用与都不启用之间，乙第4周平均订单数会增加多少？用前者减后者。',
      protocol=COMMON_NETWORK+'历史试点四店独立公平抽签。'+COMMON_A5,
      information_full='研究者提供乙本人T=0、邻居启用人数0或2时的总体条件均值；邻居人数定义为甲和丙启用数之和。',
      information_changed='团队已确定要比较邻居启用2家和0家，但是乙自己的启用状态仍在讨论，尚未固定。',
      changed='missing_own_state',kind='SPILLOVER_EFFECT',operation='FIRST_MINUS_SECOND',
      note='变体不能将乙自己默认设为0。',
      checks=['区别同伴效应与乙本人效应','保存乙本人的条件','变体乙的状态为未定']),
 dict(id='N05',split='dev',domain='network',tag='conditioning_vs_standardization',
      question='只评价东区门店甲和乙，在基线客流等级为高的背景下，比较全员启用与全员不启用的第4周订单数等权平均差；前者减后者。',
      protocol=COMMON_NETWORK+'历史试点四店独立公平抽签。'+COMMON_A5+'基线客流高低在试点前记录。',
      information_full='研究者声明拥有基线客流高组内所需的总体条件结果均值。这里并未要求跨高低组再加权标准化。',
      information_changed='尚未确认目标究竟限定基线高客流组还是对高低两组加权平均；相关人群与权重未决定。',
      changed='conflicting_background',kind='TOTAL_EFFECT',operation='FIRST_MINUS_SECOND',
      note='变体区分固定背景与跨背景标准化，不得凭习惯补权重。',
      checks=['评价甲乙而非全部四店','背景是高客流条件','不自造跨组权重']),
 dict(id='N06',split='dev',domain='network',tag='evaluation_population',
      question='研究名单为甲乙丙丁，但这次只考核甲和丁：四店全部启用助手后，第4周甲丁两店平均订单数是多少？',
      protocol=COMMON_NETWORK+'历史试点四店独立公平抽签。'+COMMON_A5,
      information_full='研究者列出每店在全体启用安排下的总体平均结果，明确覆盖甲和丁。',
      information_changed='业务经理说“只考核甲丁”，另一份正式考核表写“考核四店全部”，两者尚未协调。',
      changed='conflicting_population',kind='FIXED_POLICY_VALUE',operation='NOT_APPLICABLE',
      note='变体评价名单存在矛盾，不能随意选一份。',
      checks=['研究名单四店与评价名单甲丁区分','政策是全体启用','冲突版评价对象不得凭空定下']),
 dict(id='N07',split='dev',domain='network',tag='weighted_exposure_definition',
      question='评价乙未启用时，合作权重下的邻居启用比例从0变成1，乙第4周订单数期望变化多少？后者减前者。',
      protocol=COMMON_NETWORK+'合作权重对甲为3、对丙为1；加权比例=(3T_甲+T_丙)/4。历史试点四店独立公平抽签。'+COMMON_A5,
      information_full='总体条件均值按乙未启用、加权比例分别为0与1的格子记录。',
      information_changed='报告中出现两种未协调口径：邻居启用人数与合作权重加权比例，具体用哪种仍未决定。',
      changed='conflicting_exposure',kind='SPILLOVER_EFFECT',operation='FIRST_MINUS_SECOND',
      note='变体暴露定义冲突，不能把人数当作比例。',
      checks=['区分加权比例与人数','乙自己T=0保持不变','变体暴露口径冲突']),
 dict(id='N08',split='dev',domain='network',tag='design_vs_target_policy',
      question='只让甲丙开通助手，其余乙丁不开通，这个固定政策下四店第4周平均订单数是多少？',
      protocol=COMMON_NETWORK+'历史试点为分层固定名额：甲乙组成一层、丙丁组成一层，每层等概率抽中一店。'+COMMON_A5,
      information_full='研究者声明已知历史试点下所有可出现安排所对应的总体条件均值表。',
      information_changed='历史安排机制未记录，预算文件只说未来最多选2店；没有历史抽签概率。',
      changed='missing_design',kind='FIXED_POLICY_VALUE',operation='NOT_APPLICABLE',
      note='未来预算不等于历史分层随机化；也不证明目标支持。',
      checks=['区分历史随机设计与固定目标政策','甲丙启用乙丁不启用','变体不能凭预算猜抽签']),
 dict(id='N09',split='holdout',domain='network',tag='two_queries',
      question='请回答两件事：(1) 四店全部启用后第4周平均订单数是多少？(2) 四店全部不启用相比全部启用会让平均订单数减少多少？第二问按全启用减全不启用计算。',
      protocol=COMMON_NETWORK+'历史试点四店独立公平抽签。'+COMMON_A5,
      information_full='拥有各门店每个完整历史安排的总体平均结果。',
      information_changed='第二问的减法方向有冲突：业务问题说全启用减全不启用，最新邮件说全不启用减全启用；没有最终批准的版本。',
      changed='conflicting_second_query',kind='MULTI',operation='MIXED',
      note='两个query要独立保留；变体不能擅自挑一个方向。',
      checks=['识别两个目标而非漏掉第二问','第一问固定政策均值','第二问方向按完整问句且不偷换']),
 dict(id='N10',split='holdout',domain='network',tag='time_horizon',
      question='我们关心第8周：若四店全部启用助手，第8周订单数的等权平均是什么？',
      protocol='研究对象是门店甲、乙、丙、丁，合作网络为甲—乙、乙—丙、丙—丁；处理T为是否启用。历史试点四店独立公平抽签。'+COMMON_A5,
      information_full='观察文件同时包含第4周和第8周结果；研究者明确声明第8周相应总体均值可用，历史第4周不是本问结果时点。',
      information_changed='方案中一处写考核第8周，另一处签批文件写只考核第4周，现未决定以哪一个为准。',
      changed='conflicting_time',kind='FIXED_POLICY_VALUE',operation='NOT_APPLICABLE',
      note='第4周历史记录不能悄悄替换第8周目标。',
      checks=['目标时期保持第8周','第4周不能替代目标结果','变体时期冲突需保留']),
 dict(id='D11',split='holdout',domain='dag',tag='dag_backdoor',
      question='如果主动把广告投放A设为1，下一月销量Y的总体干预分布P(Y|do(A=1))是什么？不是只问观察条件分布P(Y|A=1)。',
      protocol='变量因果图由研究者确认：客户偏好C→广告A，客户偏好C→销量Y，广告A→销量Y。三个变量均为二元；不表示门店间合作网络。',
      information_full='完整观察总体联合分布P(C,A,Y)已知，需由数学模块独立判定图假设下是否识别。',
      information_changed='关于C→Y是否存在，图纸与研究记录相互矛盾，尚待研究者确认；目前仅有1000个样本观测行，不宣称总体联合律已知。',
      changed='conflicting_graph_and_sample',kind='INTERVENTIONAL_DISTRIBUTION',operation='NOT_APPLICABLE',
      note='不能把样本行当总体P(V)，也不能把变量图当门店网络。',
      checks=['区分do分布与条件分布','变量因果图与门店网络分开','变体图有冲突且样本不冒充总体']),
 dict(id='D12',split='holdout',domain='dag',tag='dag_frontdoor',
      question='把促销X设为0时，下一月续费Y的总体干预分布是什么？研究者问P(Y|do(X=0))。',
      protocol='研究者确认变量图：促销X→接触M→续费Y；潜在共同原因U同时影响X与Y，以X↔Y表示未观测混杂。这里是变量图，不是门店合作网络。',
      information_full='观察总体联合分布P(X,M,Y)已知，M和Y均为二元。科学图仍须独立审核，不能由LLM批准。',
      information_changed='中介M是否发生在促销X之后还没有记录；因果箭头X→M是否成立尚未确认，观察总体分布也未被明确提供。',
      changed='missing_graph_order_and_population_law',kind='INTERVENTIONAL_DISTRIBUTION',operation='NOT_APPLICABLE',
      note='变体中间结构未定，不能凭“前门”常识补箭头。',
      checks=['干预变量X值为0','目标是干预分布而非均值','变体图和A4不齐不能断言POINT'])
]

# Author-drafted semantic reference cards. Never copied into a model request.
READING_GOLD={
'N01':dict(query_kinds=['FIXED_POLICY_VALUE'],first='四店全部启用',second='不适用',evaluation='甲乙丙丁等权',time='第4周',background='未限定'),
'N02':dict(query_kinds=['TOTAL_EFFECT'],first='新方案仅丙丁启用',second='原方案仅甲乙启用',evaluation='甲乙丙丁等权',time='第4周',background='未限定'),
'N03':dict(query_kinds=['DIRECT_EFFECT'],first='乙本人启用，同伴甲丙都不启用',second='乙本人不启用，同伴甲丙都不启用',evaluation='乙',time='第4周',background='甲丙处理条件固定'),
'N04':dict(query_kinds=['SPILLOVER_EFFECT'],first='乙本人不启用，邻居甲丙都启用',second='乙本人不启用，邻居甲丙都不启用',evaluation='乙',time='第4周',background='乙本人条件固定'),
'N05':dict(query_kinds=['TOTAL_EFFECT'],first='全员启用',second='全员不启用',evaluation='东区甲乙等权',time='第4周',background='基线客流高组；不是跨组标准化'),
'N06':dict(query_kinds=['FIXED_POLICY_VALUE'],first='全部四店启用',second='不适用',evaluation='仅甲丁平均',time='第4周',background='未限定'),
'N07':dict(query_kinds=['SPILLOVER_EFFECT'],first='乙不启用，同伴加权比例1',second='乙不启用，同伴加权比例0',evaluation='乙',time='第4周',background='加权=(3T甲+T丙)/4'),
'N08':dict(query_kinds=['FIXED_POLICY_VALUE'],first='甲丙启用、乙丁不启用',second='不适用',evaluation='甲乙丙丁等权',time='第4周',background='未限定'),
'N09':dict(query_kinds=['FIXED_POLICY_VALUE','TOTAL_EFFECT'],first='Q1全部启用；Q2全启用',second='Q1不适用；Q2全不启用',evaluation='甲乙丙丁等权',time='第4周',background='两个独立目标'),
'N10':dict(query_kinds=['FIXED_POLICY_VALUE'],first='四店全部启用',second='不适用',evaluation='甲乙丙丁等权',time='第8周',background='第4周不是目标'),
'D11':dict(query_kinds=['INTERVENTIONAL_DISTRIBUTION'],first='do(A=1)',second='不适用',evaluation='销量Y总体分布',time='下一月',background='变量因果图，C是共同原因'),
'D12':dict(query_kinds=['INTERVENTIONAL_DISTRIBUTION'],first='do(X=0)',second='不适用',evaluation='续费Y总体分布',time='下一月',background='X→M→Y，X↔Y混杂')}

def build():
    assert len(CASES)==12 and sum(x['domain']=='network' for x in CASES)==10
    assert sum(x['domain']=='dag' for x in CASES)==2
    for s in CASES:
        for variant in ('full','changed'):
            case_id='T6-'+s['id']+'-'+variant
            info=s['information_full' if variant=='full' else 'information_changed']
            obj={'case_id':case_id,'business_question':s['question'],
                 'response_language':'zh','sources':[
                     {'source_id':'protocol','kind':'STUDY_PROTOCOL','text':s['protocol'],'label':'研究方案声明（待独立审核）'},
                     {'source_id':'information','kind':'DATA_DICTIONARY','text':info,'label':'信息范围或变体记录'}]}
            target=ROOT/'materials'/(case_id+'.json')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            gold={'case_id':case_id,'scenario':s['id'],'domain':s['domain'],'split':s['split'],
                  'variant':variant,'change_type':None if variant=='full' else s['changed'],
                  'expected_primary_kind':s['kind'],'expected_operation':s['operation'],
                  'expected_query_count':2 if s['id']=='N09' else 1,
                  'reference_review_status':'AUTHOR_DRAFT_PENDING_INDEPENDENT_REVIEW',
                  'source_note':'下列参考是作者自拟测试口径，不是项目数学认证或独立审读结果。',
                  'manual_checks':s['checks'],'expected_fact_warning':None if variant=='full' else s['note'],
                  'must_not_claim_point_from_a0':True,'reference_semantics':READING_GOLD[s['id']],
                  'evaluation_scope':'A0目标+字段/引用；A4/A5与全链路需额外真实事实读取和审核'}
            (ROOT/'references'/(case_id+'.gold.json')).write_text(json.dumps(gold,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Wrote',len(CASES)*2,'business materials and',len(CASES)*2,'draft references')

if __name__=='__main__':build()
