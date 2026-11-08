"""Neutral-start contract and fail-closed transitions, not LLM accuracy tests."""
import copy
import json
import subprocess
import sys

import pytest

from cfm_id import business_intake as work
from cfm_id.business_intake_cli import main
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality import BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec, SemanticClaim, TargetDraft, UnitsVariablesDraft


def scenario(uncertain=False):
    text = '销售员通过合作网络交流。我们想知道全员开通助手后的销售额，以及未开通的同事是否受到影响。'
    case = BusinessCase(case_id='sales', business_question=text)
    def claim(value):
        return SemanticClaim(value=value, basis='EXPLICIT_TEXT',
                             evidence=[dict(source_id='business_question', quote=value)])
    queries = []
    for i, (goal, kind) in enumerate([
            ('全员开通助手后的销售额', 'FIXED_POLICY_VALUE'),
            ('未开通的同事是否受到影响', 'SPILLOVER_EFFECT')], 1):
        target = TargetDraft() if uncertain else TargetDraft(kind=kind, description=claim(goal))
        semantics = QuerySemanticsV010(policy_assignment=claim('全员开通助手')) if i == 1 else QuerySemanticsV010()
        queries.append(BusinessInquiryV010(query_id=f'q{i}', business_goal=claim(goal), target=target,
                                         semantics=semantics))
    units = UnitsVariablesDraft(analysis_unit=claim('销售员'), treatment=claim('开通助手'), outcome=claim('销售额'))
    draft = MultiQueryDraftV010(shared_draft=DraftProblemSpec(target=queries[0].target, units_variables=units),
                              primary_query_id='q1', queries=queries)
    return case, draft.model_dump(mode='json')


def received(uncertain=False):
    case, raw = scenario(uncertain)
    s = work.start(case, reading_format='canonical')
    return work.receive_candidate(s, raw, request_sha256=s.request_sha256)


def test_start_without_route_and_preserve_multiple_targets():
    s = received()
    assert 'lane' not in s.model_dump()
    result = work.inspect(s)
    assert [q['target']['kind'] for q in result['report']['draft']['queries']] == [
        'FIXED_POLICY_VALUE', 'SPILLOVER_EFFECT']
    assert result['state'] == 'SEMANTIC_REVIEW_REQUIRED'
    assert result['method_matching'] == 'NOT_PERFORMED'
    assert result['scientific_review_required'] is True
    assert result['mathematical_claim'] is result['certificate'] is None
    assert not result['core_called'] and not result['estimation_handoff_allowed']
    assert work.inspect(work.start(s.case))['state'] == 'READING_REQUIRED'


def test_request_has_only_public_input_and_original_a0_contract():
    from cfm_id_llm.quality_prompts import SYSTEM_PROMPT_V010, make_quality_user_prompt
    s = received()
    req = work.prepare_request(s)
    assert req['system_prompt'] == SYSTEM_PROMPT_V010
    assert req['user_prompt'] == make_quality_user_prompt(s.case)
    assert 'RECEIVE_CANDIDATE' not in req['user_prompt']
    assert s.intake_id not in req['user_prompt']


def test_scientific_conditions_are_not_granted_by_business_reading():
    s = received()
    report = work.inspect(s)['report']
    assert report['scientific_review_required'] is True
    assert report['draft']['shared_draft']['information_design']['population_information_level'] == 'UNRESOLVED'
    assert report['draft']['shared_draft']['assumptions'] == []
    assert all(q['scientific_status'] == 'SCIENTIFIC_REVIEW_REQUIRED' for q in report['query_quality'])
    assert all('A4' not in q['question'] and 'A5' not in q['question']
               for q in work.clarification_plan(s)['questions'])


