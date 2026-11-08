"""Offline route acceptance scaffold; not a router, proof checker or approval API.

Each new theorem supplies its own adapter, independent references and verifier.
Passing this scaffold never registers a route or authorizes production inputs.
"""
from dataclasses import dataclass
from fractions import Fraction
from copy import deepcopy
from typing import Any, Protocol, Iterable
import json
from pathlib import Path


@dataclass(frozen=True)
class AcceptanceCase:
    name: str
    payload: Any
    expected_state: str
    expected_interval: tuple[str, str] | None = None
    expected_informative: bool | None = None
    # This scaffold initially accepts POINT or proved sharp intervals only.
    # Outer bounds need a distinct contract and validity tests; never mark sharp.
    expected_sharp: bool | None = None


class PartialExtensionAdapter(Protocol):
    route_id: str
    def cases(self) -> Iterable[AcceptanceCase]: ...
    def prepare(self, case: AcceptanceCase) -> dict: ...
    def run(self, case: AcceptanceCase) -> dict: ...
    def certificate(self, result: dict) -> dict | None: ...
    def replay(self, case: AcceptanceCase, certificate: dict) -> bool: ...
    def tamper(self, case: AcceptanceCase, certificate: dict) -> Iterable[tuple[str, dict]]: ...


def require(condition, code):
    if not condition:
        raise ValueError(code)


def evaluate(adapter: PartialExtensionAdapter):
    """Exercise an explicitly supplied offline adapter; do not discover plugins."""
    rows=[];names=set()
    for case in adapter.cases():
        require(case.name not in names,'DUPLICATE_CASE_NAME');names.add(case.name)
        prepared=adapter.prepare(case)
        require(prepared.get('state') not in ('POINT','PARTIAL','CORE_POINT'),'PREPARE_PUBLISHED_RESULT')
        require(not any(prepared.get(k) for k in
            ('core_called','bounded_backend_called','scientific_approval','production_admission','estimation_handoff_allowed')),
            'PREPARE_CROSSED_APPROVAL_BOUNDARY')
        result=adapter.run(case)
        require(result.get('state')==case.expected_state,'UNEXPECTED_RESULT_STATE:'+case.name)
        require(result.get('production_admission') is False,'PRODUCTION_ADMISSION_FORBIDDEN')
        require(result.get('estimation_handoff_allowed') is False,'ESTIMATION_HANDOFF_FORBIDDEN')
        cert=adapter.certificate(result);replayed=False;tamper_names=[]
        if case.expected_interval is not None:
            require(case.expected_state in ('POINT','PARTIAL'),'INTERVAL_STATE_MISMATCH')
            require(type(cert) is dict,'MISSING_CERTIFICATE')
            require(result.get('bounded_certificate_replayed') is True,'SUBMISSION_REPLAY_NOT_CONFIRMED')
            lower,upper=map(Fraction,case.expected_interval)
            require(lower<=upper,'INVALID_REFERENCE_INTERVAL')
            require((lower==upper)==(case.expected_state=='POINT'),'REFERENCE_STATUS_MISMATCH')
            require((cert.get('lower'),cert.get('upper'))==case.expected_interval,'REFERENCE_INTERVAL_DISAGREES')
            require(cert.get('status')==case.expected_state,'CERTIFICATE_STATUS_DISAGREES')
            require(cert.get('sharp') is case.expected_sharp and case.expected_sharp is True,
                    'SHARPNESS_NOT_CERTIFIED_BY_THIS_SCAFFOLD')
            require(cert.get('informative') is case.expected_informative,'INFORMATIVENESS_DISAGREES')
            require(adapter.replay(case,deepcopy(cert)) is True,'INDEPENDENT_REPLAY_FAILED')
            replayed=True
            for name,forged in adapter.tamper(case,deepcopy(cert)):
                require(name not in tamper_names,'DUPLICATE_TAMPER');tamper_names.append(name)
                require(forged!=cert,'TAMPER_DID_NOT_CHANGE_CERTIFICATE')
                require(adapter.replay(case,forged) is False,'FORGERY_ACCEPTED:'+name)
            require(len(tamper_names)>=3,'INSUFFICIENT_ADVERSARIAL_CERTIFICATE_CASES')
        else:
            require(case.expected_state in ('NEEDS_INPUT','REVIEW_REQUIRED','UNSUPPORTED','INCOMPATIBLE','CHECK_BLOCKED'),
                    'EXPLICIT_NON_IDENTIFICATION_GATE_STATE_REQUIRED')
            require(cert is None and not result.get('bounded_certificate_replayed'),'BLOCKED_CASE_PUBLISHED_CERTIFICATE')
            require(not result.get('bounded_backend_called'),'BLOCKED_CASE_RAN_BOUNDED_SOLVER')
        rows.append(dict(case=case.name,state=result['state'],passed=True,
            exact_interval=case.expected_interval,sharp=case.expected_sharp,
            informative=case.expected_informative,independent_replay=replayed,
            forged_certificates_rejected=tamper_names))
    require(rows,'EMPTY_ACCEPTANCE_SUITE')
    return dict(route=adapter.route_id,status='PASS',cases=len(rows),rows=rows,
        http_calls=0,llm_accuracy_measured=False,route_registered=False,scientific_approval=False,
        production_admission=False,scope='Offline developer acceptance only; theorem and verifier independence require separate review.')


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    # A named, explicit reference only. Never import arbitrary user-supplied code.
    from examples.partial_extension_reference import BoundedPolicyReference
    report=evaluate(BoundedPolicyReference())
    with Path(args.output).open('x',encoding='utf8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:report[k] for k in ('route','status','cases','http_calls','route_registered')},ensure_ascii=False))

if __name__=='__main__':
    main()

