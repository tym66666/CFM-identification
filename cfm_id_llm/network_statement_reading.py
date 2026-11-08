"""Opt-in source statements -> the existing unapproved network fact contract.

This is a lossless reading projection, not scientific admission. Literal quotes
are checked for occurrence, never for semantic entailment; independent reading
and science reviews remain mandatory. No solver or theorem imports.
"""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field, model_validator
from . import network_policy_reading as legacy

VERSION = 'network-source-statements-1'
SELECTION_VERSION = 'network-source-selections-1'
INFORMATION_SCOPE_CONTRACT = 'network-source-selections-a4-1'


class SourceQuote(legacy.Record):
    source_id: str
    quote: str = Field(min_length=1, max_length=6000)


class Statement(legacy.Record):
    status: Literal['ADOPTED', 'PROPOSED', 'NOT_ADOPTED', 'UNDECIDED', 'NOT_STATED', 'CONFLICTING']
    quotations: list[SourceQuote] = Field(max_length=8)

    @model_validator(mode='after')
    def evidence_shape(self):
        if self.status == 'NOT_STATED':
            if self.quotations:
                raise ValueError('ABSENT_STATEMENT_HAS_NO_QUOTATION')
        elif not self.quotations:
            raise ValueError('EXPLICIT_STATEMENT_REQUIRES_QUOTATION')
        if self.status == 'CONFLICTING' and len(self.quotations) < 2:
            raise ValueError('CONFLICT_REQUIRES_BOTH_STATEMENTS')
        pairs = [(q.source_id, q.quote) for q in self.quotations]
        if len(set(pairs)) != len(pairs) or any(not q.quote.strip() for q in self.quotations):
            raise ValueError('DISTINCT_NONBLANK_QUOTATIONS_REQUIRED')
        return self


class DesignFacts(legacy.Record):
    assignment_rule_available: legacy.Declaration = Field(description='原文是否提供完整历史名单概率规则；不是与潜在结果独立的科学声明。')
    network_fixed_before_treatment: legacy.Declaration = Field(description='原文是否明确网络在处理前固定；不从随机抽签推定。')


class ScienceStatements(legacy.Record):
    assignment_outcome_independence: Statement = Field(description='完整处理向量与全部对象在全部完整安排下的潜在结果独立。对象之间的抽签相互独立不等于这个条件。')
    consistency: Statement = Field(description='观察结果等于实际完整处理安排下的潜在结果。')
    finite_conditional_means: Statement = Field(description='所需条件一阶矩存在且有限；结果计数或二元标签不自动构成原文采用此条件的声明。')


class MeanSufficiency(Statement):
    scope: Literal['ALL_BINARY_ASSIGNMENTS', 'OTHER', 'UNKNOWN']
    covered_nodes: list[str]

    @model_validator(mode='after')
    def missing_statement_has_no_scope(self):
        if self.status == 'NOT_STATED' and (self.scope != 'UNKNOWN' or self.covered_nodes):
            raise ValueError('ABSENT_SUFFICIENCY_CANNOT_INVENT_SCOPE')
        return self


class StatementReading(legacy.Record):
    version: Literal['network-source-statements-1']
    reference_context: str = Field(pattern=r'^c[0-9a-f]{12}$')
    study: legacy.Study
    assignment: legacy.Assignment
    first_stage_exclusion: legacy.FirstStageExclusion | None = None
    target: legacy.Target
    design_facts: DesignFacts
    scientific_statements: ScienceStatements
    exposure: legacy.Exposure
    mean_sufficiency: MeanSufficiency
    information: list[legacy.Information]
    additional_restrictions: list[legacy.Note]
    unresolved: list[legacy.Note]
    bounded_model: legacy.BoundedModel | None = None


class SelectedStatement(legacy.Record):
    status: Literal['ADOPTED', 'PROPOSED', 'NOT_ADOPTED', 'UNDECIDED', 'NOT_STATED', 'CONFLICTING']
    source_ids: list[str] = Field(max_length=8)

    @model_validator(mode='after')
    def evidence_shape(self):
        if self.status == 'NOT_STATED':
            if self.source_ids:
                raise ValueError('ABSENT_STATEMENT_HAS_NO_SOURCE_SELECTION')
        elif not self.source_ids:
            raise ValueError('EXPLICIT_STATEMENT_REQUIRES_SOURCE_SELECTION')
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError('DISTINCT_SOURCE_SELECTIONS_REQUIRED')
        # Both sides of a conflict may occur in a single source paragraph.
        # Selecting it is not verification that it entails either side.
        return self


class SelectedScienceStatements(legacy.Record):
    assignment_outcome_independence: SelectedStatement = Field(description=ScienceStatements.model_fields['assignment_outcome_independence'].description)
    consistency: SelectedStatement = Field(description=ScienceStatements.model_fields['consistency'].description)
    finite_conditional_means: SelectedStatement = Field(description=ScienceStatements.model_fields['finite_conditional_means'].description)


