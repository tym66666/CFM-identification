"""Source-based interpretation of a fixed evaluation roster; never admission."""

RULE = (
    '本字段核对评价对象的选择规则是否在处理前已确定，不是询问用户何时提出问题。'
    '原文明确评价处理前研究名册的全体，或按已确定的处理前规则选择子集，且不随本轮实际处理或结果改变时，'
    '可据这些材料记录true；用户在试点结束后提出同一固定总体问题，不因此记为未知。'
    '必须同时有评价范围和名册/选择规则的处理前依据，单独存在名单、名单等于study.nodes、'
    '随机抽签或网络固定，都不足以证明这个字段。若按本轮实际中签、启用、回访结果或表现筛选评价对象，'
    '记录false；选择依据不明则为null，材料冲突另记unresolved。回访记录的覆盖名单不替代评价名单。'
    'source_ids引用支持判断的原文；这是待审核的读取声明，不是科学批准。')

QUESTION = ('本次评价的是处理前研究名单中的全体／事先确定的小组，'
            '还是按本轮实际启用、回访或结果筛选出的对象？请说明选择依据；不需要提供提出问题的日期。')

def field_constraints(paths):
    path='/target/population_fixed_before_assignment'
    return [dict(field_path=path,description=RULE)] if any(
        p=='' or p==path or p.startswith(path+'/') or path.startswith(p+'/') for p in paths) else []