def test_reply_preserves_original_clears_candidate_and_requires_new_reading():
    s = received(uncertain=True)
    plan = work.clarification_plan(s)
    assert plan['questions']
    before = s.model_dump(mode='json')
    reply = '暂时没有决定对照，请保留未知，不要替我选择。'
    new = work.append_reply(s, plan, plan['questions'][0]['clarification_id'], reply)
    assert s.model_dump(mode='json') == before
    assert new.case.business_question == s.case.business_question
    assert reply == new.case.sources[-1].text
    assert new.candidate is None
    assert work.inspect(new)['state'] == 'READING_REQUIRED'
    assert new.request_sha256 != s.request_sha256
    with pytest.raises(work.IntakeError, match='STALE_INTAKE_RESPONSE'):
        work.receive_candidate(new, s.candidate, request_sha256=s.request_sha256)
    with pytest.raises(work.IntakeError, match='CLARIFICATION_PLAN'):
        work.append_reply(new, plan, plan['questions'][0]['clarification_id'], reply)


def test_assistant_question_cannot_be_quoted_as_user_reply_evidence(tmp_path):
    s = received(uncertain=True)
    plan = work.clarification_plan(s)
    item = plan['questions'][0]
    new = work.append_reply(s, plan, item['clarification_id'], '我还没决定。')
    req = work.prepare_request(new)
    assert item['question'] in req['user_prompt']  # Context retained for short answers.
    assert item['question'] not in new.case.sources[-1].text
    assert new.clarifications[-1].kind == 'ASSISTANT_CONTEXT_NOT_EVIDENCE'
    raw = copy.deepcopy(s.candidate)
    raw['queries'][0]['business_goal']['evidence'] = [dict(
        source_id=new.case.sources[-1].source_id, quote=item['question'])]
    reread = work.receive_candidate(new, raw, request_sha256=new.request_sha256)
    assert work.inspect(reread)['state'] == 'READING_RECHECK_REQUIRED'
    path = tmp_path / 'clarified.json'
    work.save(new, path)
    assert work.prepare_request(work.restore(path)) == req
    revised = work.revise_materials(new, new.case, reason='人工重整材料')
    assert revised.clarifications == []  # Old short-answer context is not silently rebound.


def test_replacing_candidate_invalidates_previous_clarification_plan():
    s = received(uncertain=True)
    plan = work.clarification_plan(s)
    replaced = work.receive_candidate(s, s.candidate, request_sha256=s.request_sha256)
    with pytest.raises(work.IntakeError, match='CLARIFICATION_PLAN'):
        work.append_reply(replaced, plan, plan['questions'][0]['clarification_id'], '我还没有决定')


def test_same_text_in_another_intake_cannot_receive_old_request_response():
    s = received()
    other = work.start(s.case)
    with pytest.raises(work.IntakeError, match='STALE_INTAKE_RESPONSE'):
        work.receive_candidate(other, s.candidate, request_sha256=s.request_sha256)


def test_network_and_variable_graph_descriptions_are_not_forced_into_one_family():
    from cfm_id_llm.schemas import SourceDocument
    case, raw = scenario()
    case.sources.append(SourceDocument(source_id='study', text='门店之间存在客流影响。变量因果图包含区域需求指向促销与销售。'))
    structure = raw['shared_draft']['structure']
    for field, quote in [('unit_network', '门店之间存在客流影响'),
                         ('variable_causal_graph', '变量因果图包含区域需求指向促销与销售')]:
        structure[field] = dict(value=quote, basis='EXPLICIT_TEXT', evidence=[dict(source_id='study', quote=quote)])
    s = work.start(case, reading_format='canonical')
    result = work.inspect(work.receive_candidate(s, raw, request_sha256=s.request_sha256))
    assert result['report']['draft']['shared_draft']['structure'] == structure
    assert result['method_matching'] == 'NOT_PERFORMED'


@pytest.mark.parametrize('corruption', ['quote', 'approval', 'lane', 'result'])
def test_invalid_or_overreaching_candidate_stays_uncertified(corruption):
    s = received()
    raw = copy.deepcopy(s.candidate)
    if corruption == 'quote':
        raw['queries'][1]['business_goal']['evidence'][0]['quote'] = '来源中没有这句话'
    elif corruption == 'approval':
        raw['shared_draft']['assumptions'] = [dict(name='随机分配', statement='已独立批准',
            status='ACCEPTED', basis='LLM_SUGGESTION')]
    elif corruption == 'lane': raw['lane'] = 'NETWORK_FIXED_POLICY'
    else: raw['certificate'] = {'status': 'POINT'}
    new = work.receive_candidate(s, raw, request_sha256=s.request_sha256)
    assert new.candidate == raw  # No silent correction of model output.
    result = work.inspect(new)
    assert result['state'] == 'READING_RECHECK_REQUIRED'
    assert result['certificate'] is None and not result['core_called']


