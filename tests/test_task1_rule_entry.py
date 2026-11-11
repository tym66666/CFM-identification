"""rule.py is the formal identification entry (forwards identify + replay)."""
from pfn_pipeline.identification import make_unequal_probability_fixed_quota_arm_task
from pfn_pipeline._internal.identification.schemas import UnequalProbabilityFixedQuotaDesignV1
from pfn_pipeline._internal.identification.randomized_arm_family import rule

NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]


def _task(**kw):
    net = dict(network_id="f", node_ids=NODES, undirected_edges=EDGES)
    design = UnequalProbabilityFixedQuotaDesignV1(
        nodes=tuple(NODES), m=2, unit_weights={"a": "2", "b": "1", "c": "1", "d": "1"})
    return make_unequal_probability_fixed_quota_arm_task(
        net, design=design, node_id="a", own_treatment_value=1,
        source="s", evidence="e", admitted=True, synthetic=True,
        query_authority="TRUSTED_FIXTURE", **kw)


def test_rule_identify_points_to_formal_certificate():
    result = rule.identify(_task(exposure_value=0))
    assert result.result["status"] == "POINT"
    assert result.result["verification_status"] == "VERIFIED"
    assert result.result["certificate"] is not None


def test_rule_replay_reverifies():
    result = rule.identify(_task(exposure_value=0))
    assert rule.replay(result).verification_status == "VERIFIED"


def test_rule_identify_supports_weighted_exposure():
    result = rule.identify(_task(exposure_definition="weighted_exposure_sum",
                                 exposure_value="1", exposure_weights={"b": "1", "c": "2"}))
    assert result.result["status"] == "POINT"
    assert result.result["verification_status"] == "VERIFIED"
