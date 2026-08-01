"""Recommendation listing and the human approval gate (F5).

`apply` is the only endpoint in the entire API that mutates the stored graph.
That is the Responsible AI guarantee the UI banner claims, and
`test_no_autonomous_apply_path` asserts it.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ..db import connect, load_graph, persist_graph
from ..engine.cascade import run_cascade
from ..engine.metrics import graph_metrics
from ..engine.mutations import apply_mutation
from ..engine.scoring import resilience_score
from ..models import ApplyResult, Recommendation

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

#: This build ships no authentication (a stated non-goal), so there is no real
#: principal to attribute a decision to. Recording a placeholder keeps the audit
#: columns populated and makes the gap explicit rather than silent: wire real
#: auth and this becomes the authenticated user.
DEMO_OPERATOR = "demo-operator (unauthenticated build)"


def _decision(rec_id: str) -> dict:
    """The decision fields as actually persisted, for echoing back to the caller."""
    with connect() as conn:
        row = conn.execute(
            "SELECT status, decided_by, decided_at FROM recommendations WHERE id = ?",
            (rec_id,),
        ).fetchone()
    return dict(row) if row else {}


def _load(rec_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown recommendation")
    rec = dict(row)
    rec["graph_mutation"] = json.loads(rec["graph_mutation"] or "{}")
    return rec


@router.get("/pending", response_model=list[Recommendation])
def list_pending() -> list[Recommendation]:
    """Every mitigation awaiting a human decision, best value for money first."""
    with connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM recommendations WHERE status = 'pending' "
                "ORDER BY gain_per_10k DESC, expected_resilience_gain DESC"
            )
        ]
    for row in rows:
        row["graph_mutation"] = json.loads(row["graph_mutation"] or "{}")
    return rows


@router.get("", response_model=list[Recommendation])
def list_recommendations(simulation_id: str) -> list[Recommendation]:
    with connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM recommendations WHERE simulation_id = ? ORDER BY rank",
                (simulation_id,),
            )
        ]
    for row in rows:
        row["graph_mutation"] = json.loads(row["graph_mutation"] or "{}")
    return rows


@router.post("/{rec_id}/apply", response_model=ApplyResult)
def apply_recommendation(rec_id: str, actor: str = DEMO_OPERATOR) -> ApplyResult:
    """Human-approved mutation of the resilience model. Never a live system."""
    rec = _load(rec_id)
    if rec["status"] == "approved":
        raise HTTPException(status_code=409, detail="Recommendation already applied")

    with connect() as conn:
        sim_row = conn.execute(
            "SELECT payload FROM simulation_results WHERE simulation_id = ?",
            (rec["simulation_id"],),
        ).fetchone()
    if sim_row is None:
        raise HTTPException(status_code=409, detail="Simulation has no result to improve on")
    seeds = json.loads(sim_row["payload"])["seed_assets"]

    graph = load_graph()
    mutated = apply_mutation(graph, rec["graph_mutation"])
    persist_graph(mutated)

    result = run_cascade(mutated, seeds)
    metrics = graph_metrics(mutated)
    result["single_points_of_failure"] = metrics["single_points_of_failure"]
    result["importance_ranking"] = metrics["importance_ranking"][:5]
    result["simulation_id"] = rec["simulation_id"]

    with connect() as conn:
        conn.execute(
            "UPDATE recommendations SET status = 'approved', decided_by = ?, "
            "decided_at = datetime('now') WHERE id = ?",
            (actor, rec_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO simulation_results (simulation_id, payload, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (rec["simulation_id"], json.dumps(result)),
        )

    _rescore_pending(rec["simulation_id"], mutated, seeds, result["resilience_score_after"])
    # `rec` was read before the update, so mirror the decision onto the payload
    # the caller gets back rather than returning a stale row.
    rec.update(_decision(rec_id))
    baseline = {aid: a["status"] for aid, a in mutated["assets"].items()}
    return ApplyResult(
        recommendation=rec,
        result=result,
        resilience_score=resilience_score(mutated["assets"], baseline),
    )


def _rescore_pending(
    simulation_id: str, graph: dict, seeds: list[str], baseline_after: int
) -> None:
    """Re-measure every still-pending mitigation against the newly hardened graph.

    Mitigations are not independent: once the Control Centre / Substation A
    control plane is segmented, Substation A no longer fails, so "add redundancy
    at Substation A" is worth nothing. Without this pass the second card an
    operator approves would advertise a gain measured against a city that no
    longer exists. Recommendations whose value has been absorbed drop to
    `superseded` rather than lingering with a stale number.
    """
    with connect() as conn:
        pending = [
            dict(row)
            for row in conn.execute(
                "SELECT id, graph_mutation, cost_gbp FROM recommendations "
                "WHERE simulation_id = ? AND status = 'pending'",
                (simulation_id,),
            )
        ]

        for row in pending:
            mutation = json.loads(row["graph_mutation"] or "{}")
            try:
                candidate = apply_mutation(graph, mutation)
                gain = run_cascade(candidate, seeds)["resilience_score_after"] - baseline_after
            except Exception:  # noqa: BLE001 - a broken mutation must not block approval
                gain = 0
            cost_gbp = row["cost_gbp"] or 20_000
            conn.execute(
                "UPDATE recommendations SET expected_resilience_gain = ?, "
                "gain_per_10k = ?, status = ? WHERE id = ?",
                (
                    max(gain, 0),
                    round(max(gain, 0) / (cost_gbp / 10_000), 1),
                    "pending" if gain > 0 else "superseded",
                    row["id"],
                ),
            )


@router.post("/{rec_id}/reject", response_model=Recommendation)
def reject_recommendation(rec_id: str, actor: str = DEMO_OPERATOR) -> Recommendation:
    rec = _load(rec_id)
    with connect() as conn:
        conn.execute(
            "UPDATE recommendations SET status = 'rejected', decided_by = ?, "
            "decided_at = datetime('now') WHERE id = ?",
            (actor, rec_id),
        )
    rec.update(_decision(rec_id))
    return rec
