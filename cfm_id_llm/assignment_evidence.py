"""Conservative wording checks for a proposed COMPLETE_RANDOMIZATION label.

This checks source declarations, not truth, uniformity, numeric support, or A4/A5
admission. Ambiguous wording stays open for review. It never constructs a law.
"""
from __future__ import annotations

import re
import unicodedata

from .schemas import BusinessCase, SemanticClaim

# A cardinal must be the object of a selection/allocation expression. A number
# elsewhere in a document (sample size, budget, realized count) is insufficient.
_NUMBER = r"(?:[0-9]+|[零一二两三四五六七八九十百千万]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty)"
_UNIT = r"(?:个(?:人|窗口|站点|单位)?|名|人|家|店|组|位|所|间|条|座|站|池|支|个团队)"
_COUNT = rf"(?P<count>{_NUMBER})\s*{_UNIT}"
_SELECT = r"(?:抽取|抽出|抽选|抽中|选取|选出|选定|选择|挑选|抽|选)"
_RANDOM = re.compile(r"随机|均匀|等概率|抽签|抓阄|random(?:ly|ization|isation)?|uniformly|lotter", re.I)
_RELEVANT = re.compile(
    r"随机|抽|选|名额|配额|分配|处理(?:总)?人数|启用人数|使用人数|名单|组合|"
    r"random|select|draw|assign|quota|treated|lotter|subsets?", re.I)
_NAMED = re.compile(r"完全随机化|complete randomi[sz]ation", re.I)
_FIXED = re.compile(
    r"固定\s*(?:的\s*)?(?:处理\s*)?(?:总人数|总数|人数|数量|名额|配额)|"
    r"固定\s*(?:的\s*)?处理名额|定额|fixed\s+(?:treatment\s+)?(?:quota|number|size)", re.I)
_SELECTION_COUNT = re.compile(
    rf"{_SELECT}\s*(?:了|其中|其中的)?\s*(?:恰好|正好|固定)?\s*{_COUNT}", re.I)
_ALLOCATION_COUNT = re.compile(
    rf"(?:给|向)\s*(?:恰好|正好)?\s*{_COUNT}.{{0,12}}(?:分配|启用|开通|使用)|"
    rf"(?:名额|配额|处理人数)\s*(?:固定)?\s*(?:为|是|:)\s*{_NUMBER}\s*(?:{_UNIT})?", re.I)
_EN_SELECTION = re.compile(
    rf"\b(?:select|choose|draw|assign)(?:s|ed|ing)?\s+(?:(?:exactly|a fixed number of)\s+)?"
    rf"{_NUMBER}\s+(?:distinct\s+)?(?:units?|people|employees?|stores?|sites?|teams?|participants?|windows?)\b", re.I)
_EN_PASSIVE = re.compile(
    rf"\bexactly\s+{_NUMBER}\s+(?:of\s+(?:the\s+)?{_NUMBER}\s+)?"
    r"(?:people|salespeople|employees|units|stores|sites|teams|participants)\s+"
    r"(?:were|are)\s+(?:(?:randomly|uniformly)\s+)?(?:selected|chosen|assigned|drawn)\b", re.I)
_EQUAL_LISTS = re.compile(
    rf"(?<![0-9./])(?P<list_count>{_NUMBER})\s*{_UNIT}\s*(?:(?:组成|构成)的\s*)?"
    rf"(?:名单|组合|配置).{{0,12}}(?:等概率|机会相同|概率相同)|"
    rf"(?:every|all)\s+{_NUMBER}[- ](?:unit|person|store|site|team)\s+(?:lists?|subsets?|assignments?).{{0,25}}(?:equally likely|equal probability)", re.I)

# Scope these modifiers to the number/design clause, rather than banning e.g.
# "工具效果可能不同" elsewhere in the same source.
_NONEXACT = re.compile(
    rf"(?:最多|至少|至多|不少于|不超过|不多于|不低于|大约|大概|约|平均|预期).{{0,16}}{_NUMBER}|"
    rf"{_NUMBER}\s*{_UNIT}\s*(?:左右|上下|以上|以下|以内|以外)|"
    rf"{_NUMBER}\s*{_UNIT}\s*(?:为|作为|是)?(?:上限|下限|最大值|最小值)|"
    rf"{_NUMBER}\s*(?:{_UNIT})?\s*(?:到|至|或|或者|[-~～–])\s*{_NUMBER}|"
    r"\b(?:at most|at least|up to|no more than|not exactly|about|around|approximately|on average|expected)\b", re.I)
