"""Program-owned short source aliases, shared by fact-reading contracts."""
from copy import deepcopy
from hashlib import sha256
import json
from cfm_id.source_locations import build_catalog


def catalog(bundle, documents, *, binding, version):
    if type(binding) is not str or not binding:
        raise ValueError('QUERY_REFERENCE_BINDING_REQUIRED')
    original = build_catalog(documents)
    if len(original) > 9999:
        raise ValueError('QUERY_SOURCE_CATALOG_LIMIT')
    payload = dict(version=version, bundle=bundle, binding=binding, catalog=original)
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()
    return dict(context='c'+digest[:12], context_sha256=digest,
                aliases={f's{i:04d}':row for i,row in enumerate(original.values(),1)})


def expand(value, references):
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            if key.endswith('source_ids'):
                if len(set(child)) != len(child) or any(x not in references['aliases'] for x in child):
                    raise ValueError('UNKNOWN_OR_DUPLICATE_SHORT_SOURCE')
                out[key] = [references['aliases'][x]['source_id'] for x in child]
            else:
                out[key] = expand(child, references)
        return out
    if isinstance(value, list):
        return [expand(v,references) for v in value]
    return deepcopy(value)


def definition_evidence(candidate, definitions, uses, *, record_path, aliases):
    """Resolve only explicit definition links; a wildcard stays in this table.

    The resolver checks structure and source identity, never source entailment.
    Existing absolute definition paths keep exactly the same receipt shape.
    """
    if type(uses) is not list or len(set(uses)) != len(uses):
        raise ValueError('UNIQUE_EXPLICIT_DEFINITIONS_REQUIRED')
    result = {}
    context = record_path.split('/')[1:]
    for name in uses:
        if name not in definitions:
            raise ValueError('UNREGISTERED_DEFINITION_DEPENDENCY')
        definition = deepcopy(definitions[name]);parts = definition['path'].split('/')[1:]
        resolved = []
        for i,part in enumerate(parts):
            if part == '*':
                if i >= len(context) or not context[i].isdigit() or resolved != context[:i]:
                    raise ValueError('DEFINITION_OUTSIDE_RECORD_SCOPE')
                part = context[i]
            resolved.append(part)
        origin = candidate
        for part in resolved:
            part = part.replace('~1','/').replace('~0','~')
            origin = origin[int(part)] if type(origin) is list else origin[part]
        if type(origin) is not list or not origin or any(k not in aliases for k in origin):
            raise ValueError('CITED_DEFINITION_REQUIRED')
        row = dict(definition=definition, source_ids=deepcopy(origin))
        if '*' in parts:row['resolved_path'] = '/'+'/'.join(resolved)
        result[name] = row
    return result
