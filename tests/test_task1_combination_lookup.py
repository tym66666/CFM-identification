"""The Task-1 combination lookup table is reproducible and its key checks pass."""
from fractions import Fraction

import examples.generate_task1_combination_lookup as gen


def test_key_lookup_checks_pass():
    checks = gen.key_lookup_checks()
    assert checks["sum_to_one"] is True
    assert checks["all_nonneg"] is True
    assert checks["conditional_normalized"] is True
    # D7 x E1, node a: P(T_a=1, S_a=0) = 1/2 + 1/4 = 3/4.
    assert Fraction(checks["joint_a1"]) == Fraction(3, 4)


def test_support_matrix_d7_e1_hand_checked():
    rows = dict(gen.build_support_matrix())
    # D7 x E1: for own=0 only {c,d} (S=0); for own=1 {a,b},{a,c} (S=0).
    assert rows["D7"][0] == "a=0:{0}; a=1:{0}"


def test_support_matrix_d5_node_a_always_treated():
    rows = dict(gen.build_support_matrix())
    # D5 puts node a in a singleton stratum with quota 1 -> T_a=1 deterministically.
    assert rows["D5"][0] == "a=1:{0}"


def test_render_is_deterministic():
    assert gen.render() == gen.render()


def test_policy_rows_hand_checked():
    rows = {dlabel: (mean, contrast) for dlabel, mean, contrast in gen.build_policy_rows()}
    # D2 uniform m=2 -> E[2|A|] = 4; D5 total quota 3 -> E[2|A|] = 6.
    assert rows["D2"][0].startswith("POINT (4)")
    assert rows["D5"][0].startswith("POINT (6)")
