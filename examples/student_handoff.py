"""Three offline network examples through the current public project entry.

All drafts and reviews here are explicit synthetic fixtures, NOT live model
answers. A real application must obtain and independently review its own drafts.
"""
from copy import deepcopy
from pathlib import Path
import argparse,json
from cfm_id import project,business_intake as intake,business_dispatch as dispatch
from cfm_id import business_field_review as fields,fact_source_review as sources,business_case
from cfm_id_llm.compact_reference_contract import split_user,request_context
from cfm_id_llm.network_policy_reading import reference_catalog
from . import network_dispatch_reference as point,network_bounded_dispatch_reference as bounded
from .business_dispatch_reference import approve


def material(name):
    if name=='point':return point.case(design='D1',sufficiency=False)[0]
    return bounded.case(missing_scope=name=='missing_condition')[0]


def a0_fixture(session):
    """Hand-authored claims for these three materials; never processes an LLM reply."""
    case=session.case;docs=case.source_map();request=intake.prepare_request(session)
    rows=split_user(request['user_prompt'])[1]['source_catalog']
    def claim(text,*documents):
        return dict(state='STATED',value=text,refs=[r['ref'] for r in rows if r['source_id'] in documents])
    common=dict(analysis_unit=claim(docs['study'].split('。')[0]+'。','study'),
        treatment=claim('每个网点使用AI记1、不使用记0。','study'),
        outcome=claim('本周任务是否按时完成，完成记1、未完成记0。','study'),
        assignment_family='INDEPENDENT_BERNOULLI' if '各自独立' in docs['assignment'] else 'COMPLETE_RANDOMIZATION',
        assignment_law=claim(docs['assignment'],'assignment'),unit_network=claim(docs['network'],'network'),
        variable_causal_graph='UNKNOWN')
    goal=claim(case.business_question,'business_question')
    sem=dict(target_population=claim('评价完整研究名单中的全部网点。','business_question','study'),
        first_arrangement=claim('完整研究名单中每个网点都使用AI助手。','business_question','study'),
        second_arrangement='NOT_APPLICABLE',neighbor_exposure='UNKNOWN',aggregation=claim('全部网点等权平均。','business_question'),
        time_horizon=claim('本周。','study'),outcome=deepcopy(common['outcome']),
        standardization_distribution='UNKNOWN',conditioning_context='UNKNOWN',decision_constraints='UNKNOWN')
    return dict(common=common,queries=[dict(kind='FIXED_POLICY_VALUE',goal=goal,semantics=sem,
        comparison_order=dict(operation='NOT_APPLICABLE',refs=goal['refs']))],reference_context=request_context(request['user_prompt']))


def fact_fixture(entry,name):
    """Existing source-bound reference, expressed in the configured selection wire."""
    raw=(point.candidate(entry,design='D1',sufficiency=False) if name=='point'
         else bounded.reference(entry,missing_scope=name=='missing_condition'))
    a=raw.pop('assumptions');raw['version']='network-source-selections-1'
    raw['design_facts']=dict(assignment_rule_available=a['known_assignment_law'],network_fixed_before_treatment=a['fixed_pretreatment_network'])
    def statement(value,ids):
        return dict(status='ADOPTED' if value is True else 'NOT_ADOPTED' if value is False else 'NOT_STATED',source_ids=ids if value is not None else [])
    raw['scientific_statements']={new:statement(a[old]['value'],a[old]['source_ids']) for new,old in (
        ('assignment_outcome_independence','full_vector_randomization'),('consistency','consistency'),('finite_conditional_means','finite_conditional_first_moments'))}
    sf=raw['mean_sufficiency'];raw['mean_sufficiency']=dict(statement(sf['value'],sf['source_ids']),scope=sf['scope'],covered_nodes=sf['covered_nodes'])
    # Explicit fixture citations cover both the actual claim and its definitions.
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    defs=[sid for sid,row in refs['aliases'].items() if row['doc_id']=='study']
    raw['study'].update(treatment='每个网点使用AI记1、不使用记0',outcome='本周任务是否按时完成，完成记1、未完成记0')
    raw['target']['source_ids']=list(dict.fromkeys(raw['target']['source_ids']+defs))
    if raw['assignment']['probabilities']:
        raw['assignment']['source_ids']=list(dict.fromkeys(raw['assignment']['source_ids']+defs))
    if raw['mean_sufficiency']['covered_nodes']:
        raw['mean_sufficiency']['source_ids']=list(dict.fromkeys(raw['mean_sufficiency']['source_ids']+defs+raw['exposure']['source_ids']))
    for info in raw['information']:
        info['source_ids']=list(dict.fromkeys(info['source_ids']+defs+(raw['exposure']['source_ids'] if info['signature_cells'] else [])))
    if entry.get('network_fact_contract') == 'network-shared-definitions-1':
        # These are explicit offline fixtures, never edits to an LLM response.
        from cfm_id_llm.shared_fact_definitions import LAW_NAMES
        raw['study']['network_source_ids']=[sid for sid,row in refs['aliases'].items() if row['doc_id']=='network']
        reverse={value:key for key,value in LAW_NAMES.items()}
        for info in raw['information']:info['operator']=reverse.get(info['operator'],info['operator'])
    return raw


