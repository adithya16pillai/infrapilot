"""Deterministic cascading-failure engine (F3).

Pure functions over a plain-dict graph snapshot. No database, no network, no
global state -- which is what lets this module run unchanged in-process, inside
a pytest, or inside a Modal function.

Propagation rule
----------------
For each asset, sum the weights of its *failed* suppliers **per dependency
type**. If any single type reaches `failure_threshold` (default 0.7) the asset
fails; if any reaches DEGRADED_THRESHOLD (0.4) it degrades. Per-type rather
than global summation is deliberate: losing 0.5 of power and 0.5 of comms is
not the same as losing 1.0 of power, and conflating them overstates cascades.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Iterable

from .scoring import resilience_score

DEGRADED_THRESHOLD = 0.4

# Residents of the modelled city. Population impact is derived from the share of
# critical-service capacity lost, NOT by summing each asset's `population_served`
# -- those figures overlap heavily (the same resident depends on power, water and
# telecoms), so summing them would report more casualties than the city has people.
CITY_POPULATION = 850_000

# Human-readable service names for the operator-facing summary.
SERVICE_LABELS = {
    "power_station": "bulk electricity generation",
    "substation_a": "electricity distribution (north)",
    "substation_b": "electricity distribution (south)",
    "backup_generator": "standby power",
    "control_centre": "SCADA supervisory control",
    "telecom_hub": "municipal communications",
    "data_centre": "civic data services",
    "vpn_gateway": "remote engineering access",
    "traffic_mgmt": "traffic control",
    "hospital": "acute healthcare",
    "water_treatment": "drinking water treatment",
    "emergency_services": "emergency dispatch",
}


def build_indexes(graph: dict[str, Any]) -> tuple[dict, dict]:
    """Return (suppliers_of, dependents_of) adjacency maps.

    suppliers_of[target] = list of (source, dependency_type, weight)
    """
    suppliers_of: dict[str, list[tuple[str, str, float]]] = {a: [] for a in graph["assets"]}
    dependents_of: dict[str, list[str]] = {a: [] for a in graph["assets"]}
    for dep in graph["dependencies"]:
        src, tgt = dep["source"], dep["target"]
        if src not in graph["assets"] or tgt not in graph["assets"]:
            continue
        suppliers_of[tgt].append((src, dep["dependency_type"], float(dep["weight"])))
        dependents_of[src].append(tgt)
    # Sorting makes iteration order independent of insertion order -> determinism.
    for key in suppliers_of:
        suppliers_of[key].sort()
    for key in dependents_of:
        dependents_of[key].sort()
    return suppliers_of, dependents_of


def _pressure_by_type(
    asset_id: str,
    suppliers_of: dict[str, list[tuple[str, str, float]]],
    statuses: dict[str, str],
) -> dict[str, float]:
    """Summed weight of failed suppliers, grouped by dependency type."""
    pressure: dict[str, float] = {}
    for source, dep_type, weight in suppliers_of[asset_id]:
        if statuses.get(source) == "failed":
            pressure[dep_type] = pressure.get(dep_type, 0.0) + weight
    return pressure


def run_cascade(graph: dict[str, Any], seed_assets: Iterable[str]) -> dict[str, Any]:
    """Simulate failure propagation from `seed_assets`.

    Returns the F3 output contract. Deterministic: identical input always
    produces byte-identical output (apart from `compute_ms`).
    """
    started = time.perf_counter()
    assets = graph["assets"]
    suppliers_of, dependents_of = build_indexes(graph)

    baseline = {aid: assets[aid].get("status", "healthy") for aid in assets}
    score_before = resilience_score(assets, baseline)

    statuses = dict(baseline)
    # `cause[node]` = (supplier, weight, dependency_type) — the link that pushed
    # this asset over the line. Drives both the critical path and the kill chain.
    cause: dict[str, tuple[str, float, str]] = {}

    seeds = sorted({s for s in seed_assets if s in assets})
    queue: deque[str] = deque()
    for seed in seeds:
        statuses[seed] = "failed"
        queue.append(seed)

    while queue:
        current = queue.popleft()
        for dependent in dependents_of[current]:
            if statuses.get(dependent) == "failed":
                continue  # already terminal
            threshold = float(assets[dependent].get("failure_threshold", 0.7))
            pressure = _pressure_by_type(dependent, suppliers_of, statuses)
            if not pressure:
                continue
            peak_type = max(sorted(pressure), key=lambda t: pressure[t])
            peak = pressure[peak_type]

            if peak >= threshold:
                statuses[dependent] = "failed"
                cause[dependent] = _strongest_failed_supplier(
                    dependent, suppliers_of, statuses
                )
                queue.append(dependent)
            elif peak >= DEGRADED_THRESHOLD and statuses.get(dependent) == "healthy":
                statuses[dependent] = "degraded"
                cause[dependent] = _strongest_failed_supplier(
                    dependent, suppliers_of, statuses
                )
                # Degraded nodes do not propagate in the deterministic v1 model.

    score_after = resilience_score(assets, statuses)
    critical_path = _critical_path(seeds, cause, statuses)

    failed = sorted(a for a in assets if statuses[a] == "failed")
    degraded = sorted(a for a in assets if statuses[a] == "degraded")
    newly_impacted = sorted(a for a in assets if statuses[a] != baseline[a])

    return {
        "seed_assets": seeds,
        "failed": failed,
        "degraded": degraded,
        "newly_impacted": newly_impacted,
        "resilience_score_before": score_before,
        "resilience_score_after": score_after,
        "blast_radius": len(newly_impacted),
        "critical_path": critical_path,
        "kill_chain": _kill_chain(critical_path, cause, statuses),
        "estimated_population_impact": _population_impact(score_before, score_after),
        "affected_services": _affected_services(newly_impacted, statuses),
        "statuses": statuses,
        "compute_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _strongest_failed_supplier(
    asset_id: str,
    suppliers_of: dict[str, list[tuple[str, str, float]]],
    statuses: dict[str, str],
) -> tuple[str, float, str]:
    """The single failed supplier contributing the most weight (ties -> name order)."""
    candidates = [
        (source, weight, dep_type)
        for source, dep_type, weight in suppliers_of[asset_id]
        if statuses.get(source) == "failed"
    ]
    if not candidates:
        return ("", 0.0, "")
    return max(sorted(candidates), key=lambda entry: entry[1])


def _kill_chain(
    path: list[str],
    cause: dict[str, tuple[str, float, str]],
    statuses: dict[str, str],
) -> list[dict[str, Any]]:
    """The critical path expressed as numbered attacker hops.

    A security audience reads an attack as a sequence of mechanisms, not a list
    of node names — each hop names the dependency that carried the failure and
    the weight that breached the threshold.
    """
    chain: list[dict[str, Any]] = []
    for index in range(1, len(path)):
        target = path[index]
        source, weight, dep_type = cause.get(target, ("", 0.0, ""))
        chain.append(
            {
                "step": index,
                "source": path[index - 1],
                "target": target,
                "dependency_type": dep_type or "unknown",
                "weight": weight,
                "resulting_status": statuses.get(target, "healthy"),
                "via": source,
            }
        )
    return chain


def _critical_path(
    seeds: list[str], cause: dict[str, tuple[str, float, str]], statuses: dict[str, str]
) -> list[str]:
    """Heaviest root-to-leaf chain through the propagation tree.

    Ranked by (chain length, cumulative weight) so the path shown to the
    operator is the deepest real failure chain, not merely a heavy single hop.
    """
    best_path: list[str] = list(seeds[:1])
    best_key = (0, 0.0)

    for node in sorted(cause):
        path = [node]
        weight_total = 0.0
        cursor = node
        guard = 0
        while cursor in cause and guard < len(statuses) + 1:
            parent, weight, _dep_type = cause[cursor]
            if not parent or parent in path:
                break
            weight_total += weight
            path.append(parent)
            cursor = parent
            guard += 1
        key = (len(path), round(weight_total, 6))
        if key > best_key:
            best_key = key
            best_path = list(reversed(path))

    return best_path


def population_from_score_delta(score_before: int, score_after: int) -> int:
    """Residents affected, as the share of critical-service capacity lost.

    Bounded by CITY_POPULATION by construction, and directly explainable:
    "the city lost 41% of its critical service capacity, so ~348,000 residents
    see a degraded or unavailable service".

    Note this is a *restatement* of the resilience delta on a population scale,
    not an independent measurement — it carries no information the score does
    not. It exists because "348,000 residents" lands with an audience in a way
    that "41 points" does not. Anywhere this figure is needed, call this
    function; do not re-derive it from a scaling constant.
    """
    lost_fraction = max(0, score_before - score_after) / 100
    return int(round(CITY_POPULATION * lost_fraction))


# Kept as a private alias so the call site inside run_cascade reads naturally.
_population_impact = population_from_score_delta


def _affected_services(newly_impacted: list[str], statuses: dict[str, str]) -> list[str]:
    services = []
    for asset_id in newly_impacted:
        label = SERVICE_LABELS.get(asset_id, asset_id.replace("_", " "))
        if statuses[asset_id] == "degraded":
            label += " (partial)"
        services.append(label)
    return services
