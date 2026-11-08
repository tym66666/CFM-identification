"""Offline test double. Even a passing mock replay NEVER yields math certification."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field
from .schemas import StrictModel
from .orchestration_schemas import (
    ConfirmedProblemV02, CoreCapabilitiesV02, CoreDecisionV02, CoreReplayV02,
)


class MockCoreScenario(StrictModel):
    status: Literal[
        "POINT", "PARTIAL", "NOT_POINT", "NO_USEFUL_ID", "NEEDS_INPUT",
        "UNSUPPORTED", "NO_ADAPTER", "INCOMPATIBLE", "ERROR",
    ]
    route_id: str | None = None
    identified_expression: str | None = None
    certificate: dict[str, Any] | None = None
    reason: str = "Mock Core result — no theorem executed"
    missing_requirements: list[str] = Field(default_factory=list)
    replay_accept: bool = True
    # For negative testing a faulty backend that mixes problem identities.
    corrupt_problem_binding: bool = False
    corrupt_replay_binding: bool = False
    corrupt_replay_decision_binding: bool = False


class MockCorePort:
    """Simulates core responses; never claims to execute R1a/R1b/R2."""
    mode: Literal["MOCK"] = "MOCK"

    def __init__(self, scenario: MockCoreScenario):
        self.scenario = scenario
        self.identify_calls = 0
        self.replay_calls = 0

    def describe_capabilities(self) -> CoreCapabilitiesV02:
        return CoreCapabilitiesV02(
            adapter_id="mock-core-v02", library_version="NOT_CONNECTED",
            available_routes=["DEMO_R1A", "DEMO_R1B", "DEMO_R2"],
            description="Simulated replies for routing tests; not an actual identification library",
        )

    def identify(self, problem: ConfirmedProblemV02) -> CoreDecisionV02:
        self.identify_calls += 1
        digest = "0" * 64 if self.scenario.corrupt_problem_binding else problem.fingerprint()
        return CoreDecisionV02(
            status=self.scenario.status,
            problem_sha256=digest,
            route_id=self.scenario.route_id,
            identified_expression=self.scenario.identified_expression,
            certificate=self.scenario.certificate,
            reason=self.scenario.reason,
            missing_requirements=self.scenario.missing_requirements,
        )

    def replay_verify(self, problem: ConfirmedProblemV02, result: CoreDecisionV02) -> CoreReplayV02:
        self.replay_calls += 1
        digest = "0" * 64 if self.scenario.corrupt_replay_binding else problem.fingerprint()
        return CoreReplayV02(
            accepted=self.scenario.replay_accept,
            problem_sha256=digest,
            decision_sha256="0" * 64 if self.scenario.corrupt_replay_decision_binding else result.fingerprint(),
            verifier_id="mock-replay-only",
            details="This is a fixture replay, not independent mathematical verification",
        )