class SelectedMeanSufficiency(SelectedStatement):
    scope: Literal['ALL_BINARY_ASSIGNMENTS', 'OTHER', 'UNKNOWN']
    covered_nodes: list[str]

    @model_validator(mode='after')
    def missing_statement_has_no_scope(self):
        if self.status == 'NOT_STATED' and (self.scope != 'UNKNOWN' or self.covered_nodes):
            raise ValueError('ABSENT_SUFFICIENCY_CANNOT_INVENT_SCOPE')
        return self


class SelectionReading(StatementReading):
    version: Literal['network-source-selections-1']
    scientific_statements: SelectedScienceStatements
    mean_sufficiency: SelectedMeanSufficiency


STATEMENT_INSTRUCTION = '''design_facts只读原文描述的历史规则是否完整、网络是否在处理前固定；这里的事实不自动变成科学假设。
scientific_statements记录的是“原文对该科学条件说了什么”，不是你认为它是否合理或可推出。每项只填status与quotations：ADOPTED=原文明示采用；PROPOSED=明示拟采用；NOT_ADOPTED=明示不采用或否定；UNDECIDED=明示尚未决定；NOT_STATED=未提及；CONFLICTING=现有材料有未解决冲突。NOT_ADOPTED不证明相反命题。上述状态都不表示已经获科学审核批准。
除NOT_STATED外，每项quotations必须逐字摘录当前source_catalog里的相关原句（source_id和quote），涵盖具体条件及其采用/否定/未决态度；不得写解释或改写句子。NOT_STATED的quotations为空。CONFLICTING保留两方原句，不能挑一方。真实原句出现不等于支持你的解释，仍须独立审核。
先找关于“分配与全部潜在结果独立”的科学陈述，再填assignment_outcome_independence。均匀抽名单或各对象独立掷硬币，只是历史机制描述；即使这种设计在其他前提下可支持随机化论证，也不能把它改写成原文明示采用潜在结果独立性。没有科学陈述就NOT_STATED；负责人说科学条件尚未决定就UNDECIDED。consistency与finite_conditional_means也逐项查找原文，不从其他字段补出。
科学状态不能由类别、常识、未来政策、样本或Prompt的条件定义补齐。科学声明与来源事实分别读取，不选择识别方法。'''
SUFFICIENCY_INSTRUCTION = '''mean_sufficiency也按同样status和逐字quotations读取额外科学声明：均值仅依赖本人处理与已定义同伴暴露。scope和covered_nodes仅记录该声明的原文范围。仅给暴露函数、邻居影响或局部干扰不等于采用均值充分性。未提及时status=NOT_STATED、scope=UNKNOWN、covered_nodes=[]；尚未决定不等于已采用。只针对原试点支持内的声明不能扩大成ALL_BINARY_ASSIGNMENTS。'''


def make_request(bundle, *, binding, assignment_semantics=None):
    refs = legacy.reference_catalog(bundle, binding=binding)
    schema = StatementReading.model_json_schema()
    schema['properties']['reference_context']['const'] = refs['context']
    schema['$defs']['SourceId'] = dict(type='string', enum=list(refs['aliases']))
    schema['$defs']['SourceQuote']['properties']['source_id'] = {'$ref': '#/$defs/SourceId'}
    for item in schema['$defs'].values():
        props = item.get('properties', {})
        if 'source_ids' in props:
            props['source_ids'].update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    from .assignment_semantics import guidance, describe
    addition = guidance(assignment_semantics)
    if addition:
        describe(schema, specialist=True)
    lines = []
    for line in legacy.SYSTEM.splitlines():
        if line.startswith('assumptions的'):
            line = STATEMENT_INSTRUCTION
        elif line.startswith('mean_sufficiency是'):
            line = SUFFICIENCY_INSTRUCTION
        else:
            line = line.replace('target、assumptions、exposure', 'target、design_facts、scientific_statements、exposure')
        lines.append(line)
    return dict(system='\n'.join(lines) + addition,
        user=json.dumps(dict(case_id=bundle['case_id'], question=bundle['question'],
            reference_context=refs['context'], source_catalog={k:dict(doc_id=r['doc_id'],text=r['text'])
                for k,r in refs['aliases'].items()}, output_schema=schema), ensure_ascii=False))


def parse(bundle, raw, *, binding):
    wire = StatementReading.model_validate(deepcopy(raw))
    return _project(bundle, raw, wire, binding=binding, selected=False)


