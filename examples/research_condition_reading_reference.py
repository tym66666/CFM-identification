"""Frozen synthetic reading checks before any condition-version approval.

Only public bundles go to models. This source-tree harness stipulates synthetic
science separately, checks the full actual reading, and never repairs replies.
It is not an automatic real-world scientific reviewer.
"""
from copy import deepcopy
from cfm_id import research_session as work, research_versions as versions, session_routes as routes
from cfm_id.source_locations import build_catalog
from cfm_id.question_bound_assignment import question_catalog
from cfm_id_bridge.scientific_binding import sha
from evaluation import mean_order_factored_reading as reading, mean_order_factored_review as review
from evaluation.equal_weight_comparison_semantics import equivalent_target
from examples.mean_order_business_fixture import make_case, endpoint_reviews, business_review
from examples.mean_order_workflow_fixture import export_fixture, _load
from examples.research_item_review_reference import approve_items


def cases():
    """Author references before dispatch; one unchanged question, four versions."""
    own='针对A、B、C、D，我们这次拟采用一条条件：其他小组怎么用都不变时，只让本组从不用改成用系统，本组在同一研究背景下的平均完成率不会下降。这条条件包括试点没出现过的所有安排，但目前还没有审核批准。'
    peers='针对A、B、C、D，我们另拟采用一条条件：本组和其他小组的用法不变时，只让一位合作邻居从不用改成用系统，本组在同一研究背景下的平均完成率不会下降。这也包括试点没出现过的所有安排，仍需单独审核。'
    no_own='针对A、B、C、D，这个版本明确不假设本组自己使用系统就不会降低本组平均完成率。'
    no_peers='针对A、B、C、D，这个版本明确不假设增加一位使用系统的合作邻居就不会降低本组平均完成率。'
    pending='针对A、B、C、D，关于同伴影响，我们还没有决定要不要采用以下条件：本组和其他小组的用法不变时，只让一位合作邻居从不用改成用系统，本组在同一研究背景下的平均完成率不会下降。讨论的范围包括试点没出现过的所有安排；目前既没有决定采用，也没有决定放弃。'
    result=[]
    for name,mode,lines,interval in [
        ('both','BOTH',[own,peers],['1/5','1']),
        ('own_only','OWN',[own,no_peers],['-1/5','1']),
        ('no_orders','NONE',[no_own,no_peers],['-1','1']),
        ('peer_undecided','BOTH',[own,pending],None),
    ]:
        case=make_case(mode=mode)
        b=case['bundle']
        b['documents']['conditions.txt']='以下是这次研究拟采用的条件说明，不是对试点结果的总结。\n'+'\n'.join(lines)
        # Only independently authored references are rebound here. Actual model
        # replies never pass through this construction or any field replacement.
        canonical=deepcopy(case['expected_candidate'])
        canonical['comparison']['reading']['intents']['q1']['question_id']=question_catalog(b)['q1']['question_id']
        catalog=build_catalog(b['documents'])
        for row,line in zip(canonical['order_reading']['claims'],lines):
            row['source_ids']=[k for k,v in catalog.items() if v['doc_id']=='conditions.txt' and v['text'].strip()==line]
            assert len(row['source_ids'])==1
        wire=reading.reference_wire(b,canonical)
        if name=='peer_undecided':
            wire['order_reading']['claims'][1]['declaration']='尚不明确'
            canonical=reading.to_canonical(b,wire)
        case['candidate']=deepcopy(canonical)
        case['expected_candidate']=deepcopy(canonical)
        fixture=export_fixture(case,references=[wire],provenance='Independent hypothetical conditions frozen before any response; not real-world scientific approval.')
        result.append(dict(name=name,bundle=deepcopy(b),fixture=fixture,reference=wire,
                           expected_state='PARTIAL' if interval else 'NEEDS_INPUT',expected_interval=interval))
    return result


def score_reading(bundle, wire, fixture):
    """Separate reference comparison; never calls a solver or grants approval."""
    scores=[]
    for ref in fixture['references']:
        fields=reading.wire_metrics(bundle,wire,ref)
        try:
            actual=reading.to_canonical(bundle,wire)
            expected=reading.to_canonical(bundle,ref)
            a=actual['comparison']['reported_assignment']
            e=expected['comparison']['reported_assignment']
            target=equivalent_target(bundle,actual['comparison'],expected['comparison'])
            assignment=all(a.get(k)==v for k,v in e.items() if k!='source_ids') and set(e['source_ids'])<=set(a['source_ids'])
        except (ValueError,TypeError,KeyError,AttributeError):
            target=assignment=False
        scores.append(dict(order=fields,target=target,assignment=assignment,
                           passed=fields['passed'] and target and assignment))
    return dict(passed=any(r['passed'] for r in scores),scores=scores,
                automatic_real_world_semantic_verification=False)


def prepare_session(case, wire, *, parent=None):
    """Return actual session plus ephemeral native context only after reference admission."""
    original=sha(wire)
    b=case['bundle']; frozen=_load(b,case['fixture'])
    s=(work.start(routes.MEAN_ORDER,b) if parent is None else
       versions.fork_version(parent,label=case['name'],reason='Independently read current hypothetical conditions.',bundle=b))
    s=work.receive_candidate(s,wire)
    score=score_reading(b,wire,case['fixture'])
    native=None
    # Admission depends on complete reviewed semantics, never the expected answer
    # label. A degenerate sharp interval can be POINT under the same contract.
    if score['passed'] and work.inspect(s)['state']=='REVIEW_REQUIRED':
        canonical=reading.to_canonical(b,wire)
        chain=endpoint_reviews(frozen,canonical)
        legacy=business_review(frozen,canonical,chain)
        full=review.ReviewedFactoredReading(**review.worksheet(b,wire,legacy_review=legacy),
            reviewer='Independent frozen synthetic condition reviewer',evidence=case['fixture']['provenance'],
            reviewed_full_wire_semantics_and_sources=True,reviewed_projection_and_losses=True,synthetic_fixture=True)
        chain.pop('synthetic_protocol_selected')
        native=dict(chain,science=frozen['science'],review=legacy,factored_review=full)
        s=approve_items(work.begin_item_review(s,native_submission=native))
    assert sha(wire)==original and s.candidate==wire
    return s,native,score


def assess(case, wire):
    s,native,score=prepare_session(case,wire)
    no_review=work.execute(work.receive_candidate(s,wire),native_submission=native,research_protocol_selected=True)
    assert not no_review['backend_called'] and no_review['mathematical_claim'] is None
    result=work.execute(s,native_submission=native,research_protocol_selected=True)
    claim=result['mathematical_claim']
    expected=case['expected_interval']
    proved=(result['independent_replay'] and claim['interval']==expected and claim['sharp']) if expected else (
        not result['backend_called'] and claim is None and s.review is None)
    return dict(passed=score['passed'] and result['state']==case['expected_state'] and bool(proved),
        semantic_passed=score['passed'],final_state=result['state'],expected_state=case['expected_state'],
        score=score,result=result,clarification=work.clarification_plan(s),
        no_review_blocked=True,actual_reply_preserved=s.candidate==wire,synthetic_only=True)