def synthetic_review(sheet,version,dimensions):
    decisions={}
    for path,row in sheet['fields'].items():
        ids=list(sheet['source_catalog'])
        decisions[path]=dict(**{a:'ACCEPTED' for a in dimensions},reason='Explicit offline synthetic fixture review against its supplied materials; not real scientific approval.',source_ids=ids)
    return dict(version=version,binding_sha256=sheet['binding_sha256'],authority='SYNTHETIC_TEST',
        reviewer='Offline handoff fixture reviewer',evidence='Hand-authored, fixed teaching materials and expected semantic facts. Never use this fixture approver for real model replies.',decisions=decisions)


def run(output,*,allow_synthetic_reviews=False):
    if allow_synthetic_reviews is not True:raise ValueError('EXPLICIT_SYNTHETIC_REVIEW_OPT_IN_REQUIRED')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);summaries=[]
    def save(path,value):
        intake.write_json(path,json.loads(json.dumps(value,ensure_ascii=False,default=lambda x:x.model_dump(mode='json'))))
    for name,expected in (('point','POINT'),('partial','PARTIAL'),('missing_condition','NEEDS_INPUT')):
        folder=out/name;folder.mkdir();case=material(name);s=project.start(case)
        raw=a0_fixture(s);s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
        w=fields.prepare(s,'q1',authority='SYNTHETIC_TEST')['field_worksheet']
        review=synthetic_review(w,fields.VERSION,('field_role','value_state','source_coverage'))
        q=fields.submit(s,'q1',review,authority='SYNTHETIC_TEST')['query_review']
        e=project.prepare_reader(s,'q1',query_review=q);assert e['state']=='READY_TO_READ',e
        facts=fact_fixture(e,name);sw=sources.prepare(e,facts)
        source_review=synthetic_review(sw,sources.VERSION,sources.DIMENSIONS)
        options=dict(query_review=q,candidate=facts,request_sha256=e['request_sha256'],source_review=source_review)
        information_review=None
        if name!='point':
            from cfm_id import network_information_evidence as evidence
            iw=evidence.prepare(e,facts)
            information_review=dict(version=iw['version'],binding_sha256=iw['binding_sha256'],authority='SYNTHETIC_TEST',
                reviewer='Offline handoff fixture reviewer',evidence='One supplied exact mean table; study and exposure documents only define coordinates. Explicit synthetic audit.',
                disposition='ACCEPTED',table_source_ids=[sid for sid,row in iw['source_catalog'].items() if row['doc_id']=='information'],
                supporting_source_ids=[sid for sid,row in iw['source_catalog'].items() if row['doc_id']!='information'])
            options['information_evidence_review']=information_review
        plan=project.inspect_methods(s,'q1',**options)
        approvals=point.approval_records(plan) if plan['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in plan else dict(research_protocol_selected=True)
        result=project.execute(s,'q1',**options,**approvals)
        assert result['state']==expected,(name,result['state'],result.get('reason_code'))
        assert result['independent_replay']==(expected!='NEEDS_INPUT')
        if expected=='NEEDS_INPUT':assert not result['backend_called'] and result['certificate'] is None
        if expected=='PARTIAL':assert result['mathematical_claim']['interval']==['3/7','4/7'] and result['mathematical_claim']['sharp']
        whole=project.execute_case(s,{'q1':dict(options,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})},
            case_review=approve(project.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
        assert whole['results'][0]['result']==result
        for filename,value in (('business',case.model_dump(mode='json')),('a0_request',intake.prepare_request(s)),('a0_draft',raw),('a0_review',review),
            ('fact_request',e),('fact_draft',facts),('source_review',source_review),('information_review',information_review),('plan',plan),('scientific_reviews',approvals),('result',result),('whole_case',whole)):
            save(folder/(filename+'.json'),value)
        intake.save(s,folder/'intake.json')
        summaries.append(dict(example=name,state=result['state'],reason=result.get('reason_code'),
            independent_replay=result['independent_replay'],backend_called=result['backend_called'],claim=result['mathematical_claim']))
    report=dict(api_calls=0,drafts='HAND_AUTHORED_FIXTURES_NOT_LLM_OUTPUT',reviews='EXPLICIT_SYNTHETIC_ONLY',
        reading_config=project.reading_config().model_dump(mode='json'),examples=summaries)
    save(out/'SUMMARY.json',report);return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-synthetic-reviews',action='store_true');a=p.parse_args(argv)
    result=run(a.output,allow_synthetic_reviews=a.allow_synthetic_reviews)
    print(json.dumps(dict(api_calls=0,examples=[{k:r[k] for k in ('example','state','independent_replay','reason')} for r in result['examples']]),ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
