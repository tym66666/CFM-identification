"""Source-bound review checklists and append-only decisions; no scientific grants.

Items are regenerated from native declarations on every boundary. A hash is a
content/staleness check, not reviewer authentication or revocation of old copies.
"""
from copy import deepcopy
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from cfm_id_bridge.scientific_binding import sha
from . import session_routes as routes
from . import session_policy_routes as policies

Decision = Literal['PENDING', 'ACCEPTED', 'REJECTED', 'WITHDRAWN']
Group = Literal['business_target_and_sources', 'population_information', 'scientific_assumptions']


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class ReviewItem(Record):
    item_id: str
    group: Group
    category: Literal['A1_A3', 'A4', 'A5', 'REVIEW_SCOPE']
    title: str
    declaration: dict
    supporting_material: dict


class ReviewEvent(Record):
    sequence: int = Field(ge=1)
    previous_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    item_id: str
    previous_decision: Decision
    decision: Decision
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)


class ItemReview(Record):
    version: Literal['research-item-review-1'] = 'research-item-review-1'
    book_id: str = Field(pattern=r'^[0-9a-f-]{36}$')
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    native_snapshot: dict
    items: list[ReviewItem]
    events: list[ReviewEvent] = Field(default_factory=list)


class ItemDecision(Record):
    expected_review_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    item_id: str
    decision: Decision
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)


def _pick(value, *keys):
    return {k: deepcopy(value[k]) for k in keys}


