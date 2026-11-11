"""Task 1 small-network walkthrough (one runnable representative example).

Three parts, following the task's progression:

  Part 0  hand calculation of an unequal-probability fixed-quota law: every
          legal pilot list and its probability, the impossible vectors (0),
          and each node's marginal selection probability;
  Part A  new assignment designs (unequal / rerandomized) with an existing
          exposure, cross-checked against the independent oracle;
  Part B  existing designs with the new weighted / grouped exposures,
          cross-checked against the independent oracle.

Formal identification/certificates are exercised elsewhere:
``examples/task1_business_case_reference.py`` (full business dispatch) and
``examples/network_design_exposure_reference.py`` (D1-D8 x E1-E5 x four
families). This file is the step-by-step handle on the design/exposure laws and
the independent support oracle.

Run:
    python -m examples.task1_walkthrough
"""
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1)
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family.assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign, RerandomizedBalancedDesign)
from pfn_pipeline._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)
from pfn_pipeline._internal.identification.randomized_arm_family.support import SupportEngine
from pfn_pipeline._internal.identification.randomized_arm_family.support_verifier import verify_joint_support


NODES = ("a", "b", "c", "d")
M = 2
# Declared (unequal) probabilities of the legal size-m pilot lists.
DECLARED = {
    frozenset(("a", "b")): Fraction(1, 2),
    frozenset(("a", "c")): Fraction(1, 4),
    frozenset(("c", "d")): Fraction(1, 4),
}
NET = NetworkExposureSpec(network_id="fixture", node_ids=list(NODES),
                          undirected_edges=[("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])


def hand_calculation():
    print("== Part 0: hand calculation of the unequal fixed-quota law ==")
    rows = [(frozenset(s), DECLARED.get(frozenset(s), Fraction(0)))
            for s in combinations(NODES, M)]
    print("所有合法试点名单及概率：")
    for treated, probability in rows:
        print(f"  {''.join(sorted(treated))}: {probability}")
    total = sum((p for _, p in rows), Fraction(0))
    print(f"  概率总和: {total}")
    assert total == 1, "legal-list probabilities must sum to 1"
    print("不可能的处理向量（处理数 != m -> 概率 0）：")
    for bits in product((0, 1), repeat=len(NODES)):
        treated = frozenset(n for n, b in zip(NODES, bits) if b)
        if len(treated) != M:
            print(f"  {bits} -> 处理数={len(treated)}, 概率=0")
    print("每家店被选中的边际概率：")
    for node in NODES:
        print(f"  P({node} 被选中) = {sum((p for treated, p in rows if node in treated), Fraction(0))}")


def check(design, exposure, node_id="a"):
    assignment = design if isinstance(design, AssignmentSpec) else AssignmentSpec(design)
    joint = SupportEngine.joint_support(network=NET, assignment=assignment, exposure=exposure, node_id=node_id)
    report = verify_joint_support(network=NET, design=assignment, exposure=exposure,
                                  node_id=node_id, proposed=joint)
    print(f"  P(T_{node_id}=a, S_{node_id}=s) = {joint}")
    print(f"  independent check: {'PASS' if report['ok'] else 'FAIL ' + str(report['mismatch'])}")


def main():
    hand_calculation()

    base = UnequalProbabilityFixedQuotaDesign(
        nodes=NODES, m=M, assignment_probabilities=dict(DECLARED))
    balanced = RerandomizedBalancedDesign(base, lambda t: "a" in t)
    print("\n== Part A1: unequal fixed quota + E1 ==")
    check(base, ExposureSpec("strict_majority_ties_low"))
    print("== Part A2: unequal fixed quota + E4 ==")
    check(base, ExposureSpec("exact_treated_neighbor_count"))
    print("== Part A3: rerandomized + E1 ==")
    check(balanced, ExposureSpec("strict_majority_ties_low"))
    print("== Part A4: rerandomized + E4 ==")
    check(balanced, ExposureSpec("exact_treated_neighbor_count"))

    d2 = AssignmentSpec(CompleteRandomizationDesignV1(m=2))
    d1 = AssignmentSpec(HeterogeneousBernoulliDesignV1(propensities={n: "1/2" for n in NODES}))
    print("== Part B1: existing D2 + weighted exposure (sum) ==")
    check(d2, WeightedExposureSpec(weights={"b": 1, "c": 2}, mode="sum"))
    print("== Part B2: existing D1 + weighted exposure (proportion) ==")
    check(d1, WeightedExposureSpec(weights={"b": 1, "c": 2}, mode="proportion"))
    print("== Part B3: existing D2 + grouped exposure ==")
    check(d2, GroupedExposureSpec(groups={"friend": ("b",), "colleague": ("c",)}))
    print("== Part B4: existing D1 + grouped exposure ==")
    check(d1, GroupedExposureSpec(groups={"friend": ("b",), "colleague": ("c",)}))


if __name__ == "__main__":
    main()
