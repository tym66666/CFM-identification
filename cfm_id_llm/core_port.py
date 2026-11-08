"""Tiny version-independent port to the user's separately evolving ID Library.

CorePort methods represent *trusted local integration code*, never untrusted LLM data.
No production adapter is shipped in Gateway 0.2.0. A production implementation
MUST call the actual theorem verifier on the exact binding prior to returning PASS.
"""
from __future__ import annotations
from typing import Literal, Protocol, runtime_checkable
from .orchestration_schemas import (
    ConfirmedProblemV02, CoreCapabilitiesV02, CoreDecisionV02, CoreReplayV02,
)


@runtime_checkable
class CoreIdentificationPort(Protocol):
    @property
    def mode(self) -> Literal["MOCK", "PRODUCTION"]: ...

    def describe_capabilities(self) -> CoreCapabilitiesV02: ...

    def identify(self, problem: ConfirmedProblemV02) -> CoreDecisionV02: ...

    def replay_verify(self, problem: ConfirmedProblemV02, result: CoreDecisionV02) -> CoreReplayV02: ...
