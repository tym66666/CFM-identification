"""Explicit synthetic fixtures for compatibility acceptance, never runtime approval.

These fixtures reuse independently declared examples. They are not model reads
or production science reviews and must not be imported by runtime adapters.
"""
from copy import deepcopy
import json
from pathlib import Path

from cfm_id import intent_submission
from cfm_id.serialization import canonical_hash
from cfm_id.workflows.legacy_network import core_peers_staged_base
from examples import nbib_d1_fixture, nbib_d2_fixture, nbib_arm_fixture, nbib_core_peers_fixture
from examples.intent_routes_fixture import reviewed_submission


def make_case(kind):
    modules = {'d1': nbib_d1_fixture, 'd2': nbib_d2_fixture,
               'cluster': nbib_arm_fixture, 'peers': nbib_core_peers_fixture}
    module = modules[kind]
    item = deepcopy(module.load_case())
    bundle = item['bundle']
    envelope = None
    entry = {'d1': 'D1_EFFECTS', 'd2': 'D2_ARM', 'cluster': 'CLUSTER_ARM',
             'peers': 'STAGED_CORE_PEERS'}[kind]
    if kind == 'd2':
        kit = Path(__file__).resolve().parents[1] / 'examples/legacy/business_extension'
        read = lambda p: json.loads((kit / p).read_text(encoding='utf8'))
        bundle = read('public/positive_bundle.json')
        envelope = read('recorded/study_envelope.json')
        wire = read('recorded/positive_candidate.json')
        item['packet']['bundle_sha256'] = canonical_hash(bundle)
    else:
        wire = deepcopy(item['raw'])
        if kind == 'cluster':
            for q in wire['questions'].values():
                source = q.pop('remaining_source')
                quote = q.pop('remaining_evidence_span')
                q['remaining'] = dict(rule='原抽签条件平均' if source else '未确定', source=source, quote=quote)
        if kind == 'peers':
            envelope = core_peers_staged_base.bind_study(bundle, {'study': wire.pop('study')})
        for qid, q in wire['questions'].items():
            q['peer_evidence'] = {side: bundle['question_slots'][qid] if q.get(side) else None
                                  for side in ('first', 'second')}
    raw = deepcopy(wire)
    raw['intents'] = {}
    for qid, q in raw['questions'].items():
        kind_name = {'水平': '水平', '差值': '比较', '选最优': '选最优', '不明确': '不明确'}[q.pop('operation')]
        raw['intents'][qid] = dict(kind=kind_name, quote=bundle['question_slots'][qid])
    item.update(bundle=bundle, raw=intent_submission.reviewed_projection(bundle, raw, entry, envelope))
    context = module.synthetic_context(item)
    packet = item['packet']
    review = reviewed_submission(bundle, raw, entry, packet, context, envelope)
    return dict(bundle=bundle, raw=raw, entry=entry, envelope=envelope,
                packet=packet, context=context, review=review)
