"""Documentation pointers stay aligned with maintained capabilities, not routing."""
import json
from pathlib import Path
from cfm_id import capability_registry as registry

ROOT=Path(__file__).resolve().parents[1]


def test_mathematical_navigation_covers_registered_routes_and_methods():
    data=json.loads((ROOT/'literature_support/mathematical_contracts.json').read_text('utf8'))
    assert data['role']=='NON_EXECUTABLE_NAVIGATION_NOT_A_BUSINESS_TAXONOMY'
    assert data['runtime_coverage_authority']=='cfm_id.capability_registry.inventory'
    routes=[r for e in data['entries'] for r in e['native_route_ids']]
    methods=[r for e in data['entries'] for r in e['business_method_ids']]
    assert len(set(routes))==len(routes) and len(set(methods))==len(methods)
    expected={r for e in registry.separate_entries() for r in e['route_ids']}|{r.capability.route_id for r in registry.registrations()}
    assert set(routes)==expected
    assert set(methods)=={m.method_id for b in registry.business_bindings() for m in b.methods}
    for entry in data['entries']:
        for field in ('mathematical_documents','implementation_files','literature_maps'):
            for name in entry[field]:
                path=(ROOT/name).resolve()
                assert path.is_relative_to(ROOT) and path.is_file(),name


def test_literature_catalog_does_not_duplicate_current_runtime_status():
    folder=ROOT/'literature_support';catalog=json.loads((folder/'catalog.json').read_text('utf8'))
    assert catalog['runtime_coverage_authority']=='cfm_id.capability_registry.inventory'
    sources={s['id'] for s in catalog['source_cards']}
    for r in catalog['route_maps']:
        assert 'development_status' not in r and r['runtime_status_is_not_declared_here'] is True
        path=folder/r['file'];data=json.loads(path.read_text('utf8'))
        assert data['runtime_coverage_authority']==catalog['runtime_coverage_authority']
        if 'literature_scope' in data:
            assert set(data['literature_scope']['source_ids'])<=sources
    route=json.loads((folder/'routes/network_r2_policy_difference.json').read_text('utf8'))
    for key in ('derivation_path','single_endpoint_derivation_path'):
        assert (folder/'routes'/route['theorem'][key]).resolve().is_file()
    assert route['production_admission'] is False
