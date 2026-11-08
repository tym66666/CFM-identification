"""Explicit synthetic acceptance only. Never imported by the session runtime."""
from copy import deepcopy
import argparse,json
from pathlib import Path
from cfm_id import research_session as session
from cfm_id import session_routes as routes


def network(name='cold_chain'):
    from examples.reading_science_fixture import DATA,public_bundle,synthetic_context
    refs=json.loads((DATA/'references/labels.json').read_text('utf8'))
    b=public_bundle(name);candidate=deepcopy(refs[name]['reading'])
    native=None
    if name=='cold_chain':
        packet,context,review=synthetic_context(name,b,candidate)
        native=dict(packet=packet,context=context,submission_review=review)
    return routes.NETWORK,b,candidate,native


def mean_order(**case_options):
    from examples.mean_order_business_fixture import make_case,endpoint_reviews,business_review
    from evaluation.mean_order_factored_reading import reference_wire,to_canonical
    from evaluation.mean_order_factored_review import ReviewedFactoredReading,worksheet
    c=make_case(**case_options);wire=reference_wire(c['bundle'],c['expected_candidate'])
    canonical=to_canonical(c['bundle'],wire);chain=endpoint_reviews(c,canonical)
    legacy=business_review(c,canonical,chain)
    full=ReviewedFactoredReading(**worksheet(c['bundle'],wire,legacy_review=legacy),
        reviewer='Independent synthetic reference reviewer',evidence='Full source and semantic reference checked in a separate hypothetical protocol',
        reviewed_full_wire_semantics_and_sources=True,reviewed_projection_and_losses=True,synthetic_fixture=True)
    chain.pop('synthetic_protocol_selected')
    return routes.MEAN_ORDER,c['bundle'],wire,dict(chain,science=c['science'],review=legacy,factored_review=full)


def dag(index=0):
    from examples.dag_frontdoor_business_reference import cases
    from cfm_id.dag_business import inspect_candidate,reading_contract,route_contract
    c=cases()[index];lane=c['route_id'];b=c['bundle'];wire=c['reference']
    view=inspect_candidate(b,wire,route_id=lane)
    if view['state']!='REVIEW_REQUIRED':return lane,b,wire,None
    common=dict(reviewer='Independent synthetic reference reviewer',evidence='Frozen hypothetical causal graph, target and population conditions independently stipulated.',authority='SYNTHETIC_TEST')
    sheet=view['reading_worksheet'];science=view['science_worksheet']
    reading=reading_contract(lane)[2](**{k:v for k,v in sheet.items() if k!='is_approval' and k!='decisions'},
        **common,decisions={k:'ACCEPTED' for k in sheet['decisions']})
    science_type=route_contract(lane)[1]
    # The original worksheet enumerates the native science obligations.
    review=science_type(**{k:v for k,v in science.items() if k not in ('is_approval','decisions')},
                       **common,decisions={k:'ACCEPTED' for k in science['decisions']})
    return lane,b,wire,dict(reading_review=reading,science_review=review)


def approve(s,native):
    sheet=session.review_worksheet(s,native_submission=native)
    return session.record_review(s,dict(binding_sha256=sheet['binding_sha256'],
        native_submission_sha256=sheet['native_submission_sha256'],
        reviewer='Independent synthetic session reviewer',evidence='Explicitly selected synthetic reference; not real-world scientific approval.',
        decisions={k:'ACCEPTED' for k in session.DECISIONS}))


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);rows=[]
    for name,factory,expected in [('network',network,'POINT'),('partial',mean_order,'PARTIAL'),
                                  ('dag',dag,'POINT'),('missing',lambda:network('convenience_stores'),'NEEDS_INPUT')]:
        lane,b,wire,native=factory();s=session.start(lane,b)
        session.save(s,output/(name+'_materials.json'))
        s=session.receive_candidate(s,wire)
        session.write_json(output/(name+'_inspection.json'),session.inspect(s))
        if native is not None:s=approve(s,native)
        session.save(s,output/(name+'_reviewed.json'))
        restored=session.restore(output/(name+'_reviewed.json'))
        without=session.execute(restored,research_protocol_selected=True)
        assert without['mathematical_claim'] is None and not without['backend_called']
        result=session.execute(restored,native_submission=native,research_protocol_selected=True)
        assert result['state']==expected,(name,result['state'],result.get('reason_code'))
        assert result['independent_replay']==(native is not None)
        session.write_json(output/(name+'_result.json'),result)
        rows.append(dict(name=name,state=result['state'],independent_replay=result['independent_replay'],
                         restore_without_native_reviews_cannot_publish=True))
    summary=dict(passed=True,cases=rows,api_calls=0,synthetic_only=True,production_admission=False)
    session.write_json(output/'SUMMARY.json',summary);return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--allow-synthetic-reviews',action='store_true');a=p.parse_args(argv)
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic protocol selection is required')
    print(json.dumps(run(a.output),ensure_ascii=False))


if __name__=='__main__':main()
