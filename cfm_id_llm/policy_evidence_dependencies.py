"""Opt-in explicit definition references for fixed policies and their contrast.

Only wire evidence ownership changes. Direct claims and declared dependencies
remain separately reviewable; resolution neither invents references nor grants
semantic/scientific approval. Historical profiles retain their old contracts.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field
from . import network_policy_reading as legacy, network_statement_reading as statements
from . import reading_alignment_contract as alignment, network_source_dependencies as flat
from .source_reference_wire import expand

CONTRACT = 'network-policy-definition-refs-1'
RULE = ('本记录的引用由source_ids和definition_refs共同组成：source_ids支持本记录的直接业务主张；'
        'definition_refs显式引用study记录的对象名册、对象顺序和本人处理编码定义。'
        '定义不能代替本问选择的政策、评价范围、概率、信息性质或记录覆盖范围；这些仍须直接引用。'
        '未声明的依赖不会自动继承，定义与主张仍分别接受语义审核。')


class PolicyAssignment(legacy.Assignment):
    definition_refs: list[Literal['study']] = Field(description=RULE)


class PolicyTarget(legacy.Target):
    definition_refs: list[Literal['study']] = Field(description=RULE)


class PolicyInformation(legacy.Information):
    definition_refs: list[Literal['study']] = Field(description=RULE)


class Reading(statements.SelectionReading):
    version: Literal['network-policy-definition-refs-1']
    assignment: PolicyAssignment
    target: PolicyTarget
    information: list[PolicyInformation]


@lru_cache(maxsize=1)
def contrast_target_model():
    # Import lazily: the existing contrast module owns its target, not this wire.
    from .network_contrast_reading import PolicyEndpoint, PolicyContrastTarget

    class DefinedPolicyEndpoint(PolicyEndpoint):
        definition_refs: list[Literal['study']] = Field(description=RULE)

    class DefinedPolicyContrastTarget(PolicyContrastTarget):
        first: DefinedPolicyEndpoint
        second: DefinedPolicyEndpoint

    return DefinedPolicyContrastTarget


def _request(request, model, *, contract=CONTRACT, extra_required=None, schema_aliases=None):
    body = json.loads(request['user']); old = body['output_schema']
    schema = model.model_json_schema()
    names = dict(PolicyAssignment='Assignment', PolicyTarget='Target', PolicyInformation='Information',
                 DefinedPolicyEndpoint='PolicyEndpoint', DefinedPolicyContrastTarget='PolicyContrastTarget')
    names.update(schema_aliases or {})
    for name, node in schema['$defs'].items():
        prior = old['$defs'].get(name, old['$defs'].get(names.get(name, name), {}))
        for key, prop in node.get('properties', {}).items():
            if key != 'definition_refs' and 'description' in prior.get('properties', {}).get(key, {}):
                prop['description'] = prior['properties'][key]['description']
        props = node.get('properties', {})
        if 'definition_refs' in props:
            props['source_ids']['description'] = RULE
            props['definition_refs']['uniqueItems'] = True
        for key, prop in props.items():
            if key.endswith('source_ids'):
                prop.update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    # Preserve root-level field responsibilities (e.g. additional restrictions).
    for key, prop in schema['properties'].items():
        if 'description' in old['properties'].get(key, {}):
            prop['description'] = old['properties'][key]['description']
    schema['$defs']['SourceId'] = deepcopy(old['$defs']['SourceId'])
    schema['properties']['reference_context']['const'] = old['properties']['reference_context']['const']
    body['output_schema'] = schema
    body.pop('source_dependency_contract', None)
    body['reading_alignment_contract']['field_constraints'] = alignment._status_rules(schema)
    body['evidence_dependency_contract'] = dict(version=contract,
        definitions={'study': dict(path='/study/source_ids', supports=['object identity and order', 'own-treatment coding'])},
        required=dict(assignment='study when probabilities, groups or clusters contain named objects',
                      policy_target='study when assignment or population is nonempty',
                      information='study when outcome_nodes, assignment_cells or signature_cells are nonempty'),
        instruction=RULE, automatic_source_selection=False, entailment_verified=False)
    body['evidence_dependency_contract']['required'].update(extra_required or {})
    # Replace only the superseded flat-citation ownership wording. All scientific
    # and target instructions are inherited, including the exact SCIENCE rule.
    system = request['system'].replace('\n' + flat.INSTRUCTION, '')
    system = system.replace(alignment.FACT_GUIDANCE, alignment.SCIENCE)
    return dict(system=system, user=json.dumps(body, ensure_ascii=False))


def make_request(bundle, *, binding, assignment_semantics=None):
    return _request(alignment.make_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics), Reading)


def make_contrast_request(bundle, *, binding, assignment_semantics=None):
    from . import network_contrast_reading as contrast
    return _request(contrast.make_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics, profile=alignment.NETWORK_CONTRACT),
        contrast.reading_model(CONTRACT))


def _resolve(bundle, raw, *, binding, model, contrast=False, contract=CONTRACT, additional_records=()):
    candidate = model.model_validate(deepcopy(raw)).model_dump(mode='json')
    refs = legacy.reference_catalog(bundle, binding=binding)
    if candidate['reference_context'] != refs['context']:
        raise ValueError('STALE_POLICY_REFERENCE_CONTEXT')
    expand(deepcopy(candidate), refs)  # Includes unused definition source IDs.
    rows = [('/assignment', candidate['assignment'], any(candidate['assignment'].get(k) for k in ('probabilities','groups','clusters')))]
    for path, record in ([(f'/target/{side}', candidate['target'][side]) for side in ('first','second')]
                         if contrast else [('/target', candidate['target'])]):
        rows.append((path, record, bool(record['assignment'] or record['population'])))
    rows += [(f'/information/{i}', record, bool(record['outcome_nodes'] or record['assignment_cells'] or record['signature_cells']))
             for i, record in enumerate(candidate['information'])]
    # Additional record owners are supplied by registered source code only.
    # A declared definition is evidence of identity, never of scope or adoption.
    rows += [('/'+name, candidate[name], any(candidate[name].get(k) for k in keys))
             for name, keys in additional_records]
    resolutions = []
    for path, record, required in rows:
        uses = record.pop('definition_refs')
        if len(uses) != len(set(uses)) or (required and 'study' not in uses):
            raise ValueError('EXPLICIT_DEFINITION_DEPENDENCIES_REQUIRED')
        direct = list(record['source_ids']); resolved = list(direct)
        if uses:
            if not direct:
                raise ValueError('DIRECT_CLAIM_SOURCE_REQUIRED')
            origin = candidate['study']['source_ids']
            if not origin:
                raise ValueError('CITED_DEFINITION_REQUIRED')
            resolved.extend(origin)
        # Native information.source_ids denotes the information table itself.
        # Keep definitions in a bound evidence receipt, not in the table list:
        # mixing them would falsely turn one exact table into multiple sources.
        resolutions.append(dict(field_path=path, direct_source_ids=direct,
            definition_refs=uses, resolved_source_ids=list(dict.fromkeys(resolved))))
    return candidate, dict(version=contract, resolutions=resolutions,
        source_entailment_verified=False, raw_candidate_modified=False,
        automatic_source_selection=False, scientific_approval=False,
        native_source_ids_role='DIRECT_CLAIMS_ONLY_DEFINITIONS_RETAINED_IN_RECEIPT')


def parse(bundle, raw, *, binding):
    return parse_defined(bundle, raw, binding=binding, model=Reading)


def parse_defined(bundle, raw, *, binding, model, contract=CONTRACT, additional_records=()):
    candidate, receipt = _resolve(bundle, raw, binding=binding, model=model,
        contract=contract, additional_records=additional_records)
    candidate['version'] = statements.SELECTION_VERSION
    decoded = statements.parse_selection(bundle, candidate, binding=binding)
    statement_receipt = decoded['statement_reading_receipt']
    statement_receipt['projected_candidate_sha256'] = statement_receipt['original_candidate_sha256']
    statement_receipt['original_candidate_sha256'] = sha256(json.dumps(raw, ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()
    decoded['evidence_dependencies'] = receipt
    return decoded


def parse_contrast(bundle, raw, *, binding):
    return parse_defined_contrast(bundle, raw, binding=binding, mean_parser=parse)


def parse_defined_contrast(bundle, raw, *, binding, mean_parser, contract=CONTRACT, additional_records=()):
    from . import network_contrast_reading as contrast
    candidate, receipt = _resolve(bundle, raw, binding=binding,
        model=contrast.reading_model(contract), contrast=True, contract=contract, additional_records=additional_records)
    decoded = contrast.parse(bundle, candidate, binding=binding, profile=alignment.NETWORK_CONTRACT)
    # The downstream mean adapter still carries the original request profile.
    # Preserve explicit dependency declarations in its two wire projections;
    # do not feed a legacy-shaped candidate to the new profile's parser.
    kinds = {'FIXED_POLICY_MEAN_DIFFERENCE': 'FIXED_POLICY_MEAN', 'OTHER': 'OTHER', 'UNKNOWN': 'UNKNOWN'}
    for side in contrast.SIDES:
        endpoint = contrast.reading_model(contract).model_validate(deepcopy(raw)).model_dump(mode='json')
        endpoint['version'] = contract
        endpoint['target'] = dict(endpoint['target'][side], kind=kinds[endpoint['target']['kind']])
        decoded['endpoint_candidates'][side] = endpoint
        decoded['endpoint_readings'][side] = mean_parser(bundle, endpoint, binding=binding)
    decoded['evidence_dependencies'] = receipt
    return decoded


def field_constraints(paths, *, request, contract=CONTRACT):
    body = json.JSONDecoder().raw_decode(request['user'])[0]
    if body.get('evidence_dependency_contract', {}).get('version') != contract:
        raise ValueError('POLICY_DEFINITION_REQUEST_REQUIRED')
    schema = body['output_schema']
    rows = flat._schema_rules(schema) + alignment._status_rules(schema)
    def normalized(path):
        return '/'.join('*' if part.isdigit() else part for part in path.split('/'))
    return [r for r in rows if any(q == '' or normalized(q) == r['field_path'] or
        normalized(q).startswith(r['field_path'] + '/') or r['field_path'].startswith(normalized(q) + '/') for q in paths)] + [
        dict(field_path=p, description=RULE) for p in paths if 'definition_refs' in p]
