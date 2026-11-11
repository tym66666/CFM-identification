"""Deterministic, business-friendly readout of existing Gateway reports.

NO theorem inference, NO new A4/A5 permissions, NO economic estimate or ROI.
All wording derives from status and audited draft fields; a user chooses depth.
This is a view model, not an IdentificationResult or a proof certificate.
"""
from __future__ import annotations

from enum import Enum
from html import escape
from typing import Literal

from pydantic import Field, model_validator

from .audit import fingerprint_business_case
from .candidate_reasoner import GatewayRunV03
from .orchestration_schemas import canonical_sha256
from .schemas import BusinessCase, StrictModel, TargetKind


class Audience(str, Enum):
    BUSINESS = 'business'
    INVESTOR = 'investor'
    SCHOLAR = 'scholar'


class BusinessExplanationV05(StrictModel):
    schema_version: Literal['cfm-id-business-explanation-v0.5'] = 'cfm-id-business-explanation-v0.5'
    case_id: str
    input_sha256: str
    audience: Audience
    response_language: Literal["zh", "en"] = "zh"
    candidate_verification_level: Literal["NONE", "LLM_UNVERIFIED"] = "NONE"
    stage: Literal[
        'NEED_INFORMATION', 'WAIT_REVIEW', 'NO_CORE', 'MOCK_PREVIEW',
        'VERIFIED_BY_CORE', 'CORE_NEEDS_INFORMATION', 'LIBRARY_GAP',
        'TECHNICAL_BLOCK', 'UNVERIFIED_SUGGESTION', 'UNVERIFIED_UNDETERMINED',
        'CANDIDATE_REJECTED',
    ]
    verification_level: Literal['NOT_PERFORMED', 'MOCK_ONLY', 'CORE_REPLAY_VERIFIED', 'FAILED', 'LLM_UNVERIFIED']
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=5, max_length=1600)
    understood_goal: str = Field(min_length=3, max_length=1600)
    questions: list[str] = Field(default_factory=list, max_length=3)
    next_steps: list[str] = Field(default_factory=list, max_length=5)
    academic_details: list[str] = Field(default_factory=list, max_length=22)
    disclosure: str = Field(min_length=3, max_length=1500)
    # This presentation layer can never authorize numerical estimation.
    estimation_handoff_allowed: bool = False
    has_numerical_estimate: bool = False

    @model_validator(mode='after')
    def forbid_estimation_and_fake_verification(self):
        if self.estimation_handoff_allowed or self.has_numerical_estimate:
            raise ValueError('Business view cannot authorize Estimation or numerical effects')
        if self.stage == 'VERIFIED_BY_CORE' and self.verification_level != 'CORE_REPLAY_VERIFIED':
            raise ValueError('CORE_VERIFIED wording requires independent Core replay status')
        if self.stage == 'UNVERIFIED_SUGGESTION' and self.candidate_verification_level != 'LLM_UNVERIFIED':
            raise ValueError('LLM suggestions must remain unverified')
        if self.stage == 'MOCK_PREVIEW' and self.verification_level != 'MOCK_ONLY':
            raise ValueError('Simulated answers must remain mock only')
        return self


