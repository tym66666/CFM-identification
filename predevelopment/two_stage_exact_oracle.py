"""Research-only exact oracle for a *candidate* two-stage quota-mixture protocol.

NOT D1-D5, NOT a new registered assignment design, NOT a v2.7 backend.
The first stage draws a predeclared full quota profile u with exact mass pi(u).
The second stage independently and uniformly assigns m_h(u) of n_h units
in each pretreatment group. The first stage may correlate group quotas.

This module is deliberately separate from Production AssignmentSpec and any
identification theorem. Exhaustive full-vector enumeration is a third check
for the proposed conditional hypergeometric mixture formula on small graphs.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import comb


def _choose(n: int, k: int) -> int:
    return comb(n, k) if 0 <= k <= n else 0


@dataclass(frozen=True)
class TwoStageQuotaMixtureDraft:
    node_order: tuple[str, ...]
    groups: tuple[tuple[str, ...], ...]
    profiles: tuple[tuple[tuple[int, ...], str], ...]

    def __post_init__(self):
        if (not isinstance(self.node_order, tuple) or len(set(self.node_order)) != len(self.node_order)
                or not self.node_order or any(not isinstance(n, str) or not n for n in self.node_order)):
            raise ValueError('Explicit unique ordered nodes required')
        if not isinstance(self.groups, tuple) or len(self.groups) < 2 or any(not isinstance(g, tuple) or not g for g in self.groups):
            raise ValueError('At least two nonempty fixed pretreatment groups required')
        members = tuple(node for group in self.groups for node in group)
        if len(members) != len(self.node_order) or set(members) != set(self.node_order):
            raise ValueError('Groups must exactly partition node order')
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise ValueError('Explicit nonempty first-stage quota distribution required')
        seen = set()
        total = Fraction(0)
        for quotas, mass in self.profiles:
            if (not isinstance(quotas, tuple) or len(quotas) != len(self.groups)
                    or any(type(m) is not int or not 0 <= m <= len(g)
                           for m, g in zip(quotas, self.groups))):
                raise ValueError('Each profile needs a valid exact quota per group')
            if quotas in seen:
                raise ValueError('Duplicate first-stage quota profile')
            seen.add(quotas)
            if not isinstance(mass, str):
                raise ValueError('First-stage exact masses must be rational strings')
            p = Fraction(mass)
            if p <= 0 or str(p) != mass:
                raise ValueError('First-stage mass must be positive canonical rational')
            total += p
        if total != 1:
            raise ValueError('First-stage mass must sum exactly to one')

    def full_q(self, assignment: tuple[int, ...]) -> Fraction:
        """Unconditional q(t)=sum_u pi(u)*prod_h 1[quota] / C(n_h,m_h)."""
        if (not isinstance(assignment, tuple) or len(assignment) != len(self.node_order)
                or any(type(a) is not int or a not in (0, 1) for a in assignment)):
            raise ValueError('Binary full vector with exact node order required')
        values = dict(zip(self.node_order, assignment))
        result = Fraction(0)
        for quotas, raw_pi in self.profiles:
            if all(sum(values[n] for n in group) == m for group, m in zip(self.groups, quotas)):
                denominator = 1
                for group, m in zip(self.groups, quotas):
                    denominator *= comb(len(group), m)
                result += Fraction(raw_pi)/denominator
        return result

    def exhaustive_arm_joint(self, node: str, own: int, reference_nodes: frozenset[str]) -> tuple[Fraction, ...]:
        """Independent slow full-vector oracle for P(T_i=a,K_i=k)."""
        self._check_query(node, own, reference_nodes)
        positions = {name: i for i, name in enumerate(self.node_order)}
        result = [Fraction(0)] * (len(reference_nodes) + 1)
        for assignment in product((0, 1), repeat=len(self.node_order)):
            if assignment[positions[node]] != own:
                continue
            k = sum(assignment[positions[r]] for r in reference_nodes)
            result[k] += self.full_q(assignment)
        return tuple(result)

    def _check_query(self, node: str, own: int, refs: frozenset[str]):
        if node not in self.node_order or type(own) is not int or own not in (0, 1):
            raise ValueError('Valid target node and own treatment required')
        if not isinstance(refs, frozenset) or node in refs or not refs <= set(self.node_order):
            raise ValueError('Reference nodes must be a typed subset excluding self')

    def factorized_arm_joint(self, node: str, own: int, reference_nodes: frozenset[str]) -> tuple[Fraction, ...]:
        """Proposed grouped hypergeometric mixture for P(T_i=a,K_i=k).

        IMPORTANT: profile terms are weighted by pi(u)*P(T_i=a|u), not pi(u).
        When an own-treatment arm has zero probability, its conditional count
        law is undefined; the safe output here is an all-zero JOINT count mass.
        """
        self._check_query(node, own, reference_nodes)
        own_group = next(i for i, g in enumerate(self.groups) if node in g)
        degree = len(reference_nodes)
        result = [Fraction(0)] * (degree + 1)
        for quotas, raw_pi in self.profiles:
            n = len(self.groups[own_group])
            m = quotas[own_group]
            own_mass = Fraction(m if own else n - m, n)
            if not own_mass:
                continue
            # Conditional on T_i=own, groups are independent within profile.
            counts = [Fraction(1)]
            for j, (group, quota) in enumerate(zip(self.groups, quotas)):
                neighbors = len(reference_nodes.intersection(group))
                remaining = len(group) - int(j == own_group)
                draws = quota - (own if j == own_group else 0)
                den = _choose(remaining, draws)
                if not den:
                    raise AssertionError('Positive own_mass should imply feasible quota')
                part = [Fraction(_choose(neighbors, k) *
                                 _choose(remaining-neighbors, draws-k), den)
                        for k in range(neighbors+1)]
                nxt = [Fraction(0)] * (len(counts)+len(part)-1)
                for a, left in enumerate(counts):
                    for b, right in enumerate(part):
                        nxt[a+b] += left*right
                counts = nxt
            if len(counts) != degree+1 or sum(counts) != 1:
                raise AssertionError('Second-stage conditional distribution not normalized')
            for k, weight in enumerate(counts):
                result[k] += Fraction(raw_pi)*own_mass*weight
        return tuple(result)

    def own_probability(self, node: str, own: int) -> Fraction:
        return sum(self.factorized_arm_joint(node, own, frozenset()), Fraction(0))

    def conditional_neighbor_count(self, node: str, own: int, refs: frozenset[str]) -> tuple[Fraction, ...] | None:
        joint = self.factorized_arm_joint(node, own, refs)
        den = sum(joint)
        return tuple(p/den for p in joint) if den else None

    def all_assignments(self):
        """Small-graph oracle only; never enumerate a large network in production."""
        if len(self.node_order) > 12:
            raise ValueError('Research exhaustive enumeration limited to 12 nodes')
        return tuple((z, self.full_q(z)) for z in product((0, 1), repeat=len(self.node_order)))


def acceptance_witnesses() -> dict:
    """Exact small-graph values, no causal outcome model or POINT claims."""
    # A central node is treated with different probabilities across stage-1
    # profiles.  Conditional profile reweighting must NOT use raw pi=1/2.
    d = TwoStageQuotaMixtureDraft(
        node_order=('a', 'b', 'c', 'd'), groups=(('a','b'), ('c','d')),
        profiles=(((0,1),'1/2'), ((2,1),'1/2')))
    refs=frozenset(('b','c'))
    formula=d.factorized_arm_joint('a',1,refs)
    oracle=d.exhaustive_arm_joint('a',1,refs)
    assert formula==oracle
    assert d.own_probability('a',1)==Fraction(1,2)
    assert d.conditional_neighbor_count('a',1,refs)==(Fraction(0),Fraction(1,2),Fraction(1,2))
    assert sum(q for _,q in d.all_assignments())==1
    # Within a fixed profile, perfect quotas can eliminate arm support.
    blocked=TwoStageQuotaMixtureDraft(
        node_order=('a','b','c','d'),groups=(('a','b'),('c','d')),
        profiles=(((0,1),'1'),))
    assert blocked.own_probability('a',1)==0
    assert blocked.conditional_neighbor_count('a',1,refs) is None
    return {
        'status':'RESEARCH_ONLY_EXACT_ASSIGNMENT_ORACLE_NOT_IDENTIFICATION',
        'first_stage_profiles':[{'quota':list(q),'mass':p} for q,p in d.profiles],
        'joint_treated_neighbor_mass':[str(x) for x in formula],
        'conditional_treated_neighbor_mass':[str(x) for x in d.conditional_neighbor_count('a',1,refs)],
        'own_treatment_probability':str(d.own_probability('a',1)),
        'exact_total_assignment_mass':str(sum(p for _,p in d.all_assignments())),
        'unsupported_own_arm_conditional_law':'UNDEFINED_NOT_ZERO_PROBABILITY_CONDITIONING',
        'independent_enumeration_agrees': formula==oracle,
        'no_theorem_route_registered':True,
        'no_business_effect_estimated':True,
    }