def checklist(lane, bundle, candidate, snapshot):
    """Review native meanings only. Never interpret business text into approvals."""
    routes.require_lane(lane)
    if set(snapshot) != {'lane', 'native_submission'} or snapshot['lane'] != lane:
        raise ValueError('ITEM_REVIEW_NATIVE_LANE_MISMATCH')
    native = snapshot['native_submission']
    expected = (policies.fields(lane) if lane in policies.LANES else
                {'packet', 'context', 'submission_review'} if lane == routes.NETWORK else
                {'packet', 'context', 'science', 'assignment_review', 'review', 'factored_review'}
                if lane == routes.MEAN_ORDER else {'reading_review', 'science_review'})
    if set(native) != expected:
        raise ValueError('ITEM_REVIEW_EXACT_NATIVE_FIELDS_REQUIRED')
    view = routes.inspect(lane, bundle, candidate)
    if view['state'] != 'REVIEW_REQUIRED':
        raise ValueError('CANDIDATE_NOT_READY_FOR_ITEM_REVIEW')
    rows = []

    def add(key, category, title, declaration, material=None):
        group = {'A1_A3': 'business_target_and_sources', 'A4': 'population_information',
                 'A5': 'scientific_assumptions', 'REVIEW_SCOPE': 'scientific_assumptions'}[category]
        data = dict(group=group, category=category, title=title,
                    declaration=deepcopy(declaration), supporting_material=deepcopy(material or {}))
        rows.append(ReviewItem(item_id=key + ':' + sha(data)[:20], **data))

    if lane in policies.LANES:
        policies.review_rows(lane,bundle,view,native,add)
    elif lane == routes.NETWORK:
        names = {
            'consistency': '一致性：观测结果对应实际分配下的潜在结果',
            'finite_conditional_first_moments': '条件一阶矩存在且有限',
            'fixed_pretreatment_network': '网络固定且在处理前确定',
            'full_vector_randomization': '整个分配向量的随机化条件',
            'known_assignment_law': '已知共同分配律',
        }
        bindings = native['context']['bindings']
        if not bindings:
            raise ValueError('NATIVE_QUERY_BINDINGS_REQUIRED')
        add('structure', 'A1_A3', '网络、处理、分配概率与同伴暴露定义',
            dict(study=native['packet']['study'], structure=bundle['structure']),
            dict(tables=bundle.get('tables', {}), science_packet=native['packet']))
        for qid, bound in sorted(bindings.items()):
            add(qid + '/target', 'A1_A3', qid + '：比较目标、评价人群与来源',
                dict(target=bound['target'], business_intent=bound['business_intent']),
                dict(question=bundle['question_slots'][qid], admission=bound['admission']))
            if not bound['sources'] or not bound['licenses']:
                raise ValueError('NATIVE_A4_A5_ITEMS_REQUIRED')
            for index, source in enumerate(bound['sources']):
                add(f'{qid}/source/{index}', 'A4', qid + '：总体信息算子 ' + source['operator'],
                    source, dict(evidence_manifest=bound['evidence_manifest'],
                                 study_scope=bound['target']['study_scope']))
            for index, license in enumerate(bound['licenses']):
                add(f'{qid}/license/{index}', 'A5', qid + '：' + names.get(license['name'], license['name']),
                    license, dict(evidence_manifest=bound['evidence_manifest'],
                                  admission=bound['admission'], study=native['packet']['study']))
        add('native_review_scope', 'REVIEW_SCOPE', '原生审核链与合成研究范围',
            dict(scope='EXISTING_SYNTHETIC_NETWORK_CONTRACT'),
            dict(submission_review=native['submission_review'],
                 review=native['context']['review'], approval=native['context']['approval']))
    elif lane == routes.MEAN_ORDER:
        from .workflows.mean_order import inspect_candidate
        expanded = inspect_candidate(bundle, candidate, science=native['science'])
        if expanded['state'] != 'REVIEW_REQUIRED' or any(
                row.get('base_core_called') or row.get('bounded_backend_called') for row in expanded['stages']):
            raise ValueError('UNAPPROVED_MEAN_ORDER_MODEL_REQUIRED')
        model = expanded['result']['proposed_model']
        if type(model) is not dict:
            raise ValueError('NATIVE_MEAN_ORDER_MODEL_REQUIRED')
        add('target', 'A1_A3', '比较方向、评价对象与权重',
            _pick(model, 'node_order', 'first', 'second', 'weights', 'operation', 'context',
                  'treatment_definition', 'outcome_definition', 'outcome_unit', 'outcome_period'),
            dict(questions=bundle['question_slots']))
        add('structure', 'A1_A3', '网络、固定名额与同伴暴露的具体定义',
            _pick(model, 'node_order', 'undirected_edges', 'graph_scope', 'design', 'quota', 'exposure'),
            dict(assignment_review=native['assignment_review']))
        add('information_scope', 'A4', '全部可用总体信息的范围与来源；无未列入约束',
            _pick(model, 'information_scope', 'availability', 'a4_source', 'a4_provenance', 'model_scope'),
            dict(review=native['review']))
        for index, value in enumerate(model['values']):
            add(f'population_mean/{index}', 'A4', str(value['node']) + '：已声明的总体均值单元',
                value, _pick(model, 'a4_source', 'a4_provenance', 'context'))
        for key, title in (
                ('randomization_claim', '整个分配向量的随机化条件'),
                ('consistency_claim', '一致性'), ('moments_claim', '有限一阶矩'),
                ('mean_sufficiency_claim', '均值充分性：不能由暴露定义自动推出')):
            add(key, 'A5', title,
                _pick(model, key, 'context', 'mean_sufficiency_scope'),
                _pick(model, 'scientific_provenance'))
        for index, bound in enumerate(model['bounds']):
            add(f'bounds/{index}', 'A5', str(bound['node']) + '：结果界限及其适用层次',
                dict(bound=bound, **_pick(model, 'bounds_kind', 'bounds_scope', 'context',
                                       'outcome_definition', 'outcome_unit', 'outcome_period')),
                _pick(model, 'bounds_provenance'))
        for index, order in enumerate(model['node_orders']):
            # NONE is an explicit absence, never converted to monotonicity.
            for axis, label in (('OWN', '自身'), ('PEERS', '同伴')):
                add(f'order/{index}/{axis}', 'A5', str(order['node']) + '：' + label + '处理的均值顺序声明',
                    dict(order=order, axis=axis, restriction_present=order['mode'] in (axis, 'BOTH'),
                         **_pick(model, 'order_direction', 'order_scope', 'context', 'outcome_definition')),
                    dict(condition_rows=expanded['review_worksheet']['condition_rows']))
        add('native_review_scope', 'REVIEW_SCOPE', '原生双端点审核、完整候选审核与合成研究范围',
            dict(scope='EXISTING_SYNTHETIC_MEAN_ORDER_CONTRACT'),
            _pick(native, 'review', 'factored_review'))
    else:
        problem, wire = view['proposed_problem'], view['wire_candidate']
        catalog = view['source_catalog']

        def evidence(value):
            return dict(sources=[catalog[key] for key in value.get('source_ids', [])])

        add('target', 'A1_A3', '干预目标、变量角色与拟检验方法',
            dict(target=wire['target'], variables=wire['variables'],
                 adjustment=wire.get('adjustment'), frontdoor_choice=wire.get('frontdoor_choice')),
            dict(source_catalog=catalog, reading_review=native['reading_review']))
        add('population_law', 'A4', '观测变量的完整联合总体分布及来源',
            _pick(problem['information'], 'variables', 'availability', 'source_id', 'source_sha256', 'provenance'),
            evidence(wire['information']))
        add('positivity', 'A4', '总体联合分布严格正性的声明（适用域条件）',
            dict(strictly_positive_joint=problem['information']['strictly_positive_joint'],
                 variables=problem['information']['variables']), evidence(wire['information']['positivity']))
        labels = {'static_acyclic': '固定、无反馈的有向无环模型',
                  'graph_complete': '所列因果边的完整性', 'latent_causes_accounted': '共同原因均已显式纳入模型',
                  'independent_errors': '结构方程外生误差相互独立', 'perfect_intervention': '理想干预与其余机制不变'}
        for key, title in labels.items():
            add(key, 'A5', title, dict(clause=wire['scope'][key],
                **_pick(problem, 'model', 'variable_domain', 'nodes', 'observed', 'latent', 'edges', 'context')),
                evidence(wire['scope'][key]))
        add('native_review_scope', 'REVIEW_SCOPE', '原生科学审核及额外限制的完整性',
            _pick(problem, 'additional_restrictions'), _pick(native, 'reading_review', 'science_review'))
    if not rows or len({r.item_id for r in rows}) != len(rows):
        raise ValueError('NONEMPTY_UNIQUE_REVIEW_ITEMS_REQUIRED')
    return rows