_UNSET = re.compile(
    r"尚未|还未|未决定|未确定|待定|暂未|未说明|没有说明|不确定|"
    r"可能|也许|拟|考虑|建议|设想|假设|如果|假如|若|是否|能否|"
    r"尚不|未必|不一定|\?|\b(?:if|suppose|perhaps|might|may|consider|undecided|not yet|whether|hypothetical)\b", re.I)
_NEGATED = re.compile(
    r"(?:不是|并非|没有|不设|未设|不采用|不实行|不属于|非)(?:按|任何|所谓|一个)?\s*(?:固定|定额|完全随机)|"
    r"(?:名额|配额|人数|数量|总数).{0,6}(?:不固定|未固定|不确定|可变|变化)|"
    r"\b(?:not|no|without)\s+(?:(?:a|any|using)\s+)?(?:fixed|complete random|quota)", re.I)
_NEGATED_ACTION = re.compile(
    r"(?:不是|并非|(?:不|未|没有|并不|并未)(?:采取|采用|要求|实行|执行|进行|按|会|曾)|从不|并未|不曾).{0,18}(?:随机|抽|选|分配)|"
    r"(?:不|未|没有)\s*(?:随机|均匀)?\s*(?:抽|选|分配)|"
    r"\b(?:do(?:es)? not|don't|doesn't|never|not)\s+(?:\w+\s+){0,3}(?:randomly|select|choose|draw|assign)\b", re.I)
_PROPOSED_TARGET = re.compile(
    r"(?:想|希望).{0,6}(?:知道|评估|了解|比较).{0,30}(?:随机|抽|选|政策)|"
    r"\b(?:want to know|want to evaluate|would like to assess)\b", re.I)
_ILLUSTRATIVE = re.compile(r"举例|例如|示例|仅供|另一个实验|当前.{0,10}另有安排|\b(?:example|illustration)\b", re.I)
_REALIZED = re.compile(
    r"观察到|记录显示|统计显示|数据显示|最终|最后|碰巧|恰巧|实际有|中签结果|"
    r"结果(?:是|有|恰好|正好|显示)|实际(?:中签|入选|启用|使用|抽中)|"
    r"\b(?:observed|realized|turned out|happened to|ended up|records show)\b", re.I)
_OTHER_MECHANISM = re.compile(
    r"(?:每个|各个|每|各)(?:片区|层|组|区域|分组).{0,12}(?:分别|各自|抽|选|名额)|"
    r"分层|分组.{0,8}(?:抽|选)|(?<!不)(?<!无)放回|"
    r"按.{0,8}(?:规模|权重).{0,10}(?:抽|选|分配)|加权.{0,6}(?:抽|选)|不等概率|"
    r"按.{0,8}(?:规模|权重).{0,10}加权.{0,8}名单|"
    r"(?:名单|组合).{0,12}(?:概率|机会).{0,4}(?:不同|不等)|"
    r"\b(?:stratif|within each|in each group|with replacement|unequal probability|weighted sampling)", re.I)
_INDEPENDENT = re.compile(
    r"(?:每人|每个|逐人|逐个|各自|各人).{0,12}独立|独立.{0,12}(?:抽签|抛硬币|伯努利)|"
    r"\b(?:independently|independent bernoulli|independent coin)\b", re.I)