def make_selection_request(bundle, *, binding, assignment_semantics=None):
    """Select current source IDs; the program retrieves complete source text."""
    request = make_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    body = json.loads(request['user'])
    schema = SelectionReading.model_json_schema()
    schema['properties']['reference_context']['const'] = body['reference_context']
    schema['$defs']['SourceId'] = dict(type='string', enum=list(body['source_catalog']))
    for item in schema['$defs'].values():
        props = item.get('properties', {})
        if 'source_ids' in props:
            props['source_ids'].update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    from .assignment_semantics import guidance, describe
    if guidance(assignment_semantics):
        describe(schema, specialist=True)
    body['output_schema'] = schema
    paragraphs = STATEMENT_INSTRUCTION.splitlines()
    paragraphs[1] = paragraphs[1].replace('status与quotations', 'status与source_ids')
    paragraphs[2] = ('除NOT_STATED外，每项source_ids必须选择当前source_catalog中说明该条件及其采用/否定/未决态度的原文编号。'
        '程序会取回所选来源完整原文，你不抄写或改写引文。NOT_STATED的source_ids为空。'
        'CONFLICTING选择能保留冲突双方的全部来源；双方也可能在同一段内。来源存在不等于支持你的解释，仍须独立审核。')
    request['system'] = request['system'].replace(STATEMENT_INSTRUCTION, '\n'.join(paragraphs)).replace(
        SUFFICIENCY_INSTRUCTION, SUFFICIENCY_INSTRUCTION.replace('status和逐字quotations', 'status和原文编号source_ids'))
    request['user'] = json.dumps(body, ensure_ascii=False)
    return request


def parse_selection(bundle, raw, *, binding):
    wire = SelectionReading.model_validate(deepcopy(raw))
    return _project(bundle, raw, wire, binding=binding, selected=True)


def make_information_request(bundle, *, binding, assignment_semantics=None):
    """Same source-selection wire, with explicit A4 field meaning."""
    from .information_semantics import with_information_scope
    return with_information_scope(make_selection_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics))


def _project(bundle, raw, wire, *, binding, selected):
    refs = legacy.reference_catalog(bundle, binding=binding)
    if wire.reference_context != refs['context']:
        raise ValueError('STALE_QUERY_REFERENCE_CONTEXT')
    statements = {}; conflicts = []

    def declaration(name, statement):
        ids = []; quotations = []
        if selected:
            if any(s not in refs['aliases'] or not refs['aliases'][s]['text'].strip() for s in statement.source_ids):
                raise ValueError('STATEMENT_SELECTION_NOT_IN_CURRENT_SOURCE')
            cited = [(s, refs['aliases'][s]['text']) for s in statement.source_ids]
        else:
            cited = [(q.source_id, q.quote) for q in statement.quotations]
        for source_id, quote in cited:
            if source_id not in refs['aliases'] or quote not in refs['aliases'][source_id]['text']:
                raise ValueError('STATEMENT_QUOTE_NOT_IN_CURRENT_SOURCE')
            if source_id not in ids:
                ids.append(source_id)
            quotations.append(dict(source_id=refs['aliases'][source_id]['source_id'], quote=quote))
        statements[name] = dict(status=statement.status, quotations=quotations)
        if statement.status == 'CONFLICTING':
            conflicts.append(name)
        value = {'ADOPTED': True, 'PROPOSED': True, 'NOT_ADOPTED': False}.get(statement.status)
        return dict(value=value, source_ids=ids)

    data = wire.model_dump()
    design = data.pop('design_facts'); data.pop('scientific_statements')
    science = wire.scientific_statements
    data['version'] = legacy.VERSION
    data['assumptions'] = dict(known_assignment_law=design['assignment_rule_available'],
        fixed_pretreatment_network=design['network_fixed_before_treatment'],
        full_vector_randomization=declaration('assignment_outcome_independence',science.assignment_outcome_independence),
        consistency=declaration('consistency',science.consistency),
        finite_conditional_first_moments=declaration('finite_conditional_means',science.finite_conditional_means))
    data['mean_sufficiency'] = dict(declaration('mean_sufficiency',wire.mean_sufficiency),
        scope=wire.mean_sufficiency.scope, covered_nodes=list(wire.mean_sufficiency.covered_nodes))
    result = legacy.parse(bundle, data, binding=binding)
    result['statement_reading_receipt'] = dict(version=wire.version, statements=statements,
        original_candidate_sha256=sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest(),
        conflicts=conflicts, quotation_occurrence_verified=True, semantic_entailment_verified=False,
        scientific_approval=False, native_math_called=False,
        projection='Source attitude only: ADOPTED/PROPOSED -> unapproved true; NOT_ADOPTED -> route unavailable, not proof of the negation; other states -> null.')
    if selected:
        result['statement_reading_receipt']['quotation_origin'] = 'PROGRAM_RETRIEVED_COMPLETE_CURRENT_SOURCE'
    return result