def test_checkpoint_roundtrip_and_rehashed_scientific_authority_rejected(tmp_path):
    s = received()
    path = tmp_path / 'case.json'
    work.save(s, path)
    assert work.inspect(work.restore(path)) == work.inspect(s)
    with pytest.raises(FileExistsError): work.save(s, path)
    value = work.read_json(path)
    value['payload']['review'] = {'status': 'ACCEPTED'}
    value['sha256'] = work._sha(value['payload'])
    bad = tmp_path / 'tampered.json'
    work.write_json(bad, value)
    with pytest.raises(ValueError): work.restore(bad)


def test_material_or_prompt_drift_blocks_saved_reading(monkeypatch):
    s = received()
    changed = s.model_dump(mode='json')
    changed['case']['business_question'] += '全部改为不开通。'
    with pytest.raises(work.IntakeError, match='MATERIAL_OR_PROMPT_CHANGED'): work.inspect(changed)
    monkeypatch.setattr(work, 'SYSTEM_PROMPT_V010', work.SYSTEM_PROMPT_V010 + '\n新的提示')
    with pytest.raises(work.IntakeError, match='MATERIAL_OR_PROMPT_CHANGED'): work.inspect(s)


def test_one_provider_invocation_without_core_or_selection():
    case, raw = scenario()
    class CountingProvider:
        calls = 0
        def generate_json(self, **kwargs):
            self.calls += 1
            return MockProvider(raw).generate_json(**kwargs)
    provider = CountingProvider()
    s = work.read_once(work.start(case, reading_format='canonical'), provider)
    assert provider.calls == 1
    assert len(work.inspect(s)['report']['draft']['queries']) == 2


def test_no_mathematical_backend_imported_by_neutral_reading():
    script = "from cfm_id import business_intake as b; import sys; b.inspect(b.start(dict(case_id='a',business_question='我要比较两种做法'))); assert not any(m.startswith(('pfn_pipeline', 'research_partial', 'cfm_id.session_routes', 'cfm_id.research_session')) for m in sys.modules)"
    result = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cli_question_to_request_candidate_and_inspection(tmp_path):
    case, raw = scenario()
    from cfm_id_llm.evidence_refs import build_catalog
    ref = build_catalog(case)[1]['ref']
    def claim(value):
        return dict(state='STATED', value=value, refs=[ref])
    raw = dict(queries=[dict(goal=claim(q['business_goal']['value']), kind=q['target']['kind'])
                        for q in raw['queries']])
    question = tmp_path / 'question.txt'
    question.write_text(case.business_question, encoding='utf-8')
    first, request, reply, second, output = [tmp_path / (n + '.json')
                                          for n in ('first', 'request', 'reply', 'second', 'output')]
    assert main(['new', '--question-file', str(question), '--case-id', case.case_id, '--output', str(first)]) == 0
    assert main(['request', '--intake', str(first), '--output', str(request)]) == 0
    work.write_json(reply, raw)
    assert main(['candidate', '--intake', str(first), '--request', str(request),
                 '--candidate', str(reply), '--output', str(second)]) == 0
    assert main(['inspect', '--intake', str(second), '--output', str(output)]) == 0
    result = work.read_json(output)
    assert len(result['report']['draft']['queries']) == 2
    assert not result['core_called']
    assert main(['new', '--question-file', str(question), '--output', str(first)]) == 2


@pytest.mark.parametrize('text', ['{"case_id":"one","case_id":"two"}', '{"value":NaN}'])
def test_json_ambiguity_is_rejected(tmp_path, text):
    path = tmp_path / 'bad.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(work.IntakeError): work.read_json(path)
