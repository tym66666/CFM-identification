"""Compact presentation never approves a run or conceals unsupported restrictions."""
from copy import deepcopy
import pytest
from demo.backend.engine import Run
from demo.backend.review_summary import summarize


def example():
    return Run(owner='fixture',query_id='q1',review_kind='source',
        queries=[dict(query_id='q1',business_goal={'value':'比较两种安排'},semantics={})],
        review_templates={'source':{'decisions':{'/target':dict(field_role='PENDING',value_state='PENDING',source_coverage='PENDING')}}},
        attachment_report={'factual_data':dict(nodes=120,observed=60,features=20)},
        submission={'candidate':dict(version='network-randomized-effect-reading-1',
            target=dict(first=dict(own=1,exposure=0),second=dict(own=0,exposure=0),population=['a','b'],aggregation='EQUAL_MEAN'),
            exposure={'kind':'STRICT_MAJORITY_TIES_LOW'},
            assignment={'kind':'INDEPENDENT_BERNOULLI','probabilities':{'a':'1/2','b':'1/2'}},
            scientific_statements={'consistency':{'status':'PROPOSED'}},
            information=[{'availability':'SYMBOLIC_POPULATION_OPERATOR'}],
            additional_restrictions=[],unresolved=[])})


def test_summary_is_three_cards_without_granting_review():
    run=example();before=deepcopy(run.review_templates)
    result=summarize(run)
    assert len(result['cards'])==3 and result['compact_confirmation_available']
    assert result['is_approval'] is False and run.review_templates==before
    assert '120' in result['cards'][2]['lines'][0] and '60' in result['cards'][2]['lines'][0]
    assert '拟采用' in str(result['cards'][1])
    assert run.result is None and run.reviews=={}


def test_actual_fact_endpoints_are_shown_instead_of_repeating_only_the_goal():
    run=example()
    run.submission['candidate']['target']['first']['own']=0
    assert '本人不接受处理' in summarize(run)['cards'][0]['lines'][0]


def test_additional_conditions_and_rejections_cannot_use_compact_approval():
    run=example();run.submission['candidate']['additional_restrictions']=['another restriction']
    assert not summarize(run)['compact_confirmation_available']
    run=example();run.plan={'rejected_fields':['/target']}
    assert not summarize(run)['compact_confirmation_available']


def test_unmapped_scientific_routes_require_full_review():
    run=example();run.review_kind='science';run.plan={'methods':[{'method':'NEW_ROUTE'}]}
    assert not summarize(run)['compact_confirmation_available']


def test_fixed_policy_summary_includes_actual_assignment_and_information_without_approval():
    run=example();run.review_kind='science';run.plan={'methods':[{'method':'R1B_FULL_ASSIGNMENT'}]}
    facts=run.submission['candidate'];facts['version']='network-source-selections-1'
    facts['target']=dict(kind='FIXED_POLICY_MEAN',assignment={'甲店':1,'乙店':0},population=['甲店','乙店'],aggregation='EQUAL_MEAN')
    facts['scientific_statements']={k:{'status':'ADOPTED'} for k in
        ('consistency','assignment_outcome_independence','finite_conditional_means')}
    facts['information'][0]['operator']='ALL_OUTCOMES_TOGETHER_WITH_FULL_ASSIGNMENT'
    before=deepcopy(run.submission);result=summarize(run)
    assert result['compact_confirmation_available'] and not result['is_approval']
    assert '甲店接受处理；乙店不接受处理'==result['cards'][0]['lines'][0]
    assert '联合总体分布' in str(result['cards'][2])
    assert run.submission==before and not run.reviews
    for status in ('NOT_STATED','UNDECIDED','NOT_ADOPTED','CONFLICTING'):
        facts['scientific_statements']['consistency']['status']=status
        assert not summarize(run)['compact_confirmation_available']
    facts['scientific_statements']['consistency']['status']='ADOPTED'
    run.plan['methods']=[{'method':'R2_MEAN_SIGNATURE'}]
    assert not summarize(run)['compact_confirmation_available']


def test_unstated_conditions_are_not_displayed_as_adopted():
    run=example();run.submission['candidate']['scientific_statements']['consistency']['status']='NOT_STATED'
    text=str(summarize(run)['cards'][1])
    assert '原文未声明' in text and '拟采用' not in text


def test_policy_difference_summary_preserves_both_ends_and_common_scope():
    run=example();run.review_kind='science';run.plan={'methods':[{'method':'R1B_ENDPOINT_DIFFERENCE'}]}
    facts=run.submission['candidate'];facts['version']='network-policy-contrast-reading-1'
    facts['target']=dict(kind='FIXED_POLICY_MEAN_DIFFERENCE',operation='FIRST_MINUS_SECOND',
        first=dict(assignment={'甲':1,'乙':1},population=['甲','乙'],aggregation='EQUAL_MEAN'),
        second=dict(assignment={'甲':0,'乙':0},population=['甲','乙'],aggregation='EQUAL_MEAN'),
        shared_outcome_and_context={'value':True})
    facts['scientific_statements']={k:{'status':'ADOPTED'} for k in
        ('consistency','assignment_outcome_independence','finite_conditional_means')}
    result=summarize(run)
    assert result['compact_confirmation_available'] and '减去第二方案' in str(result['cards'])
    assert '2 个评价对象 · 等权平均' in str(result['cards'])
    assert not run.reviews and not result['is_approval']
    for mutate in [lambda t:t.update(operation='UNKNOWN'),
                   lambda t:t['second'].update(population=['甲']),
                   lambda t:t['second'].update(aggregation='UNKNOWN'),
                   lambda t:t.update(shared_outcome_and_context={'value':False})]:
        before=deepcopy(facts['target']);mutate(facts['target'])
        assert not summarize(run)['compact_confirmation_available']
        facts['target']=before


def test_two_stage_condition_must_be_shown_and_explicit_before_confirmation():
    run=example();run.review_kind='science';run.plan={'methods':[{'method':'R1A_COMPOSITION'}]}
    f=run.submission['candidate'];f['assignment']={'kind':'TWO_STAGE_QUOTA_MIXTURE'}
    f['scientific_statements']={k:{'status':'PROPOSED'} for k in
        ('consistency','assignment_outcome_independence','finite_conditional_means')}
    assert not summarize(run)['compact_confirmation_available']
    for status in ('ADOPTED','PROPOSED','UNDECIDED','NOT_ADOPTED','CONFLICTING'):
        f['first_stage_exclusion']={'status':status}
        r=summarize(run)
        assert r['compact_confirmation_available']==(status in ('ADOPTED','PROPOSED'))
        assert '名额方案本身不再直接影响结果' in str(r['cards'])

@pytest.mark.parametrize('status,allowed,label',[
    ('ADOPTED',True,'原文明确采用'),('PROPOSED',True,'本次拟采用'),
    ('UNDECIDED',False,'尚未决定'),('NOT_ADOPTED',False,'不采用'),
    ('NOT_STATED',False,'原文未声明'),('CONFLICTING',False,'材料存在冲突'),
])
def test_scientific_attitudes_displayed_without_granting_approval(status,allowed,label):
    run=example();run.review_kind='science';run.plan={'methods':[{'method':'R1A_COMPOSITION'}]}
    run.submission['candidate']['scientific_statements']={k:{'status':status} for k in
        ('consistency','assignment_outcome_independence','finite_conditional_means')}
    before=deepcopy(run.submission);result=summarize(run)
    assert result['compact_confirmation_available'] is allowed
    assert label in str(result['cards'][1]) and not result['is_approval']
    assert run.submission==before and not run.reviews
