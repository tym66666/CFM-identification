"""Carry reviewed intent and exact provenance to existing fact readers.

No prose-to-coordinate inference, citation repair, scientific permission or
new mathematical method. The fact reply stays unchanged and must be reviewed
against the single owner of the selected business target.
"""
from copy import deepcopy
import json

VERSION = 'reviewed-intent-handoff-1'
READERS = ('NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS',
           'NETWORK_RANDOMIZED_EFFECT_FACTS', 'NETWORK_OBSERVATIONAL_POLICY_FACTS',
           'NETWORK_RANDOMIZED_ARM_FACTS','NETWORK_FINITE_POLICY_FACTS','NETWORK_OBSERVATIONAL_EFFECT_FACTS')
COMMON = ('analysis_unit', 'treatment', 'outcome')
SEMANTICS = ('first_arrangement', 'second_arrangement', 'target_population',
             'aggregation', 'time_horizon', 'conditioning_context',
             'standardization_distribution', 'neighbor_exposure', 'outcome',
             'decision_constraints')
INSTRUCTION = ('本次reviewed_intent是本问已审核的业务意图，不是新事实或科学批准。'
    '目标含义、评价范围、时期和共同条件由它保留，不再另写一份业务摘要；'
    '只构造当前Schema需要的数学坐标及尚未读取的事实。'
    'source_links保留原文位置，fact_source_ids才是本次可用的原文引用；a0_ref不能直接作为本次source_ids。'
    '共同单位和处理定义可据这些原文核对，不能从“全部”自行补未知名单或默认0/1编码。'
    '若坐标不能忠实表达已审核意图，保留缺项或冲突，不能悄悄改目标。'
    'UNKNOWN只表示此前未读出，不证明没有条件；新发现的原文仍保留并交审核。'
    'time_horizon是结果时期；conditioning_context才是明确限定评价的背景。网络固定、资料中存在特征或时期相同，本身不产生额外背景条件；不能在事实阶段据此新增条件目标。真实给定G或X=x的目标则须保留。'
    '科学声明、总体信息和其他问题的条件不得从此交接自动批准或混入当前目标。')


def _source_links(ids, a0_catalog, fact_catalog, documents):
    links = []
    for ref in ids:
        origin = a0_catalog[ref]
        doc = documents[origin['source_id']]
        start, end = origin['start'], origin['end']
        if doc[start:end] != origin['quote']:
            raise ValueError('INTENT_ORIGINAL_QUOTE_MISMATCH')
        matches = [(key, row) for key, row in fact_catalog.items()
                   if row['doc_id'] == origin['source_id']
                   and max(start, row['start']) < min(end, row['end'])]
        # Compare offsets in the same original document, never match a phrase
        # in another document or assume the two catalogs use identical IDs.
        covered = set()
        for _, row in matches:
            if doc[row['start']:row['end']] != row['text']:
                raise ValueError('INTENT_FACT_QUOTE_MISMATCH')
            covered.update(range(max(start,row['start']), min(end,row['end'])))
        if any(not doc[i].isspace() and i not in covered for i in range(start,end)):
            raise ValueError('INTENT_SOURCE_SPAN_NOT_COVERED')
        links.append(dict(a0_ref=ref,document_id=origin['source_id'],start=start,end=end,
            quote=origin['quote'],fact_source_ids=[key for key,_ in matches]))
    return links


def build(session, query_id, review, reader_id, references):
    """Called only after current full A0 review, with the issued fact catalog."""
    from .compact_reference_contract import catalog
    from cfm_id.business_dispatch import sha
    if reader_id not in READERS:
        raise ValueError('INTENT_HANDOFF_READER_NOT_CONNECTED')
    original = session.candidate['queries'][int(query_id[1:])-1]
    a0 = {r['ref']:r for r in catalog(session.case,session.a0_reference_contract)}
    documents = dict(session.case.source_map(),business_question=session.case.business_question)
    values = {f'common.{key}':session.candidate['common'][key] for key in COMMON}
    values.update({'query.goal':original['goal'],'query.kind':original['kind'],
                   'query.comparison_order':original['comparison_order']})
    values.update({f'query.{key}':original['semantics'].get(key,'UNKNOWN') for key in SEMANTICS})
    slots = {}
    for name, value in values.items():
        ids = value.get('refs',[]) if isinstance(value,dict) else []
        links = _source_links(ids,a0,references['aliases'],documents)
        claim = {k:deepcopy(v) for k,v in value.items() if k!='refs'} if isinstance(value,dict) else value
        slots[name] = dict(claim=claim,source_links=links,
            fact_source_ids=list(dict.fromkeys(i for link in links for i in link['fact_source_ids'])))
    identity = dict(version=VERSION,query_id=query_id,reader_id=reader_id,
        a0_contract=session.a0_response_contract,a0_candidate_sha256=sha(session.candidate),
        a0_review_sha256=sha(review),slots=slots)
    return dict(identity,intent_sha256=sha(identity),semantic_owner='REVIEWED_A0_QUERY',
        coordinate_owner='FACT_READER_WITH_INDEPENDENT_ALIGNMENT_REVIEW',
        scientific_approval=False,is_citable_source=False,candidate_modified=False)


def attach(request, intent, binding):
    result = deepcopy(request)
    body, end = json.JSONDecoder().raw_decode(result['user'])
    body['reviewed_intent'] = dict(deepcopy(intent),fact_binding_sha256=binding)
    result['user'] = json.dumps(body,ensure_ascii=False) + result['user'][end:]
    result['system'] += '\n' + INSTRUCTION
    return result


def field_constraints(paths):
    relevant = ('/study','/target','/conditioning','/bounded_model','/unresolved')
    return [dict(field_path=path,description=INSTRUCTION)
            for path in paths if path=='' or any(path==p or path.startswith(p+'/') for p in relevant)]


def add_review_expectations(rows, intent):
    """Existing source/role decisions now include explicit stage alignment.

    No extra scientific authority and no automatic natural-language equality
    judgment. The worksheet hash binds these expectations to the raw reply.
    """
    expectations = dict(intent_sha256=intent['intent_sha256'],slots=deepcopy(intent['slots']),
        required_checks=['same_target_and_subtraction_order','same_evaluation_roster_and_weights',
                         'same_treatment_coding_and_outcome','same_period_and_common_conditions',
                         'missing_and_conflicting_content_preserved'],
        meaning='核对事实坐标是否忠实表达这些已审核字段。冲突或遗漏须拒绝；不能由审核人补值后当作模型通过。',
        automatic_semantic_match=False,scientific_approval=False)
    rows['']['reviewed_intent_alignment'] = expectations
    # Keep real candidate paths for feedback. Rejection of the corresponding
    # value_state/field_role stops execution through the existing review gate.
    for path,row in rows.items():
        if path and path.split('/')[1] in ('study','target','conditioning','bounded_model'):
            row['reviewed_intent_sha256'] = intent['intent_sha256']
            row['role'] += ' 同时核对全局工作表的reviewed_intent_alignment；保持已审核目标、范围、编码、时期和共同条件。'
