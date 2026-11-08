"""Opt-in exact schedule diagnostic for nonnegative finite downtime hours.

Post-experiment domain correction only. The frozen v037 experiment and outputs
remain untouched. Reuses its strict schedule schema and scientific scope; reads
the model's original values without scaling, clipping, or completing missing rows.
Requires a separately reviewed time-window bound; never infers one from the
variable name. Not a Core certificate or permission for estimation.
"""
from fractions import Fraction
from itertools import product
from cfm_id_llm.orchestration_schemas import canonical_sha256
from .witness_schedule import TwoWorldScheduleV037, LICENSES, rational

def inspect_two_worlds(math, proposal, artifact, *, max_downtime_hours=None):
    """Caller must separately bind the candidate to an approved, actual Core gap."""
    out = dict(status="NOT_CHECKED", inspector_version="nonnegative-downtime-v0.38",
        outcome_value_domain="NONNEGATIVE_RATIONAL_HOURS_WITH_REVIEWED_UPPER_BOUND",
        reviewed_max_downtime_hours=max_downtime_hours,
        core_certified=False, mathematical_certificate=None,
        estimation_handoff_allowed=False, full_candidate_text_verified=False,
        independent_expert_review=False, input_sha256=canonical_sha256(math),
        candidate_sha256=canonical_sha256(proposal), artifact_sha256=canonical_sha256(artifact),
        scope="GLOBAL_COUNTEREXAMPLE_CONSTRUCTION_NOT_ANY_GIVEN_OBSERVED_LAW")
    def stop(status, reason):
        out.update(status=status, reason=reason)
        return out
    if artifact is None:
        return stop("NO_ARTIFACT", "No structured two-world schedules were supplied")
    try:
        witness = TwoWorldScheduleV037.model_validate(artifact)
    except Exception:
        return stop("INVALID_ARTIFACT", "Schedule syntax or dimensions are invalid")
    p = proposal["proposal"]
    if (p["claimed_identification"] != "NOT_POINT" or p["scope"] != "AS_REVIEWED"
            or p.get("additional_requirements") or p["target_kind"] != "FIXED_POLICY_VALUE"):
        return stop("UNSUPPORTED_SCOPE", "Only an AS_REVIEWED fixed-policy NOT_POINT construction is inspected")
    # Fail closed on stronger scientific assumptions: arithmetic alone cannot
    # establish mean sufficiency, no interference, monotonicity, etc.
    if (math.get("synthetic_hypothetical_scope") is not True
            or set(math.get("a5_admitted_names", [])) != LICENSES
            or math.get("outcome") != "downtime_hours"):
        return stop("UNSUPPORTED_SCOPE", "Scientific scope or outcome domain is outside this narrow checker")
    a4 = math.get("a4_operators", [])
    if (not a4 or any(x.get("operator") not in ("NODE_FULL_LAW", "FULL_JOINT_LAW")
                      or x.get("availability") != "SYMBOLIC_POPULATION_OPERATOR" for x in a4)
            or p["a4_used"]["source"] != "REVIEWED_OPERATOR"
            or p["a4_used"]["operator"] not in {x["operator"] for x in a4}
            or p["a4_used"]["level"] != p["a4_used"]["operator"]):
        return stop("UNSUPPORTED_SCOPE", "A4 is not the declared symbolic observable law")
    try:
        limit = rational(max_downtime_hours)
        if limit <= 0:
            raise ValueError("Positive time-window bound required")
    except (TypeError, ValueError, ZeroDivisionError):
        return stop("UNSUPPORTED_SCOPE", "A separately reviewed positive downtime-hour bound is required")
    try:
        nodes = math["node_order"]
        n = len(nodes)
        target = tuple(math["target_assignment"])
        if witness.node_order != nodes or len(target) != n or any(type(b) is not int or b not in (0, 1) for b in target):
            return stop("BINDING_MISMATCH", "Node order or target dimensions differ")
        weights = tuple(map(rational, math["target_unit_weights"]))
        if len(weights) != n or any(w < 0 for w in weights) or sum(weights) != 1:
            return stop("UNSUPPORTED_SCOPE", "Only a declared weighted population mean is inspected")
        design = math["assignment_design"]
        clusters, probs = design["clusters"], tuple(map(rational, design["cluster_probabilities"]))
        if (design["kind"] != "cluster_bernoulli_binary_v2_4" or not 1 <= len(clusters) <= 10
                or len(probs) != len(clusters) or any(not 0 < x < 1 for x in probs)
                or any(not group for group in clusters)
                or sorted(node for group in clusters for node in group) != sorted(nodes)):
            return stop("UNSUPPORTED_SCOPE", "Assignment design is outside bounded cluster-Bernoulli enumeration")
        def compile_world(w):
            default = tuple(map(rational, w.default_outcomes))
            rows = {tuple(r.assignment): tuple(map(rational, r.outcomes)) for r in w.overrides}
            # Keep received values unchanged, within independently reviewed bounds.
            if any(v < 0 or v > limit for row in [default, *rows.values()] for v in row):
                raise ValueError("Hours outside the reviewed outcome bounds")
            return lambda z: rows.get(tuple(z), default)
        world_a, world_b = map(compile_world, (witness.world_a, witness.world_b))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return stop("INVALID_INPUT", "Invalid design, target, weights, or finite rational schedule")
    rows = []
    probability_sum = Fraction()
    target_supported = False
    for draws in product((0, 1), repeat=len(clusters)):
        mapping = {node: bit for group, bit in zip(clusters, draws) for node in group}
        assignment = tuple(mapping[node] for node in nodes)
        probability = Fraction(1)
        for bit, chance in zip(draws, probs):
            probability *= chance if bit else 1-chance
        a, b = world_a(assignment), world_b(assignment)
        probability_sum += probability
        target_supported |= assignment == target
        rows.append(dict(assignment=list(assignment), probability=str(probability),
                         world_a=list(map(str, a)), world_b=list(map(str, b)), equal=a == b))
    out.update(support_rows=rows, assignments_checked=len(rows),
               support_probability_sum=str(probability_sum), target_in_support=target_supported)
    if probability_sum != 1:
        return stop("INVALID_INPUT", "Enumerated design probability is not one")
    if not all(row["equal"] for row in rows):
        return stop("OBSERVABLE_LAWS_DIFFER", "At least one positive-probability assignment has different observed outcomes")
    theta_a = sum(w*y for w, y in zip(weights, world_a(target)))
    theta_b = sum(w*y for w, y in zip(weights, world_b(target)))
    out.update(theta_a=str(theta_a), theta_b=str(theta_b), target_gap=str(theta_b-theta_a))
    if theta_a == theta_b:
        return stop("TARGETS_EQUAL", "The two proposed worlds have the same declared target")
    out["license_checks"] = dict(
        known_assignment_law="Exactly the same declared cluster law in both worlds",
        full_vector_randomization="Complete schedules are deterministic, hence independent of random assignment",
        consistency="Observed outcomes are evaluated at each realized full assignment",
        fixed_pretreatment_network="The input graph is held fixed in both worlds",
        finite_conditional_first_moments="All entries are finite nonnegative rational hours within the reviewed bound")
    return stop("PASSED_EXACT_CONSTRUCTION",
                "The supplied schedules have equal observable laws and distinct declared target values within this restricted synthetic scope")

