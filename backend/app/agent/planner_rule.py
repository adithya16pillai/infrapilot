"""Deterministic fallback planner (F4 safety net).

Routes a query to a tool sequence by intent. This is not a fixed pipeline: a
structural question ("what is our biggest single point of failure?") runs
`graph_metrics` and deliberately skips the cascade, which is the same analysis
selection the LLM planner performs. The demo therefore survives a dead API key,
a rate limit, or venue wifi with no visible change.
"""

from __future__ import annotations

from typing import Any

from . import events, tools
from .tools import ToolContext

STRUCTURAL_HINTS = (
    "single point of failure",
    "single points of failure",
    "spof",
    "most critical",
    "most important",
    "most central",
    "biggest risk",
    "weakest link",
    "weakest point",
    "bottleneck",
    "centrality",
    "which asset matters",
)

SUPPLY_CHAIN_HINTS = (
    "supply chain",
    "package",
    "dependency vulnerab",
    "malicious",
    "osprey",
    "software risk",
    "npm",
    "library",
)

INVENTORY_HINTS = ("inventory", "what software", "running on", "firmware", "installed")


def classify(query: str) -> str:
    text = (query or "").lower()
    if any(hint in text for hint in STRUCTURAL_HINTS):
        return "structural"
    if any(hint in text for hint in SUPPLY_CHAIN_HINTS):
        return "supply_chain"
    if any(hint in text for hint in INVENTORY_HINTS):
        return "inventory"
    return "cascade"


def plan(ctx: ToolContext) -> dict[str, Any]:
    """Execute the tool sequence for this query's intent."""
    intent = classify(ctx.query)
    events.emit(
        ctx.simulation_id,
        type="plan",
        label="Planning investigation",
        status="done",
        detail=f"Intent: {intent.replace('_', ' ')} -- selecting analyses",
    )

    tools.call_tool(ctx, "resolve_assets")

    if intent == "structural":
        # Deliberately no cascade: the question is about graph shape, not an event.
        tools.call_tool(ctx, "graph_metrics")
        return _finish(ctx, _structural_summary(ctx))

    if intent == "inventory":
        for asset_id in ctx.resolved_assets[:2] or ["control_centre"]:
            tools.call_tool(ctx, "get_inventory", asset_id=asset_id)
        return _finish(ctx, _inventory_summary(ctx))

    if intent == "supply_chain":
        asset_id = ctx.resolved_assets[0] if ctx.resolved_assets else None
        tools.call_tool(ctx, "osprey_scan", asset_id=asset_id)
        return _finish(ctx, _supply_chain_summary(ctx))

    # Cascade investigation.
    if not ctx.resolved_assets:
        return _finish(ctx, _unknown_asset_summary(ctx), unresolved=True)

    tools.call_tool(ctx, "run_cascade")
    tools.call_tool(ctx, "graph_metrics")
    recs = tools.call_tool(ctx, "rank_mitigations")
    ctx.recommendations = recs["recommendations"]
    return _finish(ctx, _cascade_summary(ctx))


# --- Summary writers --------------------------------------------------------


def _finish(ctx: ToolContext, summary: str, unresolved: bool = False) -> dict[str, Any]:
    events.emit(
        ctx.simulation_id,
        type="summary",
        label="Investigation complete",
        status="done",
        detail=summary,
    )
    return {"summary": summary, "unresolved": unresolved}


def _structural_summary(ctx: ToolContext) -> str:
    metrics = ctx.metrics or {}
    spofs = metrics.get("single_points_of_failure", [])
    ranking = metrics.get("importance_ranking", [])
    names = ctx.graph["assets"]
    if not ranking:
        return "No structural metrics available."
    top = ranking[0]
    spof_names = ", ".join(names[a]["name"] for a in spofs if a in names) or "none"
    return (
        f"{names[top['asset_id']]['name']} is the most structurally important asset "
        f"(betweenness {top['betweenness']}). Articulation points -- assets whose loss "
        f"splits the dependency network -- are: {spof_names}. No cascade was simulated: "
        f"this is a structural property of the graph, not an incident."
    )


def _cascade_summary(ctx: ToolContext) -> str:
    result = ctx.cascade_result or {}
    names = ctx.graph["assets"]
    seeds = ", ".join(names[a]["name"] for a in result.get("seed_assets", []))
    failed = [names[a]["name"] for a in result.get("failed", [])]
    path = " -> ".join(names[a]["name"] for a in result.get("critical_path", []))
    best = max(
        (r["expected_resilience_gain"] for r in ctx.recommendations), default=0
    )
    return (
        f"Compromise of {seeds} propagates to {result.get('blast_radius', 0)} assets. "
        f"{len(failed)} fail outright ({', '.join(failed)}) along the path {path}. "
        f"Resilience falls {result.get('resilience_score_before')} -> "
        f"{result.get('resilience_score_after')}, affecting roughly "
        f"{result.get('estimated_population_impact', 0):,} residents. "
        f"The strongest available mitigation recovers {best} points."
    )


def _supply_chain_summary(ctx: ToolContext) -> str:
    if not ctx.findings:
        return "No supply chain findings recorded for that asset."
    top = ctx.findings[0]
    chain = " -> ".join(
        ctx.graph["assets"][a]["name"] for a in top.get("chain", []) if a in ctx.graph["assets"]
    )
    return (
        f"{len(ctx.findings)} finding(s). Highest operational impact: {top['package']} on "
        f"{top['asset_name']} (impact {top['operational_impact']}, severity "
        f"{top['severity']}). It ranks first because its failure chain reaches {chain}."
    )


def _inventory_summary(ctx: ToolContext) -> str:
    names = ctx.graph["assets"]
    parts = []
    for asset_id in ctx.resolved_assets[:2] or ["control_centre"]:
        inventory = names[asset_id].get("software_inventory", {})
        parts.append(
            f"{names[asset_id]['name']}: {inventory.get('os', 'unknown OS')}, "
            f"{len(inventory.get('packages', []))} packages"
        )
    return "; ".join(parts)


def _unknown_asset_summary(ctx: ToolContext) -> str:
    """F2 AC#2 / edge story: name the problem and list what IS valid."""
    valid = ", ".join(sorted(a["name"] for a in ctx.graph["assets"].values()))
    return (
        "I could not match that query to an asset in this city, so no simulation was run. "
        f"Valid assets are: {valid}."
    )
