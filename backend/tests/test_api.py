"""API contract tests (PRD Section 10).

These run against a throwaway database so they never disturb the demo city.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A fully seeded app backed by a temporary database."""
    import app.config as config

    config.DB_PATH = tmp_path_factory.mktemp("db") / "test.db"

    import app.db as db

    db.DB_PATH = config.DB_PATH

    from app.main import app as fastapi_app
    from seed.seed import seed

    db.init_db()
    seed(reset=True)

    with TestClient(fastapi_app) as test_client:
        yield test_client


def _run(client, query: str) -> dict:
    response = client.post("/api/simulate", json={"query": query})
    assert response.status_code == 202
    sim_id = response.json()["simulation_id"]

    for _ in range(100):
        detail = client.get(f"/api/simulations/{sim_id}").json()
        if detail["status"] != "planning":
            return detail
        time.sleep(0.1)
    raise AssertionError("simulation did not complete")


def test_graph_endpoint(client):
    body = client.get("/api/graph").json()
    assert len(body["assets"]) == 12
    assert len(body["dependencies"]) == 18
    assert body["resilience_score"] == 84
    # Deterministic layout: every asset carries a fixed position (F1).
    assert all(a["position_x"] is not None for a in body["assets"])


def test_simulate_returns_quickly(client):
    """F2 AC#1: the endpoint returns an id without waiting for the agent."""
    started = time.perf_counter()
    response = client.post("/api/simulate", json={"query": "Ransomware on Control Centre"})
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 202
    assert elapsed_ms < 500


def test_unknown_asset_query(client):
    """Edge story: friendly message listing valid assets, and no cascade run."""
    detail = _run(client, "Simulate an attack on the Atlantis Sea Gate")
    assert detail["status"] == "unresolved"
    assert detail["result"] is None
    assert "could not match" in detail["summary"]
    assert "Control Centre" in detail["summary"]


def test_agent_selects_analyses(client):
    """F4 AC#2: a structural question must not run a cascade."""
    structural = _run(client, "What is our biggest single point of failure?")
    tools = [e["tool"] for e in client.get(f"/api/simulations/{structural['id']}/events").json()]
    assert "graph_metrics" in tools
    assert "run_cascade" not in tools

    incident = _run(client, "What happens if the Water Treatment Plant loses power?")
    tools = [e["tool"] for e in client.get(f"/api/simulations/{incident['id']}/events").json()]
    assert tools.count("resolve_assets") >= 1
    assert "run_cascade" in tools
    assert "rank_mitigations" in tools


def test_events_are_ordered_and_complete(client):
    detail = _run(client, "Ransomware on the Control Centre")
    events = client.get(f"/api/simulations/{detail['id']}/events").json()
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert events[-1]["type"] == "done"
    assert all(e["status"] in {"running", "done", "failed"} for e in events)


def test_recommendation_gain_is_real(client):
    """F5: every advertised gain equals the measured re-simulation delta."""
    client.post("/api/reset")
    detail = _run(client, "Ransomware on the Control Centre")
    score = detail["result"]["resilience_score_after"]
    assert detail["recommendations"], "expected at least one mitigation"

    applied = 0
    for _ in range(5):
        pending = [
            r
            for r in client.get(
                "/api/recommendations", params={"simulation_id": detail["id"]}
            ).json()
            if r["status"] == "pending"
        ]
        if not pending:
            break
        best = max(pending, key=lambda r: r["expected_resilience_gain"])
        claimed = best["expected_resilience_gain"]
        result = client.post(f"/api/recommendations/{best['id']}/apply").json()
        actual = result["result"]["resilience_score_after"] - score
        assert actual == claimed, f"{best['title']}: claimed {claimed}, measured {actual}"
        score = result["result"]["resilience_score_after"]
        applied += 1

    assert applied >= 1
    client.post("/api/reset")


def test_reject_marks_status(client):
    detail = _run(client, "Ransomware on the Control Centre")
    rec_id = detail["recommendations"][0]["id"]
    assert client.post(f"/api/recommendations/{rec_id}/reject").json()["status"] == "rejected"
    client.post("/api/reset")


def test_no_autonomous_apply_path(client):
    """F5 AC#3: only the explicit apply route may mutate the stored graph."""
    from app.routes import graph as graph_routes
    from app.routes import recommendations as rec_routes
    from app.routes import simulate as sim_routes
    import inspect

    def mutating_names(module) -> set[str]:
        source = inspect.getsource(module)
        return {
            name
            for name in ("persist_graph",)
            if name in source
        }

    assert mutating_names(rec_routes) == {"persist_graph"}
    assert mutating_names(sim_routes) == set()
    # `/api/reset` reseeds the demo city; it never applies a recommendation.
    assert "persist_graph" not in inspect.getsource(graph_routes)


def test_asset_detail_includes_findings(client):
    body = client.get("/api/assets/control_centre").json()
    assert body["name"] == "Control Centre"
    assert body["finding_count"] >= 1
    assert body["top_severity"] == "high"
    assert body["suppliers"] and body["dependents"]


def test_supply_chain_ranked_by_operational_impact(client):
    """F6 AC#2: ranking is by operational impact, not raw severity."""
    findings = client.get("/api/supply-chain").json()["findings"]
    impacts = [f["operational_impact"] for f in findings]
    assert impacts == sorted(impacts, reverse=True)

    by_asset = {f["asset_id"]: f for f in findings}
    # Same 'high' severity, but the Control Centre outranks the Data Centre
    # because its cascade reaches further into the city.
    assert by_asset["control_centre"]["severity"] == by_asset["data_centre"]["severity"]
    assert (
        by_asset["control_centre"]["operational_impact"]
        > by_asset["data_centre"]["operational_impact"]
    )


def test_health_reports_fallbacks(client):
    body = client.get("/api/health").json()
    assert body["database"] == "ok"
    assert body["osprey"] in {"mock", "live"}
    assert body["planner"] in {"llm", "fallback"}
