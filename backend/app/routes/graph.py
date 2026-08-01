"""Graph and asset endpoints (F1)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import connect, load_graph
from ..engine.cascade import build_indexes
from ..engine.scoring import resilience_score
from ..models import AssetDetail, GraphResponse
from ..osprey import adapter as osprey
from seed.seed_data import SCENARIO_PRESETS

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
def get_graph() -> GraphResponse:
    graph = load_graph()
    statuses = {aid: a["status"] for aid, a in graph["assets"].items()}
    return GraphResponse(
        assets=list(graph["assets"].values()),
        dependencies=graph["dependencies"],
        presets=SCENARIO_PRESETS,
        resilience_score=resilience_score(graph["assets"], statuses),
    )


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: str) -> AssetDetail:
    graph = load_graph()
    asset = graph["assets"].get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Unknown asset: {asset_id}")

    suppliers = [d for d in graph["dependencies"] if d["target"] == asset_id]
    dependents = [d for d in graph["dependencies"] if d["source"] == asset_id]
    summary = osprey.findings_summary(graph, asset_id)

    return AssetDetail(
        **asset,
        suppliers=suppliers,
        dependents=dependents,
        findings=summary["findings"],
        finding_count=summary["count"],
        top_severity=summary["top_severity"],
    )


@router.get("/supply-chain")
def get_supply_chain() -> dict:
    """All findings, ranked by operational impact rather than raw severity (F6)."""
    graph = load_graph()
    findings = osprey.scan_all(graph)
    return {
        "mode": osprey.mode(),
        "findings": findings,
        "comparison": osprey.impact_comparison(graph),
    }


@router.get("/simulations")
def list_simulations(limit: int = 50) -> list[dict]:
    """History for the Simulations page."""
    import json

    with connect() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT s.id, s.query, s.scenario_preset, s.status, s.summary, "
                "s.created_at, r.payload FROM simulations s "
                "LEFT JOIN simulation_results r ON r.simulation_id = s.id "
                "ORDER BY s.created_at DESC LIMIT ?",
                (limit,),
            )
        ]

    out = []
    for row in rows:
        payload = json.loads(row["payload"]) if row["payload"] else None
        out.append(
            {
                "id": row["id"],
                "query": row["query"],
                "scenario_preset": row["scenario_preset"],
                "status": row["status"],
                "summary": row["summary"],
                "created_at": row["created_at"],
                "score_before": payload["resilience_score_before"] if payload else None,
                "score_after": payload["resilience_score_after"] if payload else None,
                "blast_radius": payload["blast_radius"] if payload else None,
                "seed_assets": payload["seed_assets"] if payload else [],
            }
        )
    return out


@router.post("/reset")
def reset_city() -> dict:
    """Restore the seed city. Used between demo runs and by the E2E test."""
    from seed.seed import seed

    seed(reset=True)
    graph = load_graph()
    statuses = {aid: a["status"] for aid, a in graph["assets"].items()}
    return {"status": "ok", "resilience_score": resilience_score(graph["assets"], statuses)}


@router.get("/dashboard")
def get_dashboard() -> dict:
    """Composed summary for the executive dashboard (F8)."""
    import json

    graph = load_graph()
    assets = graph["assets"]
    statuses = {aid: a["status"] for aid, a in assets.items()}
    _, dependents_of = build_indexes(graph)

    with connect() as conn:
        sims = [
            dict(row)
            for row in conn.execute(
                "SELECT s.id, s.query, s.status, s.created_at, r.payload "
                "FROM simulations s LEFT JOIN simulation_results r "
                "ON r.simulation_id = s.id ORDER BY s.created_at DESC LIMIT 8"
            )
        ]
        pending = [
            dict(row)
            for row in conn.execute(
                "SELECT id, simulation_id, title, expected_resilience_gain, "
                "cost_estimate, cost_gbp, gain_per_10k, difficulty, confidence, "
                "rationale, status, graph_mutation FROM recommendations "
                "WHERE status = 'pending' "
                "ORDER BY gain_per_10k DESC, expected_resilience_gain DESC LIMIT 5"
            )
        ]

    recent = []
    for sim in sims:
        payload = json.loads(sim["payload"]) if sim["payload"] else None
        recent.append(
            {
                "id": sim["id"],
                "query": sim["query"],
                "status": sim["status"],
                "created_at": sim["created_at"],
                "score_before": payload["resilience_score_before"] if payload else None,
                "score_after": payload["resilience_score_after"] if payload else None,
            }
        )

    highest_risk = max(
        assets.values(),
        key=lambda a: (a["criticality"] * (len(dependents_of[a["id"]]) + 1), a["id"]),
    )

    return {
        "resilience_score": resilience_score(assets, statuses),
        "status_breakdown": {
            state: sum(1 for s in statuses.values() if s == state)
            for state in ("healthy", "degraded", "failed", "hardened")
        },
        "critical_assets": sum(1 for a in assets.values() if a["criticality"] >= 8),
        "highest_risk_asset": {
            "id": highest_risk["id"],
            "name": highest_risk["name"],
            "criticality": highest_risk["criticality"],
        },
        "estimated_population_impact": max(
            (r["score_before"] or 0) - (r["score_after"] or 0) for r in recent
        )
        * 8_500
        if recent
        else 0,
        "score_trend": [
            r["score_after"] for r in reversed(recent) if r["score_after"] is not None
        ],
        "recent_simulations": recent,
        "pending_recommendations": pending,
        "top_supply_chain_risks": osprey.scan_all(graph)[:4],
    }
