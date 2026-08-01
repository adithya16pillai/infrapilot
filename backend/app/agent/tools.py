"""The six tools the agent can choose between (F4).

Each tool is a plain Python callable wrapped so that invoking it emits a
`running` event, then flips that same row to `done`/`failed` with a one-line
detail. Both planners share this module, which is what makes the LLM planner and
the deterministic fallback produce byte-identical event streams.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from ..db import connect, load_graph
from ..engine.cascade import run_cascade as _run_cascade
from ..engine.metrics import graph_metrics as _graph_metrics
from ..osprey import adapter as osprey
from ..recommendations.rules import build_recommendations
from . import events

# Words that should never be treated as an asset name during resolution.
_STOPWORDS = {
    "the", "a", "an", "on", "at", "in", "to", "of", "if", "is", "what", "happens",
    "simulate", "attack", "our", "we", "and", "for", "from", "loses", "lose",
    "failure", "fails", "fail", "biggest", "single", "point", "compromise",
    "compromised", "ransomware", "blast", "radius", "city", "power",
}


class ToolContext:
    """Per-simulation working memory shared across tool calls."""

    def __init__(self, simulation_id: str, query: str):
        self.simulation_id = simulation_id
        self.query = query
        self.graph = load_graph()
        self.resolved_assets: list[str] = []
        self.cascade_result: dict[str, Any] | None = None
        self.metrics: dict[str, Any] | None = None
        self.recommendations: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.tools_used: list[str] = []


#: Fields that originate outside our trust boundary. With OSPREY_MODE=live these
#: carry text authored by whoever published the flagged package — an attacker can
#: choose it. It reaches the planner as a tool result, which is exactly the
#: channel prompt injection travels down, so it is fenced before it gets there.
UNTRUSTED_FIELDS = ("behaviour", "package", "rank_reason")
MAX_UNTRUSTED_CHARS = 400


def _fence(value: Any) -> str:
    """Neutralise untrusted text so it reads as data, never as instructions.

    Strips the delimiters and role markers an injected string would use to
    break out of its block, then wraps what remains in an explicit fence. The
    planner's system prompt tells it to treat fenced content as inert.
    """
    text = str(value)[:MAX_UNTRUSTED_CHARS]
    for marker in ("<untrusted>", "</untrusted>", "```", "\r"):
        text = text.replace(marker, " ")
    # Collapse newlines: injections rely on a fresh line to look authoritative.
    text = " ".join(text.split())
    return f"<untrusted>{text}</untrusted>"


def _fence_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: (_fence(value) if key in UNTRUSTED_FIELDS else value)
            for key, value in finding.items()
        }
        for finding in findings
    ]


def _asset_name_map(graph: dict) -> dict[str, str]:
    return {asset["name"].lower(): asset_id for asset_id, asset in graph["assets"].items()}


def resolve_assets(ctx: ToolContext, query: str | None = None) -> dict[str, Any]:
    """Map natural language onto asset ids."""
    text = (query or ctx.query or "").lower()
    names = _asset_name_map(ctx.graph)
    matched: list[str] = []

    # Exact name and id substring matches first -- highest precision.
    for name, asset_id in names.items():
        if name in text and asset_id not in matched:
            matched.append(asset_id)
    for asset_id in ctx.graph["assets"]:
        if asset_id in text and asset_id not in matched:
            matched.append(asset_id)

    # Fall back to fuzzy matching individual salient words.
    if not matched:
        words = [w for w in re.findall(r"[a-z]+", text) if w not in _STOPWORDS and len(w) > 3]
        for word in words:
            close = difflib.get_close_matches(word, list(names), n=1, cutoff=0.75)
            if close and names[close[0]] not in matched:
                matched.append(names[close[0]])

    ctx.resolved_assets = matched
    return {
        "resolved": matched,
        "names": [ctx.graph["assets"][a]["name"] for a in matched],
        "valid_assets": sorted(
            ctx.graph["assets"][a]["name"] for a in ctx.graph["assets"]
        ),
    }


def run_cascade(ctx: ToolContext, seed_assets: list[str] | None = None) -> dict[str, Any]:
    """Simulate failure propagation from the given seed assets."""
    seeds = seed_assets or ctx.resolved_assets
    if not seeds:
        raise ValueError("No seed assets resolved -- cannot simulate a cascade.")
    result = _run_cascade(ctx.graph, seeds)
    ctx.cascade_result = result
    return result


def graph_metrics(ctx: ToolContext) -> dict[str, Any]:
    """Structural analysis: single points of failure and importance ranking."""
    metrics = _graph_metrics(ctx.graph)
    ctx.metrics = metrics
    return metrics


def get_inventory(ctx: ToolContext, asset_id: str) -> dict[str, Any]:
    """Software and firmware inventory for one asset."""
    asset = ctx.graph["assets"].get(asset_id)
    if asset is None:
        raise ValueError(f"Unknown asset: {asset_id}")
    inventory = dict(asset.get("software_inventory", {}))
    if inventory.get("packages"):
        inventory["packages"] = [_fence(pkg) for pkg in inventory["packages"]]
    return {"asset_id": asset_id, "name": asset["name"], "software_inventory": inventory}


def osprey_scan(ctx: ToolContext, asset_id: str | None = None) -> dict[str, Any]:
    """Supply chain findings, ranked by operational impact."""
    if asset_id:
        findings = osprey.scan_asset(ctx.graph, asset_id)
    else:
        findings = osprey.scan_all(ctx.graph)
    # The UI renders the real text; the planner only ever sees a fenced copy.
    ctx.findings = findings
    return {"mode": osprey.mode(), "findings": _fence_findings(findings)}


def rank_mitigations(ctx: ToolContext) -> dict[str, Any]:
    """Prioritised mitigations with gains measured by re-simulation."""
    if ctx.cascade_result is None:
        raise ValueError("Run a cascade before ranking mitigations.")
    recs = build_recommendations(ctx.graph, ctx.cascade_result)
    ctx.recommendations = recs
    return {"recommendations": recs}


# --- Event-emitting wrapper -------------------------------------------------

TOOL_LABELS = {
    "resolve_assets": "Identifying affected assets",
    "run_cascade": "Calculating cascading impact",
    "graph_metrics": "Mapping structural dependencies",
    "get_inventory": "Reading software inventory",
    "osprey_scan": "Scanning software supply chain",
    "rank_mitigations": "Generating mitigation plan",
}

TOOLS: dict[str, Callable[..., Any]] = {
    "resolve_assets": resolve_assets,
    "run_cascade": run_cascade,
    "graph_metrics": graph_metrics,
    "get_inventory": get_inventory,
    "osprey_scan": osprey_scan,
    "rank_mitigations": rank_mitigations,
}


def _summarise(tool: str, result: Any, ctx: ToolContext) -> str:
    """One line of operator-facing detail per completed tool call."""
    if tool == "resolve_assets":
        names = result.get("names") or []
        return ", ".join(names) if names else "no matching asset found"
    if tool == "run_cascade":
        return (
            f"{result['blast_radius']} assets affected, resilience "
            f"{result['resilience_score_before']} -> {result['resilience_score_after']}"
        )
    if tool == "graph_metrics":
        spofs = result["single_points_of_failure"]
        top = result["importance_ranking"][0]["asset_id"] if result["importance_ranking"] else "-"
        return (
            f"{result['edge_count']} edges, {len(result['dependency_types'])} dependency types; "
            f"{len(spofs)} single point(s) of failure, most central: {top}"
        )
    if tool == "get_inventory":
        packages = result.get("software_inventory", {}).get("packages", [])
        return f"{len(packages)} packages on {result.get('name', '')}"
    if tool == "osprey_scan":
        findings = result.get("findings", [])
        high = sum(1 for f in findings if f["severity"] == "high")
        return f"{len(findings)} finding(s), {high} high severity [{result.get('mode')}]"
    if tool == "rank_mitigations":
        recs = result.get("recommendations", [])
        best = max((r["expected_resilience_gain"] for r in recs), default=0)
        return f"{len(recs)} mitigation(s), best gain +{best} points"
    return "done"


def call_tool(ctx: ToolContext, tool: str, **kwargs: Any) -> Any:
    """Invoke a tool with running -> done/failed event bookkeeping."""
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool: {tool}")

    event = events.emit(
        ctx.simulation_id,
        type="tool_call",
        label=TOOL_LABELS.get(tool, tool),
        tool=tool,
        status="running",
    )
    try:
        result = TOOLS[tool](ctx, **kwargs)
    except Exception as exc:  # F7 AC#2: a failed tool renders and the run continues
        events.update_last(ctx.simulation_id, event["seq"], status="failed", detail=str(exc))
        raise

    ctx.tools_used.append(tool)
    events.update_last(
        ctx.simulation_id, event["seq"], status="done", detail=_summarise(tool, result, ctx)
    )
    return result


def persist_recommendations(simulation_id: str, recommendations: list[dict]) -> list[dict]:
    """Store ranked mitigations and hand back rows carrying their ids."""
    import json

    stored = []
    with connect() as conn:
        conn.execute("DELETE FROM recommendations WHERE simulation_id = ?", (simulation_id,))
        for index, rec in enumerate(recommendations):
            rec_id = f"{simulation_id}_rec_{index + 1:02d}"
            conn.execute(
                """
                INSERT INTO recommendations
                    (id, simulation_id, title, expected_resilience_gain, cost_estimate,
                     cost_gbp, gain_per_10k, difficulty, confidence, rationale,
                     status, graph_mutation, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    rec_id,
                    simulation_id,
                    rec["title"],
                    rec["expected_resilience_gain"],
                    rec["cost_estimate"],
                    rec["cost_gbp"],
                    rec["gain_per_10k"],
                    rec["difficulty"],
                    rec["confidence"],
                    rec["rationale"],
                    json.dumps(rec["graph_mutation"]),
                    index,
                ),
            )
            stored.append({**rec, "id": rec_id, "simulation_id": simulation_id})
    return stored