_TARGET_ZH = {
    TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN: '比较某种自己使用情况和同事使用情况对应的平均结果',
    TargetKind.DIRECT_EFFECT: '了解一项措施对接受它的人的影响',
    TargetKind.SPILLOVER_EFFECT: '了解一项措施会不会影响周围没有直接接受它的人',
    TargetKind.LOCAL_TOTAL_EFFECT: '了解本人和同伴状态共同改变时的设计平均总效应',
    TargetKind.TOTAL_EFFECT: '了解一项措施在个人和相互影响叠加后带来的效果',
    TargetKind.LATE: '了解因获得资格才参加者的参加效应',
    TargetKind.ATE: '了解一项措施平均会带来什么变化',
    TargetKind.CATE: '了解不同类型的人使用措施后，效果有何不同',
    TargetKind.FIXED_POLICY_VALUE: '评估某一个确定的推广方案对整体结果的影响',
    TargetKind.STOCHASTIC_POLICY_VALUE: '评估按一定概率实施不同方案时的整体结果',
    TargetKind.POLICY_OPTIMIZATION: '决定怎样分配措施，才能让整体效果更好',
    TargetKind.INTERVENTIONAL_DISTRIBUTION: '了解实施措施后结果可能怎样分布',
    TargetKind.OTHER: '研究您提出的特定业务影响',
    TargetKind.UNRESOLVED: '弄清楚究竟要比较什么业务结果',
}
_TARGET_EN = {
    TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN: 'average outcomes for a specified treatment and peer-exposure group',
    TargetKind.DIRECT_EFFECT: 'how an intervention affects the person receiving it',
    TargetKind.SPILLOVER_EFFECT: 'how an intervention affects connected people',
    TargetKind.LOCAL_TOTAL_EFFECT: 'the design-averaged total contrast changing own and peer treatment states',
    TargetKind.TOTAL_EFFECT: 'the overall effect allowing for interactions',
    TargetKind.LATE: 'the participation effect for compliers',
    TargetKind.ATE: 'the average change caused by an intervention',
    TargetKind.CATE: 'how effects differ between groups',
    TargetKind.FIXED_POLICY_VALUE: 'the outcome under a particular rollout plan',
    TargetKind.STOCHASTIC_POLICY_VALUE: 'the outcome under a randomized rollout plan',
    TargetKind.POLICY_OPTIMIZATION: 'which rollout plan would work best',
    TargetKind.INTERVENTIONAL_DISTRIBUTION: 'how outcomes are distributed after intervening',
    TargetKind.OTHER: 'the specific business impact you described',
    TargetKind.UNRESOLVED: 'which business impact you want to compare',
}

_QUESTION_ZH = {
    'target.kind': '您最想知道的是：措施对使用者自身的影响、对周围人的影响，还是某套推广方案的整体收益？',
    'information_design.assignment_family': '当初是怎样决定谁能使用这项措施的？每个人独立抽取、固定名额随机抽取，还是按业务情况决定？',
    'information_design.population_information_level': '您手里有哪些试验和结果记录？是否保留了每个人的分配方式、关系网络与结果？（这些记录本身不等于已获得完整总体信息。）',
    'units_variables.analysis_unit': '这项业务研究的对象是员工、客户、门店，还是其他单位？',
    'units_variables.treatment': '您实际做了什么改变？比如开放新工具、发放优惠券或调整服务。',
    'units_variables.outcome': '您最想观察哪个结果？例如销售额、复购率或成交量，以及观察多久？',
    'structure.exposure_mapping': '您想怎样描述周围人的影响：看有多少人参与、参与比例，还是关系强弱？',
}
_QUESTION_EN = {
    'target.kind': 'Are you asking about effects on participants, effects on connected people, or results of a rollout plan?',
    'information_design.assignment_family': 'How was the intervention assigned: independent draws, a fixed random quota, or business selection?',
    'information_design.population_information_level': 'What allocation, network and outcome records do you have? (Records alone do not establish the population information needed for identification.)',
    'units_variables.analysis_unit': 'Who is the unit of analysis: employees, customers, stores or something else?',
    'units_variables.treatment': 'What exactly changed for the units?',
    'units_variables.outcome': 'Which result matters and over what period?',
    'structure.exposure_mapping': 'How should peer exposure be described: number, share, or strength of relationships?',
}

_QUESTION_PRIORITY = (
    'target.kind', 'information_design.assignment_family',
    'units_variables.outcome', 'units_variables.treatment', 'units_variables.analysis_unit',
    'structure.exposure_mapping', 'information_design.population_information_level',
)


def friendly_questions(run: GatewayRunV03, *, language: str = 'zh', max_questions: int = 2) -> list[str]:
    """Translate only actual outstanding question paths, never invent missing assumptions."""
    if not 0 <= max_questions <= 3:
        raise ValueError('max_questions must be between 0 and 3')
    questions = run.formulation.suggested_questions
    paths = {q.field_path for q in questions if q.priority == 'HIGH'}
    mapping = _QUESTION_ZH if language == 'zh' else _QUESTION_EN
    result: list[str] = []
    if max_questions == 0:
        return []
    for field in _QUESTION_PRIORITY:
        if field in paths and field in mapping:
            result.append(mapping[field])
        if len(result) == max_questions:
            break
    # Keep a generic next step for an unrecognized field; do not print technical field names.
    if len(result) < max_questions and len(result) < len(paths):
        result.append('还有一项业务定义需要您确认，可请研究人员查看完整草稿。' if language == 'zh'
                      else 'Another detail needs review; please check the full research draft.')
    return result[:max_questions]


