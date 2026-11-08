"""Four NBIB business-text matched, NO-API-KEY, real-Core demonstration fixtures.

The original 21 NBIB stories are *not* formal identification data.  This module
recognizes ONLY an unchanged original case description, then (on a SEPARATE,
explicitly marked synthetic-study action) creates a prewritten hypothetical
network, exact random assignment and typed population information, and executes
existing math Core + independent replay. It NEVER certifies the original real
business or derives assumptions from text.  No new theorem, estimator or LLM.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any
import json

from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
from pfn_pipeline.identification import make_complete_randomization_arm_task
from pfn_pipeline.identification_business import (
    ArmInquiryV21, FixedPolicyInquiryV21,
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, declare_signature_population_source,
    admit_mean_signature_sufficiency,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, declare_network_a4_source, fixed_policy_target_from_context,
)
from identification_only import from_verified_core

ROOT = Path(__file__).resolve().parents[1]
NBIB_PATH = ROOT / 'assets/benchmark_assets' / 'benchmarks' / 'network_business_identification'
CASE_IDS = ('NBIB-002','NBIB-007','NBIB-008','NBIB-009')

DESCRIPTIONS = {
    'NBIB-002': '48 个站点中固定抽出 24 个试用排班系统；研究已使用系统、且恰好一个相邻站点使用时的平均延误。',
    'NBIB-007': '14 名员工独立随机试用协作平台；研究全员上线后的整体表现。',
    'NBIB-008': '14 家门店固定只抽 7 家安装系统；想知道全员安装后的整体收入。',
    'NBIB-009': '同一 14 家门店试验；如果额外接受“收入均值只依赖本店和是否有邻店采用”的假设，能否研究全员推广？',
}
SYNTHETIC_CONDITIONS = {
    'NBIB-002': (
        '假设 48 站点形成固定环形支援网络，全部 24 人处理组合等概率；'
        '另声明并接受目标 Arm 的总体条件均值算子。原文件未提供该总体算子。'
    ),
    'NBIB-007': (
        '假设 14 名员工彼此独立、各以 1/2 概率抽签；以一个固定环形协作网表示关系；整体表现以 14 人等权平均表示；'
        '另声明并接受完整分配层次总体条件均值算子。正支持可能极小。'
    ),
    'NBIB-008': (
        '采用旗舰店连接 13 家合作门店的星型固定图，原试验均匀抽 7 家安装；'
        '另声明完整分配层次总体信息，不增加干扰结构充分性假设。本数学目标是14店等权平均收入，原问题所说总收入需要乘以固定门店数，未提供任何数值。'
    ),
    'NBIB-009': (
        '采用与 NBIB-008 完全相同的星型图和固定 7 家抽签；'
        '另外独立接受 E5 任一邻店采用的均值签名充分性，并声明所需总体签名均值。本数学目标是14店等权平均收入，总收入可在固定门店数下作已知比例换算。'
    ),
}


def _raw_cases() -> dict[str,dict[str,Any]]:
    data = json.loads((NBIB_PATH/'gateway_target_only_cases.json').read_text(encoding='utf-8'))
    return {c['case_id']: c for c in data if c['case_id'] in CASE_IDS}


def catalog() -> list[dict[str,Any]]:
    """The packaged, immutable-by-source-control four-case NBIB text catalog.

    Built from the original NBIB dataset and checked against it when the source
    repository is available; works in an installed wheel without that repository.
    """
    package_catalog = Path(__file__).resolve().parent/'web'/'no_key_case_catalog.json'
    if package_catalog.is_file():
        rows=json.loads(package_catalog.read_text(encoding='utf-8'))
        if [r.get('case_id') for r in rows]!=list(CASE_IDS):
            raise RuntimeError('Packaged curated NBIB catalog is inconsistent')
        if (NBIB_PATH/'gateway_target_only_cases.json').is_file():
            source=_raw_cases()
            for r in rows:
                if (sha256(source[r['case_id']]['business_question'].encode('utf-8')).hexdigest()
                        !=r['text_sha256']):
                    raise RuntimeError('Packaged NBIB text differs from original benchmark')
        return rows
    known = _raw_cases()
    if set(known) != set(CASE_IDS):
        raise RuntimeError('Curated NBIB source set has changed')
    return [dict(
        case_id=cid,
        title=DESCRIPTIONS[cid],
        business_text=known[cid]['business_question'],
        questions=[entry['quote'] for entry in known[cid]['expected']],
        text_sha256=sha256(known[cid]['business_question'].encode('utf-8')).hexdigest(),
        overlay=SYNTHETIC_CONDITIONS[cid],
        input_kind='ORIGINAL_NBIB_BUSINESS_LANGUAGE',
        original_a4_status='NOT_PROVIDED',
    ) for cid in CASE_IDS]


def _assumptions() -> tuple[Assumption,...]:
    return tuple(Assumption(name=a, source='demo_specification', confirmed=True,
            status='ADMITTED', evidence=['Hypothetical laboratory research setting, not a real-world verification'])
                 for a in REQUIRED)


def _policy_study(case_id: str):
    n=14
    nodes=tuple(f'site-{i:02d}' for i in range(n))
    if case_id == 'NBIB-007':
        edges=tuple((nodes[i],nodes[(i+1)%n]) for i in range(n))
        design={'kind':'heterogeneous_bernoulli_binary_v1',
                'propensities':{node:'1/2' for node in nodes}}
    else:
        edges=tuple((nodes[0],node) for node in nodes[1:])
        design={'kind':'complete_randomization_binary_v1','m':7}
    return declare_network_study(
        network_id='SYNTH-NBIB-007-ring14' if case_id == 'NBIB-007' else 'SYNTH-NBIB-008-009-star14',
        node_order=nodes,undirected_edges=edges,
        treatment_variable='software_access',outcome_variable=('delivery_quality' if case_id == 'NBIB-007' else 'store_revenue'),
        outcome_kind='continuous',context_reference='W=synthetic_pre',
        observation_regime='experimental',assignment_design=design,
        protocol_provenance='HYPOTHETICAL: not certified from original NBIB logs',
        network_provenance='HYPOTHETICAL pretreatment graph aligned to business network type',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _formal_inquiry(case_id: str):
    if case_id == 'NBIB-002':
        n=48
        nodes=tuple(f'site-{i:02d}' for i in range(n))
        network=NetworkExposureSpec(
            network_id='SYNTH-NBIB-002-ring48',node_ids=list(nodes),
            undirected_edges=[(nodes[i],nodes[(i+1)%n]) for i in range(n)])
        task=make_complete_randomization_arm_task(
            network,m=24,node_id=nodes[0],own_treatment_value=1,
            exposure_value=1,exposure_definition='exact_treated_neighbor_count',
            source='HYPOTHETICAL_NBIB_002_TYPED_ARM_POPULATION',
            evidence='Additional typed symbolic population law; not obtained from the original business files',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
        return ArmInquiryV21(task)
    study=_policy_study(case_id)
    target=fixed_policy_target_from_context(
        study,(1,)*len(study.node_order),authority='TRUSTED_FIXTURE')
    src=declare_network_a4_source(
        study,source_id='SYNTHETIC_POLICY_NODE_FULL_LAW',operator='NODE_FULL_LAW',
        provenance='Hypothetical symbolic population operator; not inferred from company observations',
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=study.node_order)
    if case_id!='NBIB-009':
        return FixedPolicyInquiryV21(study,target,_assumptions(),r1b_sources=(src,))
    sig=declare_policy_signature(study,grouping='any_treated_neighbor')
    signature_src=declare_signature_population_source(
        study,sig,source_id='SYNTHETIC_ACCEPTED_ANY_NEIGHBOR_SIGNATURE_MEANS',
        operator='NODE_SIGNATURE_MEANS',outcome_nodes=study.node_order,
        signature_cells=tuple((node,1,1) for node in study.node_order),
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        provenance='Hypothetical typed population node-signature means, no numerical outcomes')
    suff=admit_mean_signature_sufficiency(
        study,sig,covered_nodes=study.node_order,
        assumption=Assumption(name='mean_signature_sufficiency',source='human_confirmation',
            status='ADMITTED',confirmed=True,
            evidence=['Additional mean restriction explicitly stipulated across all assignments in this toy study']))
    return FixedPolicyInquiryV21(study,target,_assumptions(),r1b_sources=(src,),
        r2_signature=sig,r2_sufficiency=suff,r2_sources=(signature_src,))


def run_curated(case_id: str, business_text: str, *, synthetic_protocol_selected: bool) -> dict[str,Any]:
    """Fail-closed exact-text boundary; no user text can create A4/A5 permissions.

    Returns a Core-replayed mathematical outcome ONLY for the explicitly selected
    synthetic research overlay. Never returns a verified status for arbitrary prose.
    """
    records={row['case_id']:row for row in catalog()}
    if not isinstance(case_id,str) or case_id not in records:
        return {'status':'REVIEW_REQUIRED','reason':'未列入受控演示的问题；需要人工形式化或 A0 审核。',
                'core_called':False,'point_certified':False}
    row=records[case_id]
    if not isinstance(business_text,str) or sha256(business_text.encode('utf-8')).hexdigest()!=row['text_sha256']:
        return {'status':'REVIEW_REQUIRED','reason':'业务描述与已确认的示例不一致；不能复用旧数学合同。',
                'core_called':False,'point_certified':False,'case_id':case_id}
    if synthetic_protocol_selected is not True:
        return {'status':'REVIEW_REQUIRED','reason':'原 NBIB 没有正式总体信息；必须先审核科学条件。',
                'core_called':False,'point_certified':False,'case_id':case_id,
                'original_business_not_certified':True}
    outcome=identify_network_business_query(_formal_inquiry(case_id))
    if outcome.status=='POINT' and replay_verified_business_outcome(outcome) is not True:
        raise RuntimeError('Formal Core POINT failed independent replay')
    report=from_verified_core(outcome,case_id=case_id+'-SYNTHETIC',
        business_question=row['questions'][0],setting=row['title'],
        design={'NBIB-002':'D2','NBIB-007':'D1','NBIB-008':'D2','NBIB-009':'D2'}[case_id],
        exposure='E4' if case_id=='NBIB-002' else ('E5' if case_id=='NBIB-009' else '不使用暴露映射'),
        assumptions_description='仅合成演示中独立接受的数学前提；现实合法性未审核',
        information_description='仅合成演示中额外声明的 typed 总体算子；原题库未提供')
    return {
        'status':outcome.status,'reason_code':outcome.reason_code,
        'route':outcome.route,'case_id':case_id,
        'core_called':True,'point_certified':report['proof']['replay_verified'],
        'core_replay_verified':report['proof']['replay_verified'],
        'scientific_fixture':'HYPOTHETICAL_NOT_REAL_BUSINESS_EVIDENCE',
        'original_business_not_certified':True,
        'business_text_sha256':row['text_sha256'],
        'summary':row['title'],'question':row['questions'][0],
        'formal_target_plain':('指定站点处于“本人使用、恰有一位相邻站点使用”时的平均延误'
            if case_id == 'NBIB-002' else '14名员工全员使用时的等权平均交付质量'
            if case_id == 'NBIB-007' else '14家门店全员安装后的等权平均收入；原问题的总收入是该均值的14倍'),
        'conditional_story':SYNTHETIC_CONDITIONS[case_id],
        'identification':report['identification'],
        'proof':report['proof'],
        'scientific_conditions':[
            {'name':'业务目标及比较方式','state':'confirmed','explanation':'仅与 NBIB 原文精确匹配；额外数学目标以合成实例预设'},
            {'name':'试验分配与网络结构','state':'confirmed','explanation':'合成研究协议已明确；不代表原企业实际网络获得验证'},
            {'name':'总体研究信息','state':'confirmed','explanation':'合成研究另行声明了总体算子，原题库没有'},
            {'name':'因果前提','state':'confirmed','explanation':'合成研究另行接受；不代表真实科学论证'},
            {'name':'目标状态可出现','state':'confirmed' if outcome.status=='POINT' else 'failed',
             'explanation':'依正式 Core 对本合成分配律进行精确检查'},
        ],
        'numeric_value':None,
        'not_real_world_identification':True,
        'nonidentification_proven':False,
    }


def build_snapshot() -> dict:
    out=[]
    for row in catalog():
        raw=run_curated(row['case_id'],row['business_text'],synthetic_protocol_selected=False)
        formal=run_curated(row['case_id'],row['business_text'],synthetic_protocol_selected=True)
        out.append({'catalog':row,'original':raw,'synthetic':formal})
    return {'schema':'cfm-id-v3-no-key-curated-v1',
            'cases':out,'api_key_needed':False,'llm_called':False,
            'new_business_auto_identified':False,
            'all_core_points_replayed':all(not x['synthetic']['point_certified'] or
                                            x['synthetic']['proof']['replay_verified'] for x in out)}
