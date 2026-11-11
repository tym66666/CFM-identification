from fractions import Fraction
import pytest

from pfn_pipeline._internal.identification.randomized_arm_family.assignment_extensions import (
    UnequalProbabilityFixedQuotaDesign,
    RerandomizedBalancedDesign,
)


def test_unequal_fixed_quota_enumerates_zero_mass_and_exact_probabilities():
    d = UnequalProbabilityFixedQuotaDesign(
        nodes=("a", "b", "c", "d"), m=2,
        assignment_probabilities={"1100": "1/2", "0011": "1/3", frozenset({"a", "c"}): "1/6"},
    )
    table = d.probability_table()
    assert len(table) == 6
    assert table[frozenset({"a", "b"})] == Fraction(1, 2)
    assert table[frozenset({"a", "d"})] == 0
    assert sum(table.values(), Fraction(0)) == 1
    assert d.assignment_probability({"a", "b", "c"}) == 0


def test_unit_weights_normalize_to_unequal_quota():
    d = UnequalProbabilityFixedQuotaDesign(
        nodes=("a", "b", "c"), m=2,
        unit_weights={"a": 1, "b": 2, "c": 3},
    )
    table = d.probability_table()
    assert table[frozenset({"b", "c"})] == Fraction(6, 11)
    assert sum(table.values(), Fraction(0)) == 1


def test_rerandomization_conditions_on_balance_event():
    base = UnequalProbabilityFixedQuotaDesign(
        nodes=("a", "b", "c", "d"), m=2,
        assignment_probabilities={
            frozenset({"a", "b"}): Fraction(1, 2),
            frozenset({"a", "c"}): Fraction(1, 4),
            frozenset({"b", "d"}): Fraction(1, 4),
        },
    )
    balanced = RerandomizedBalancedDesign(base, lambda treated: "a" in treated)
    assert balanced.balance_probability == Fraction(3, 4)
    assert balanced.assignment_probability({"a", "b"}) == Fraction(2, 3)
    assert balanced.assignment_probability({"b", "d"}) == 0
    assert sum(balanced.probability_table().values(), Fraction(0)) == 1


def test_zero_probability_balance_event_rejected():
    base = UnequalProbabilityFixedQuotaDesign(
        nodes=("a", "b"), m=1,
        assignment_probabilities={frozenset({"a"}): 1},
    )
    with pytest.raises(ValueError, match="zero probability"):
        RerandomizedBalancedDesign(base, lambda treated: "b" in treated)