def _consistency_check(case: BusinessCase, run: GatewayRunV03) -> None:
    form, route, candidate = run.formulation, run.routing, run.candidate
    sh = fingerprint_business_case(case)
    dh = canonical_sha256(form.draft)
    if form.case_id != case.case_id or form.input_sha256 != sh:
        raise ValueError('Business presentation input does not match audited formulation')
    if route.case_id != case.case_id or route.input_sha256 != sh or route.draft_sha256 != dh:
        raise ValueError('Business presentation routing belongs to a different draft')
    if candidate is not None:
        if (route.status not in ('CORE_UNSUPPORTED', 'MOCK_CORE_RESULT')
                or candidate.routing_sha256 != canonical_sha256(route)
                or candidate.input_sha256 != sh
                or candidate.draft_sha256 != dh
                or candidate.case_id != case.case_id):
            raise ValueError('Candidate report is not bound to this valid routing')
        if route.status == 'CORE_UNSUPPORTED' and candidate.execution_mode != 'CORE_UNSUPPORTED':
            raise ValueError('Candidate execution mode does not match the core')
        if route.status == 'MOCK_CORE_RESULT' and (candidate.execution_mode != 'MOCK_PREVIEW'
                                                  or route.core_status != 'UNSUPPORTED'):
            raise ValueError('Mock candidate preview is inconsistent')


