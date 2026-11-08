"""Synthetic reference answers for offline tests, never imported by the server."""
from cfm_id.business_intake import prepare_request
from cfm_id_llm.compact_reference_contract import catalog, request_context
from cfm_id_llm.scoped_effect_reading import VERSION as FACT_VERSION
from examples.network_effect_dispatch_reference import material, fact_reference

def fixture():
    case, info = material()
    info['probabilities'] = {node: '1/2' for node in info['nodes']}
    info['docs']['assignment'] = '各门店独立Bernoulli抽签，每家启用概率均为1/2。'
    case = case.model_copy(update={'sources': [source.model_copy(update={
        'text': info['docs'][source.source_id]}) for source in case.sources]})
    return case, info

def a0_candidate(session, info):
    """Hand-authored reference answer, not an automated business reader."""
    refs = catalog(session.case, session.a0_reference_contract)
    def claim(value, source):
        return dict(state='STATED', value=value,
                    refs=[r['ref'] for r in refs if r['source_id'] == source])
    docs = info['docs']
    raw = dict(reference_context=request_context(prepare_request(session)['user_prompt']),
        common=dict(analysis_unit=claim(info['unit'], 'study'),
            treatment=claim(info['treatment'], 'study'), outcome=claim(info['outcome'], 'study'),
            assignment_family='INDEPENDENT_BERNOULLI', assignment_law=claim(docs['assignment'], 'assignment'),
            unit_network=claim(docs['network'], 'network'), exposure_mapping=claim(docs['exposure'], 'exposure'),
            network_pretreatment_status=claim('网络在处理前固定', 'network'),
            available_information=claim(docs['information'], 'information'), covariates=[]),
        queries=[dict(kind='DIRECT_EFFECT', goal=claim(info['questions']['q1'], 'business_question'),
            semantics=dict(target_population=claim(docs['population'], 'population'),
                aggregation=claim('评价名单内等权平均', 'population'), time_horizon=claim('同一周', 'context'),
                policy_assignment='NOT_APPLICABLE', conditioning_context='UNKNOWN',
                standardization_distribution=claim(docs['remaining'], 'remaining')),
            comparison_request=dict(quantity='EVALUATED_MINUS_REFERENCE',
                evaluated=claim('自己启用', 'business_question'), reference=claim('自己未启用', 'business_question'),
                shared_condition=claim('合作对象过半启用', 'business_question'),
                refs=claim(info['questions']['q1'], 'business_question')['refs']))])
    if session.a0_response_contract == 'target-first-skill-1':
        from cfm_id_llm.target_first_reading import COMMON_FIELDS
        raw['common']={k:raw['common'].get(k,'UNKNOWN') for k in COMMON_FIELDS}
        q=raw['queries'][0]; comparison=q.pop('comparison_request'); sem=q['semantics']
        sem.pop('policy_assignment')
        sem.update(first_arrangement=claim('自己启用且合作对象过半启用','business_question'),
            second_arrangement=claim('自己未启用且合作对象过半启用','business_question'),
            neighbor_exposure=claim('合作对象过半启用','business_question'),
            outcome=claim(info['outcome'],'study'),decision_constraints='UNKNOWN')
        q['comparison_order']=dict(operation='FIRST_MINUS_SECOND',refs=comparison['refs'])
    return raw

def fact_candidate(entry, info):
    facts = fact_reference(entry, info)
    if entry.get('effect_fact_contract') != FACT_VERSION:
        return facts
    target = facts['target']
    first, second = target.pop('first'), target.pop('second')
    target.pop('operation'); target.pop('kind')
    target.update(evaluated=first, reference=second, definition_refs=['study'])
    facts['version'] = FACT_VERSION
    facts['assignment']['definition_refs'] = ['study']
    for arm in (first, second):
        arm['definition_refs'] = ['study', 'exposure']
    for item in facts['information']:
        item.update(definition_refs=['study'], scope_status='DECLARED', scope_source_ids=list(item['source_ids']))
    return facts