def plan_digest(book):
    return sha(book.model_dump(exclude={'events'}))


def decisions(book):
    """Validate the ordered journal and derive decisions; no cached approval flags."""
    current = {row.item_id: 'PENDING' for row in book.items}
    previous = plan_digest(book)
    for index, event in enumerate(book.events, 1):
        if (event.sequence != index or event.previous_sha256 != previous or
                event.item_id not in current or event.previous_decision != current[event.item_id] or
                len(event.reviewer.strip()) < 3 or len(event.evidence.strip()) < 12):
            raise ValueError('ITEM_REVIEW_JOURNAL_INVALID')
        current[event.item_id] = event.decision
        previous = sha(event)
    return current


def checked(book, *, lane, bundle, candidate, binding):
    book = ItemReview.model_validate(deepcopy(book.model_dump()))
    if book.binding_sha256 != binding:
        raise ValueError('STALE_ITEM_REVIEW')
    if sha(book.items) != sha(checklist(lane, bundle, candidate, book.native_snapshot)):
        raise ValueError('ITEM_REVIEW_CHECKLIST_CHANGED')
    decisions(book)
    return book


def open_book(*, lane, bundle, candidate, binding, native_snapshot):
    return ItemReview(book_id=str(uuid4()), binding_sha256=binding,
                      native_snapshot=deepcopy(native_snapshot),
                      items=checklist(lane, bundle, candidate, native_snapshot))


def decide(book, change):
    change = ItemDecision.model_validate(deepcopy(change.model_dump() if type(change) is ItemDecision else change))
    if change.expected_review_sha256 != sha(book):
        raise ValueError('STALE_ITEM_REVIEW_EDIT')
    current = decisions(book)
    if change.item_id not in current:
        raise ValueError('UNKNOWN_REVIEW_ITEM')
    event = ReviewEvent(sequence=len(book.events) + 1,
        previous_sha256=sha(book.events[-1]) if book.events else plan_digest(book),
        previous_decision=current[change.item_id],
        **change.model_dump(exclude={'expected_review_sha256'}))
    updated = book.model_copy(update={'events': [*book.events, event]})
    decisions(updated)
    return updated


def worksheet(book):
    current = decisions(book)
    return dict(review_sha256=sha(book), binding_sha256=book.binding_sha256,
        native_submission_sha256=sha(book.native_snapshot), is_approval=False,
        items=[dict(**row.model_dump(), decision=current[row.item_id],
            last_event=next((e.model_dump() for e in reversed(book.events) if e.item_id == row.item_id), None))
            for row in book.items], events=[e.model_dump() for e in book.events],
        native_review_materials=deepcopy(book.native_snapshot),
        instruction='Accept or reject each exact declaration with reviewer and reason. Withdrawal blocks this session; it does not relax or recompute the model.')
