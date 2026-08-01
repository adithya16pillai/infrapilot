"""Structural graph metrics (F3 / F4 `graph_metrics` tool).

Single points of failure come from articulation points on the undirected
projection: nodes whose removal disconnects the dependency network. Importance
ranking uses betweenness centrality on the directed graph, which captures "how
much of the city's dependency flow routes through this asset".
"""

from __future__ import annotations

from typing import Any

import networkx as nx


def to_networkx(graph: dict[str, Any]) -> nx.DiGraph:
    """Build a NetworkX DiGraph from the dict snapshot, deterministically."""
    digraph = nx.DiGraph()
    for asset_id in sorted(graph["assets"]):
        digraph.add_node(asset_id, **graph["assets"][asset_id])
    for dep in sorted(
        graph["dependencies"],
        key=lambda d: (d["source"], d["target"], d["dependency_type"]),
    ):
        # Parallel edges of different types collapse to the strongest link.
        weight = float(dep["weight"])
        if digraph.has_edge(dep["source"], dep["target"]):
            existing = digraph[dep["source"]][dep["target"]]["weight"]
            weight = max(weight, existing)
        digraph.add_edge(
            dep["source"], dep["target"], weight=weight, dependency_type=dep["dependency_type"]
        )
    return digraph


def graph_metrics(graph: dict[str, Any]) -> dict[str, Any]:
    """Articulation points, betweenness ranking, and basic shape stats."""
    digraph = to_networkx(graph)
    undirected = digraph.to_undirected()

    spofs = sorted(nx.articulation_points(undirected)) if undirected.number_of_nodes() else []

    betweenness = nx.betweenness_centrality(digraph, normalized=True)
    ranking = sorted(
        ({"asset_id": aid, "betweenness": round(value, 4)} for aid, value in betweenness.items()),
        key=lambda row: (-row["betweenness"], row["asset_id"]),
    )

    in_degree = {aid: digraph.in_degree(aid) for aid in digraph.nodes}
    out_degree = {aid: digraph.out_degree(aid) for aid in digraph.nodes}

    return {
        "single_points_of_failure": spofs,
        "importance_ranking": ranking,
        "node_count": digraph.number_of_nodes(),
        "edge_count": digraph.number_of_edges(),
        "dependency_types": sorted(
            {d["dependency_type"] for d in graph["dependencies"]}
        ),
        "highest_fan_out": max(out_degree, key=lambda a: (out_degree[a], a)) if out_degree else None,
        "in_degree": in_degree,
        "out_degree": out_degree,
    }


def downstream_criticality(graph: dict[str, Any], asset_id: str) -> float:
    """Total criticality reachable downstream of `asset_id` (F6 impact ranking).

    Uses the cascade rather than raw reachability so the number reflects what
    would *actually* fail, not merely what is connected.
    """
    from .cascade import run_cascade

    if asset_id not in graph["assets"]:
        return 0.0
    result = run_cascade(graph, [asset_id])
    total = 0.0
    for impacted in result["newly_impacted"]:
        criticality = graph["assets"][impacted]["criticality"]
        total += criticality if result["statuses"][impacted] == "failed" else criticality * 0.5
    return round(total, 2)
