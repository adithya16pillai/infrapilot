"""Engine tests (PRD Section 10).

The golden values here were produced by running the engine against the seed
city, not derived by hand. They exist to make the demo unsurprisable: if a
seed-data edit moves these numbers, the test fails before the stage does.
"""

from __future__ import annotations

import pytest

from app.engine.cascade import run_cascade
from app.engine.metrics import graph_metrics
from app.engine.mutations import apply_mutation
from app.engine.scoring import resilience_score
from seed.calibrate import build_graph

# Frozen from `python -m seed.calibrate` against the seed city.
BASELINE_SCORE = 84
CONTROL_CENTRE_SCORE_AFTER = 43


@pytest.fixture
def graph():
    return build_graph()


def test_baseline_score_is_golden(graph):
    """The city starts at 84 -- posture debt, not a perfect 100."""
    statuses = {aid: a["status"] for aid, a in graph["assets"].items()}
    assert resilience_score(graph["assets"], statuses) == BASELINE_SCORE


def test_cascade_determinism(graph):
    """Same input -> identical output, twice. compute_ms is the only variance."""
    first = run_cascade(graph, ["control_centre"])
    second = run_cascade(graph, ["control_centre"])
    first.pop("compute_ms")
    second.pop("compute_ms")
    assert first == second


def test_cascade_does_not_mutate_input(graph):
    """The engine is pure -- callers can reuse a graph snapshot safely."""
    before = {aid: a["status"] for aid, a in graph["assets"].items()}
    run_cascade(graph, ["control_centre"])
    after = {aid: a["status"] for aid, a in graph["assets"].items()}
    assert before == after


def test_cascade_control_centre(graph):
    """Golden test for the demo scenario -- ransomware on the Control Centre."""
    result = run_cascade(graph, ["control_centre"])

    assert result["failed"] == ["control_centre", "substation_a", "traffic_mgmt"]
    # Newly degraded by this attack (excludes pre-existing posture debt).
    newly_degraded = [a for a in result["newly_impacted"] if a not in result["failed"]]
    assert newly_degraded == ["emergency_services", "hospital", "water_treatment"]

    assert result["resilience_score_before"] == BASELINE_SCORE
    assert result["resilience_score_after"] == CONTROL_CENTRE_SCORE_AFTER
    assert result["blast_radius"] == 6
    assert result["critical_path"] == ["control_centre", "substation_a", "traffic_mgmt"]
    assert result["compute_ms"] < 3000  # F3: well inside the 3s budget


def test_population_impact_never_exceeds_city(graph):
    """Overlapping `population_served` figures must not inflate the headline."""
    from app.engine.cascade import CITY_POPULATION

    for seed in graph["assets"]:
        result = run_cascade(graph, [seed])
        assert 0 <= result["estimated_population_impact"] <= CITY_POPULATION


def test_no_cascade_isolated_node(graph):
    """Backup Generator supplies only the Hospital, below its threshold."""
    result = run_cascade(graph, ["backup_generator"])
    assert result["failed"] == ["backup_generator"]
    assert result["newly_impacted"] == ["backup_generator"]
    assert result["blast_radius"] == 1


def test_spof_detection(graph):
    """Control Centre is a true articulation point of the dependency network."""
    metrics = graph_metrics(graph)
    assert "control_centre" in metrics["single_points_of_failure"]
    # And it is also the highest-throughput node by betweenness.
    assert metrics["importance_ranking"][0]["asset_id"] == "control_centre"


def test_metrics_shape(graph):
    metrics = graph_metrics(graph)
    assert metrics["node_count"] == 12
    assert metrics["edge_count"] == 18
    assert metrics["dependency_types"] == ["comms", "operational", "power"]


def test_degraded_seed_still_propagates(graph):
    """Seeding an already-degraded asset escalates it to failed."""
    result = run_cascade(graph, ["telecom_hub"])
    assert "telecom_hub" in result["failed"]
    assert "emergency_services" in result["failed"]


def test_unknown_seed_is_ignored_not_crashing(graph):
    result = run_cascade(graph, ["atlantis"])
    assert result["seed_assets"] == []
    assert result["resilience_score_after"] == BASELINE_SCORE


def test_mutation_is_non_destructive(graph):
    """apply_mutation returns a copy; the original graph is untouched."""
    original_edges = len(graph["dependencies"])
    mutated = apply_mutation(
        graph,
        {
            "operations": [
                {
                    "op": "remove_edge",
                    "source": "control_centre",
                    "target": "substation_a",
                    "dependency_type": "operational",
                }
            ]
        },
    )
    assert len(graph["dependencies"]) == original_edges
    assert len(mutated["dependencies"]) == original_edges - 1


def test_severing_exploited_edge_improves_score(graph):
    """Removing the operational link the cascade exploits demonstrably helps."""
    baseline = run_cascade(graph, ["control_centre"])["resilience_score_after"]
    hardened = apply_mutation(
        graph,
        {
            "operations": [
                {
                    "op": "remove_edge",
                    "source": "control_centre",
                    "target": "substation_a",
                    "dependency_type": "operational",
                }
            ]
        },
    )
    improved = run_cascade(hardened, ["control_centre"])["resilience_score_after"]
    assert improved > baseline
