"""Public synthetic business materials, never real study data or model replies."""


def case(case_id='A'):
    if case_id not in ('A', 'B', 'C', 'D'):
        raise ValueError('CASE_MUST_BE_A_B_C_D')
    population = '全部符合报名条件的人' if case_id == 'B' else '因获得资格才参加培训的人'
    question = f'对{population}，参加培训相对不参加，对三个月内就业概率平均增加多少？'
    table = ('Z=0: D0Y0=1,D0Y1=0,D1Y0=0,D1Y1=0；'
             'Z=1: D0Y0=0.5,D0Y1=0,D1Y0=0,D1Y1=0.5。')
    if case_id == 'D':
        # Positive first stage and Wald=0.5, but monotone-IV constraints conflict.
        table = ('Z=0: D0Y0=0.3,D0Y1=0.3,D1Y0=0.3,D1Y1=0.1；'
                 'Z=1: D0Y0=0.35,D0Y1=0.05,D1Y0=0.15,D1Y1=0.45。')
    exclusion = ('资格除通过实际参加外不直接影响就业。' if case_id != 'C'
                 else '是否可以排除资格通知本身对就业的影响尚未确定。')
    return dict(case_id='synthetic-iv-'+case_id, business_question=question,
        response_language='zh', sources=[
            dict(source_id='protocol', text=(
                '以下为虚构的合成研究场景，不是真实业务或科学批准。研究单位为报名者。'
                'Z表示资格(1获得、0未获得)，D表示实际参加(1参加、0不参加)，'
                'Y表示三个月内就业(1就业、0未就业)。两资格组概率各为0.5。'
                '研究拟采用资格与全部潜在参加和结果独立、一致性、无个体间干扰。'
                + exclusion + '本模型拟施加D(1)>=D(0)：获得资格不会使本来参加的人放弃参加；'
                '这不表示培训一定改善结果。对ATE可另建明确不施加该条件的审核版本。')),
            dict(source_id='population', text=(
                '合成信息提供者明确给定同一报名总体的精确条件分布P(D,Y|Z)，不是样本频数；'
                '每组包含下列全部四格，编码沿用研究方案。'+table))])