def explain_business(case: BusinessCase, run: GatewayRunV03, *,
                     audience: Audience | str = Audience.BUSINESS,
                     max_questions: int = 2) -> BusinessExplanationV05:
    """Make a faithful plain-language VIEW of the already completed run."""
    _consistency_check(case, run)
    audience = Audience(audience)
    zh = case.response_language == 'zh'
    form, route, candidate = run.formulation, run.routing, run.candidate
    target = form.draft.target.kind
    goal = (_TARGET_ZH if zh else _TARGET_EN)[target]
    if zh:
        understood = f'根据业务描述，我们暂时把问题理解为：{goal}。这只是待核对的问题定义。'
        disclosure = ('本报告没有估计实际销量、收入、利润、投资回报率，也不代表 Estimation/Policy 已经完成。'
                      '研究设计、假设和总体信息仍须由有权限的人员确认。')
    else:
        understood = f'We provisionally understand your goal as: {goal}. This interpretation still needs review.'
        disclosure = ('This report contains no estimated sales, profit, ROI, causal effect size, or policy recommendation. '
                      'Study design and assumptions still require appropriate review.')
    status = route.status
    stage, level = 'NEED_INFORMATION', route.verification_level
    if zh:
        title, answer = '还需要弄清业务问题', '目前还无法可靠判断这个问题是否可以从已有信息回答；先确认几个关键事实。'
        next_steps = ['补充关键业务事实，再让研究者核对数学问题。']
    else:
        title, answer = 'A few details are missing', 'We cannot yet say whether available information answers this question.'
        next_steps = ['Clarify the main business facts, then review the mathematical question.']

    if status == 'AWAITING_HUMAN_REVIEW':
        stage = 'WAIT_REVIEW'
        title = '业务问题已整理，等待确认' if zh else 'The business question is drafted; review needed'
        answer = ('系统已整理出一个初步的因果问题，但尚未判断它能否被识别。'
                  if zh else 'A draft causal question is ready, but its identifiability has not been assessed.')
        next_steps = ['请研究者确认目标、实验分配方式和所需假设。'] if zh else ['Confirm the goal, allocation design and assumptions.']
    elif status == 'NO_CORE_CONNECTED':
        stage = 'NO_CORE'
        title = '尚未连接数学识别库' if zh else 'The verified mathematics library is not connected'
        answer = ('即使业务已确认，当前还没有执行正式识别，不能据此说它可识别或不可识别。'
                  if zh else 'No formal identification has run; this is neither proof nor non-identification.')
        next_steps = ['未来接入正式 Identification Library 后重新检查。'] if zh else ['Connect the formal Identification Library.']
    elif status == 'CORE_VERIFIED':
        stage = 'VERIFIED_BY_CORE'
        claim = route.candidate_math_claim
        if claim == 'POINT':
            title = '在给定条件下，理论识别已通过验证' if zh else 'Identification verified under stated conditions'
            answer = ('严格识别库报告：在已审核的数学条件成立时，目标由指定的总体信息唯一决定。'
                      '这还不是具体的业务收益数字。' if zh else
                      'The core reports a uniquely identified target under the reviewed mathematical conditions. No business outcome has been estimated.')
        elif claim in ('NOT_POINT', 'NO_USEFUL_ID'):
            title = '严格识别库报告无法唯一确定目标' if zh else 'Core reports that the target is not uniquely identified'
            answer = ('这是一项针对当前信息和假设的数学判断，并非因为软件缺少代码。'
                      if zh else 'This concerns the reviewed information and assumptions, not a missing software route.')
        else:
            title = '严格识别库给出了经过重放的识别结论' if zh else 'The core returned a replay-checked result'
            answer = ('请查看数学细节确认识别集合及其适用条件，尚未得到数值。'
                      if zh else 'See mathematical details for the identified set and its scope; no value was estimated.')
        next_steps = ['另行检查是否有匹配的估计模型和可用样本，再考虑业务决策。'] if zh else ['Check estimator capability and observed data separately.']
    elif status == 'CORE_NEEDS_INPUT':
        stage = 'CORE_NEEDS_INFORMATION'
        title = '正式识别还缺少条件' if zh else 'The mathematical core needs more information'
        answer = ('现有定理需要补充研究信息或确认假设；不能让大模型自行假定这些条件成立。'
                  if zh else 'A missing condition requires review; an LLM must not assume it holds.')
        next_steps = ['请研究者核对严格库提出的缺失条件。'] if zh else ['Review the core\'s missing requirements.']
    elif status == 'CORE_UNSUPPORTED':
        stage = 'LIBRARY_GAP'
        title = '当前识别库暂时没有对应方法' if zh else 'Current library does not cover this question'
        answer = ('这表示软件还没有匹配的已验证定理，不表示数学上已经证明它不可识别。'
                  if zh else 'A missing theorem in software is not proof of non-identification.')
        next_steps = ['可以进一步开展大模型候选分析，再由数学人员审查。'] if zh else ['Consider an unverified model suggestion for expert review.']
    elif status == 'MOCK_CORE_RESULT':
        stage, level = 'MOCK_PREVIEW', 'MOCK_ONLY'
        title = '这是演示流程，不是真实识别结论' if zh else 'Simulation only—not an identification result'
        answer = ('当前使用模拟识别库，演示能说明程序如何分流，但不能证明任何业务因果结论。'
                  if zh else 'The mocked library demonstrates flow control, not causal identification.')
        next_steps = ['今后接入真实定理库后再判定。'] if zh else ['Connect a real theorem backend.']
    elif status in ('CORE_NO_ADAPTER', 'CORE_INCOMPATIBLE', 'CORE_ERROR',
                    'CORE_VERIFICATION_FAILED', 'CORE_BINDING_FAILED'):
        stage = 'TECHNICAL_BLOCK'
        title = '校验或接口出现问题，结果已被拦截' if zh else 'The result was blocked by a technical or verification check'
        answer = ('不能把这类程序错误解释为识别成功、不可识别，或让大模型跳过核验。'
                  if zh else 'A technical failure cannot be treated as an identified or non-identified target.')
        next_steps = ['请开发/研究团队检查版本、输入绑定及证书核验。'] if zh else ['Check the adapter, input binding and replay receipt.']

    if candidate is not None:
        if candidate.status in ('UNVERIFIED_CANDIDATE', 'UNDETERMINED_UNVERIFIED'):
            # Preserve simulated origin if this is a mocked core. Both cases stay unverified.
            if status != 'MOCK_CORE_RESULT':
                stage, level = ('UNVERIFIED_SUGGESTION' if candidate.status == 'UNVERIFIED_CANDIDATE'
                                else 'UNVERIFIED_UNDETERMINED'), 'LLM_UNVERIFIED'
            title = ('大模型提出了一个尚未核验的分析思路' if candidate.status == 'UNVERIFIED_CANDIDATE'
                     else '大模型也未能给出可靠结论') if zh else (
                         'An unverified AI suggestion is available' if candidate.status == 'UNVERIFIED_CANDIDATE'
                         else 'The AI did not reach a reliable conclusion')
            answer = (('现有严格库未给出此题的正式结果。大模型给出了一种候选分析，仍需核查公式、假设和证据，不能直接用来决定投放或测算收益。'
                       if candidate.status == 'UNVERIFIED_CANDIDATE' else
                       '当前没有经认证的结论；大模型也表示暂不能确定。') if zh else
                      ('The AI suggested an approach, but no theorem or proof has verified it. Do not use it for a rollout decision.'
                       if candidate.status == 'UNVERIFIED_CANDIDATE' else
                       'The AI also could not determine an answer; no conclusion is certified.'))
            if status == 'MOCK_CORE_RESULT':
                answer += ('另外，当前严格库只是模拟的。' if zh else ' The core is also simulated.')
            next_steps = (['数学审查候选推导；逐项确认新增条件确实成立。'] if zh
                          else ['Mathematically check the candidate and every added condition.'])
        elif candidate.status in ('REJECTED_UNSAFE_OUTPUT', 'PROVIDER_FAILED'):
            if status != 'MOCK_CORE_RESULT':
                stage, level = 'CANDIDATE_REJECTED', 'LLM_UNVERIFIED'
            title = '大模型的建议未通过检查' if zh else 'The model suggestion was rejected'
            answer = ('模型输出无效或没有通过安全检查；没有形成可用于决策的识别结果。'
                      if zh else 'The suggestion failed validation and cannot support a decision.')
            next_steps = ['保持原研究问题不变，检查错误后再尝试。'] if zh else ['Keep the original problem fixed and review the error.']

    questions = friendly_questions(run, language=case.response_language, max_questions=max_questions) if status == 'NEEDS_CLARIFICATION' else []
    if status == 'CORE_NEEDS_INPUT' and route.next_steps:
        # Core missing requirements may contain technical terms; send them only to scholars.
        questions = ['有一项定理前提仍需研究者确认。' if zh else 'A theorem requirement needs expert review.']

    details: list[str] = []
    if audience == Audience.SCHOLAR:
        d = form.draft
        details = [
            f'TargetKind: {d.target.kind.value}',
            f'Original candidate target description: {d.target.description.value or "UNRESOLVED"}',
            f'AssignmentFamily: {d.information_design.assignment_family.value}',
            f'A4 population level: {d.information_design.population_information_level.value}',
            f'A4 operator (draft only): {d.information_design.population_observable_operator.value or "UNRESOLVED"}',
            f'A5 draft proposals (not automatically admitted): {", ".join(x.name for x in d.assumptions) or "none"}',
            f'Routing status: {route.status}',
            f'Core status: {route.core_status or "none"}',
            f'Verification: {route.verification_level}',
            f'Formulation prompt version: {form.prompt_version}',
        ]
        if route.core_route:
            details.append(f'Core route: {route.core_route}')
        if route.core_expression:
            details.append(f'Core expression (read together with verification level): {route.core_expression}')
        if route.next_steps:
            details.extend(f'Core next requirement: {x[:800]}' for x in route.next_steps[:3])
        if candidate and candidate.candidate:
            c = candidate.candidate
            details.extend([
                f'Candidate claim / scope: {c.claimed_identification} / {c.scope}',
                f'Candidate source: {candidate.execution_mode}; LLM_UNVERIFIED',
                f'Candidate expression (NOT VERIFIED): {c.candidate_expression or "none"}',
            ])
            details.extend(f'Proposed additional requirement (not admitted): {x.description}' for x in c.additional_requirements[:3])
    if audience == Audience.INVESTOR:
        next_steps.append('即使理论上能够识别，仍要单独评估有限样本误差、成本与投资回报。' if zh
                          else 'Even if identified, uncertainty, deployment costs and ROI require separate estimation.')
    if target in (TargetKind.FIXED_POLICY_VALUE, TargetKind.POLICY_OPTIMIZATION, TargetKind.STOCHASTIC_POLICY_VALUE):
        if audience == Audience.SCHOLAR:
            details.append('Policy target caution: a design-standardized arm mean is not automatically full-assignment policy welfare.')
        else:
            next_steps.append('不能直接把个人层面的平均效果当成整个推广方案的真实收益。' if zh
                              else 'Individual average effects are not automatically true rollout value.')
    if audience == Audience.SCHOLAR:
        next_steps.append('检查目标 Q、总体信息 A4、已接受 A5 与有效域/支持 A6。' if zh
                          else 'Review Q, A4, admitted A5, and A6 validity/support.')

    return BusinessExplanationV05(
        case_id=case.case_id, input_sha256=fingerprint_business_case(case), audience=audience,
        response_language=case.response_language,
        candidate_verification_level="LLM_UNVERIFIED" if candidate is not None else "NONE",
        stage=stage, verification_level=level,
        title=title, summary=answer, understood_goal=understood,
        questions=questions, next_steps=next_steps[:5], academic_details=details[:22],
        disclosure=disclosure,
    )