_SENTENCE_BREAK = re.compile(r"[。！？!?\n]|\.(?:\s|$)")
_CLAUSE_BREAK = re.compile(r"[，,；;]")
_COUNT_USAGE = re.compile(rf"(?:启用|开通|使用|用)\s*{_NUMBER}\s*{_UNIT}", re.I)
# A declared untreated remainder is compatible with a fixed treated count.
# Remove only its negated treatment verb for the negated-design check; later
# modifiers/contradictions in that clause must still be screened normally.
_UNTREATED_REMAINDER = re.compile(
    rf"^((?:其余|剩余|剩下)(?:的)?(?:{_NUMBER}\s*{_UNIT})?"
    r"(?:员工|人员|参与者|门店|站点|窗口|单位|人)?\s*(?:均|都)?)"
    r"(?:不|未|没有)(?:被)?(?:分配|给予|接受|启用|开通|使用)")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def _sentence_state(text: str) -> bool | None:
    """True: affirmative design declaration; False: conflicting/ambiguous."""
    text = _normalize(text)
    clauses = [s.strip() for s in _CLAUSE_BREAK.split(text) if s.strip()]
    relevant = [s for s in clauses if _RELEVANT.search(s) or _COUNT_USAGE.search(s)]
    if not relevant:
        return None
    # A leading "if/undecided" can qualify a later comma-separated design.
    if _UNSET.search(clauses[0]) and not re.search(r"结果|效果|收益|outcome|effect", clauses[0]):
        return False
    # A reporting prefix before a comma must not turn a realized list into
    # an affirmative design declaration in the following clause.
    if _REALIZED.search(clauses[0]) and not re.search(r"结果|效果|收益|完成率|outcome|effect", clauses[0]):
        return False
    for clause in relevant:
        if any(p.search(clause) for p in (_NONEXACT, _UNSET, _NEGATED, _REALIZED, _OTHER_MECHANISM, _PROPOSED_TARGET, _ILLUSTRATIVE)):
            return False
        # A contrast explicitly denying independent coins is not evidence *for*
        # independent coins, and may accompany a valid fixed-size declaration.
        independent_text = re.sub(
            r"(?:不是|并非|不)(?:逐人|每人|相互|彼此)?独立(?:抽签)?|not independently",
            "", clause)
        action_text = _UNTREATED_REMAINDER.sub(r"\1", independent_text, count=1)
        if _INDEPENDENT.search(independent_text) or _NEGATED_ACTION.search(action_text):
            return False
    # Clauses within one original sentence may jointly state the count and draw
    # (e.g. '人数为四人，随机抽签决定名单'). Never combine separate sentences.
    random_in_sentence = any(_RANDOM.search(s) for s in relevant)
    for clause in relevant:
        if _NAMED.search(clause):
            return True
        equal_lists = _EQUAL_LISTS.search(clause)
        equal_declared = bool(equal_lists)
        if equal_lists:
            cardinal = equal_lists.group('list_count')
            # A composition phrase does not make a colloquial range exact.
            if cardinal and len(cardinal) > 1 and re.fullmatch(r"[一二两三四五六七八九]+", cardinal):
                equal_declared = False
        if not random_in_sentence and not equal_declared:
            continue
        if _FIXED.search(clause) or equal_declared or _EN_SELECTION.search(clause) or _EN_PASSIVE.search(clause):
            return True
        selected = _SELECTION_COUNT.search(clause)
        if selected:
            cardinal = selected.group("count")
            # 三四家 is an approximate range, unlike 十四家 or 150人.
            if len(cardinal) > 1 and re.fullmatch(r"[一二两三四五六七八九]+", cardinal):
                continue
            return True
        if _ALLOCATION_COUNT.search(clause):
            return True
    return None


def _context_state(text: str) -> bool | None:
    ends = [m.end() for m in _SENTENCE_BREAK.finditer(text)]
    ends.append(len(text))
    start = 0
    states = []
    for end in ends:
        if end > start:
            states.append(_sentence_state(text[start:end]))
        start = end
    if False in states:
        return False
    return True if True in states else None


def _quote_contexts(source: str, quote: str) -> list[str]:
    """Retain negation/modality outside the quoted substring at every occurrence."""
    boundaries = list(_SENTENCE_BREAK.finditer(source))
    contexts = []
    start = source.find(quote)
    while start >= 0:
        end = start + len(quote)
        left = max((m.end() for m in boundaries if m.end() <= start), default=0)
        right = next((m.end() for m in boundaries if m.end() >= end), len(source))
        contexts.append(source[left:right])
        start = source.find(quote, start + 1)
    return list(dict.fromkeys(contexts))


def has_fixed_quota_declaration(case: BusinessCase, claim: SemanticClaim) -> bool:
    """Evidence screening only; does not approve or modify a proposed family.

    An ambiguous repeated quote cannot select its preferred occurrence. Evidence
    snippets are never concatenated into a new sentence or inferred design.
    """
    sources = case.source_map()
    supported = False
    for evidence in claim.evidence:
        contexts = _quote_contexts(sources.get(evidence.source_id, ""), evidence.quote)
        if not contexts:
            return False
        states = [_context_state(s) for s in contexts]
        if False in states or (True in states and None in states):
            return False
        supported |= True in states
    return supported

