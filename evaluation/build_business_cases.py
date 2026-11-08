"""Create 24 short, synthetic, plain-language business questions.

Developer references MUST stay out of real LLM prompts. No client or sales data.
"""
from __future__ import annotations
import json
from pathlib import Path

# category, question, plausible target alternatives, biggest ambiguity (internal audit only)
CASES = [
 ('企业协作','我们给部分销售员装了 AI 助手，大家会互相分享经验。用了 AI 的人业绩真的会更好吗？',['DIRECT_EFFECT','ATE'],'对其他人的使用情况尚不清楚'),
 ('企业协作','有些销售员虽然没用 AI，但经常向用 AI 的同事请教。他们会不会也提高业绩？',['SPILLOVER_EFFECT'],'同事之间的影响如何定义'),
 ('企业协作','我们只能给 100 位销售员开通 AI，应该选谁才能让整个团队销售额更高？',['POLICY_OPTIMIZATION'],'没有明确的分配协议和未来方案'),
 ('市场营销','客户之间会推荐朋友。给一些人发优惠券，没收到的人会不会也更愿意购买？',['SPILLOVER_EFFECT'],'用户关系与优惠券发放机制尚不清楚'),
 ('市场营销','推广预算只能覆盖部分客户。怎样选人发券，最终订单总额可能更高？',['POLICY_OPTIMIZATION'],'需要界定总收益与投放预算'),
 ('市场营销','我们向部分社区做广告，周围社区的销量也变了。这能说明广告带来额外销量吗？',['OTHER','SPILLOVER_EFFECT'],'需要分清同时变化的因素和因果效应'),
 ('连锁零售','我们给几家门店试用了新促销，邻近门店可能抢同一批顾客。促销真的让公司多赚了吗？',['TOTAL_EFFECT','FIXED_POLICY_VALUE','ATE'],'门店互相影响且可能挤出销售'),
 ('连锁零售','这次只随机选一半门店试新陈列，下一季全部推广，公司总销售会怎样？',['FIXED_POLICY_VALUE'],'随机一半的具体办法和全部推广的支持尚不明确'),
 ('连锁零售','两家商场距离很近。只给其中一家降价会不会让另一家的客流减少？',['SPILLOVER_EFFECT'],'如何分配降价和观察客流尚不清楚'),
 ('电商平台','平台上的商家会争夺相同买家。扶持一部分商家，会不会影响没被扶持的商家的订单？',['SPILLOVER_EFFECT'],'共享买家网络如何定义'),
 ('电商平台','如果明年给所有商家增加推荐流量，平台总体成交额会比现在高多少？',['FIXED_POLICY_VALUE'],'全员推广不是四臂均值的同义词'),
 ('电商平台','我们想在一些主播之间推广直播工具，哪些主播应该先用，平台整体效果才最好？',['POLICY_OPTIMIZATION'],'需要明确共同平台结果与网络溢出'),
 ('学校培训','班级里学生互相讨论题目。补习课程只给部分学生，未参加的同学成绩会不会受到影响？',['SPILLOVER_EFFECT'],'班级互相影响可能存在'),
 ('学校培训','给每个班一部分学生配学习助手，与全班都配相比，平均考试成绩会有怎样的变化？',['FIXED_POLICY_VALUE','TOTAL_EFFECT'],'两种完整推广方案的比较'),
 ('学校培训','学校按老师建议给成绩落后的学生安排辅导，后来成绩好了。能说辅导有效吗？',['ATE','CATE'],'观察性安排可能包含混杂'),
 ('物流配送','仓库之间可以互相调货。改造一个仓库后，附近仓库的发货速度会变快还是变慢？',['SPILLOVER_EFFECT'],'跨仓调拨网络影响'),
 ('物流配送','升级预算只能覆盖三个配送站。应该改造哪些站点，整体配送延误才可能最少？',['POLICY_OPTIMIZATION'],'全局优化需要明确预算和站点联动'),
 ('物流配送','我们先挑一半配送站试新排班。如果之后所有站都采用，平均送达时间会怎样？',['FIXED_POLICY_VALUE'],'原试验是否固定配额尚不明'),
 ('医疗协作','医院之间会转诊。给一些医院增加远程会诊，会不会也减轻附近医院的排队压力？',['SPILLOVER_EFFECT'],'转诊关系和治疗安排'),
 ('医疗协作','只有部分社区诊所使用提醒系统，其他诊所的复诊率也变化了。能判断提醒系统的作用吗？',['OTHER','SPILLOVER_EFFECT'],'诊所分配非显式随机'),
 ('医疗协作','如果把预约提醒系统部署到整个医院网络，患者等待时间可能缩短多少？',['FIXED_POLICY_VALUE'],'需要明确全网络部署的目标与支持'),
 ('生产协作','生产线之间共用设备。只给部分产线安装监控系统，其他产线的停机时间会受到影响吗？',['SPILLOVER_EFFECT'],'设备共享网络'),
 ('生产协作','我们只在两条生产线试用了 AI 质检。把它推广到全厂能减少多少报废成本？',['FIXED_POLICY_VALUE'],'试点与全厂推广的对应关系'),
 ('生产协作','新排班由主管决定，产线之间还会借人。产出提高了，能否判断是排班造成的？',['OTHER','ATE'],'观察性安排和产线联动'),
]

def build() -> dict:
    items = []
    for idx,(category,question,targets,ambiguity) in enumerate(CASES,1):
        items.append({
            'id': f'B{idx:02d}',
            'category': category,
            'business_case': {'case_id':f'B{idx:02d}', 'business_question':question, 'sources':[], 'response_language':'zh'},
            'reference_for_developers_only': {
                'plausible_target_kinds': targets,
                'principal_ambiguity': ambiguity,
                'requires_independent_review': True,
            },
        })
    return {
        'dataset_version':'cfm-id-real-business-v0.5',
        'provenance':'Synthetic everyday business situations written for product testing; no real customer data.',
        'warning':'References are developer hints, not mathematical ground-truth or proof. Never show references to the LLM.',
        'cases':items,
    }


def main():
    output=Path(__file__).resolve().parent/'business_cases.json'
    output.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {output} ({len(CASES)} business questions)')

if __name__=='__main__': main()