def render_business_text(report: BusinessExplanationV05) -> str:
    zh = report.response_language == 'zh'
    lines = [report.title, '', report.summary, '', report.understood_goal]
    if report.questions:
        lines.append('\n' + ('接下来想确认：' if zh else 'Questions to clarify:'))
        lines.extend(f'{i}. {q}' for i, q in enumerate(report.questions, 1))
    if report.next_steps:
        lines.append('\n' + ('接下来怎么办：' if zh else 'Next steps:'))
        lines.extend(f'- {x}' for x in report.next_steps)
    lines.append('\n' + ('结果来源/认证级别：' if zh else 'Status / verification: ') +
                 f'{report.stage} / {report.verification_level}')
    if report.candidate_verification_level != 'NONE':
        lines.append(('大模型候选：' if zh else 'AI suggestion: ') + report.candidate_verification_level)
    lines.append(report.disclosure)
    if report.academic_details:
        lines.append('\n' + ('研究人员核查详情（不替代证明）：' if zh else 'Researcher details (not a proof):'))
        lines.extend(f'- {x}' for x in report.academic_details)
    return '\n'.join(lines)


def render_business_html(report: BusinessExplanationV05) -> str:
    """No JavaScript; escape ALL untrusted/LLM-derived text to prevent HTML injection."""
    e = lambda x: escape(str(x), quote=True)
    list_html = lambda items: '<ul>' + ''.join('<li>' + e(x) + '</li>' for x in items) + '</ul>' if items else ''
    is_zh = report.response_language == 'zh'
    qa = '想确认的问题' if is_zh else 'Questions to clarify'
    nx = '建议下一步' if is_zh else 'Suggested next steps'
    dt = '研究人员可展开查看的详细信息' if is_zh else 'Researcher details'
    details = (f'<details><summary>{e(dt)}</summary>{list_html(report.academic_details)}</details>'
               if report.academic_details else '')
    return f'''<!doctype html><html lang="{'zh-CN' if is_zh else 'en'}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(report.title)} — CFM-ID</title>
<style>body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#f7f8fa;color:#17202e;margin:0}}
main{{max-width:790px;margin:42px auto;padding:0 18px}}article{{background:white;border:1px solid #e1e6ee;border-radius:15px;padding:26px;box-shadow:0 5px 24px #17202e0b}}
h1{{font-size:1.55rem;margin:8px 0 18px}}h2{{font-size:1rem;margin:23px 0 10px}}p{{line-height:1.75}}li{{line-height:1.7;margin:7px 0}}
small,.sub{{color:#596473}}.pill{{border:1px solid #ccd4df;border-radius:100px;display:inline-block;font-size:.78rem;padding:5px 10px}}
footer{{padding:17px 0 0;font-size:.85rem;color:#596473;border-top:1px solid #e1e6ee;margin-top:24px}}
details{{border-top:1px solid #e1e6ee;padding:15px 0;margin-top:15px}}summary{{cursor:pointer}}
</style></head><body><main><article>
<div class="pill">{e(report.stage)} · {e(report.verification_level)}</div>
<h1>{e(report.title)}</h1><p>{e(report.summary)}</p><p class="sub">{e(report.understood_goal)}</p>
{f'<h2>{e(qa)}</h2>{list_html(report.questions)}' if report.questions else ''}
{f'<h2>{e(nx)}</h2>{list_html(report.next_steps)}' if report.next_steps else ''}
{details}<footer>{e(report.disclosure)}</footer>
</article></main></body></html>'''
