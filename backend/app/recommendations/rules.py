"""Mitigation generation and scoring (F5).

Candidates are *generated from the cascade that actually happened* rather than
looked up in a static table, so an unexpected question from a judge still gets
sensible mitigations. Every advertised `expected_resilience_gain` is measured by
re-running the engine on the mutated graph -- the LLM is never permitted to
invent a number.

Confidence is a real sensitivity analysis: the gain is re-measured under
jittered failure thresholds, and confidence is the share of those runs where the
benefit holds up. A mitigation that only works at exactly 0.7 scores low.
"""

from __future__ import annotations

from typing import Any

from ..engine.cascade import run_cascade
from ..engine.mutations import apply_mutation

SEGMENTATION_FACTOR = 0.35  # residual coupling after network segmentation
HARDENED_THRESHOLD = 0.9  # N+1 redundancy raises the bar before an asset drops

# (mode, delta) worlds to re-measure each gain in. "uniform" shifts every
# threshold the same way — the whole city becoming more or less fragile at once.
# "alternating" moves neighbours in opposite directions, which is where a
# mitigation that depends on one specific asset holding tends to break.
#
# 0.0 is deliberately absent: the unjittered world is the one that produced the
# advertised gain, so scoring it hands every positive mitigation a free 1/N and
# puts a floor under confidence it has not earned.
JITTER_PROFILES: list[tuple[str, float]] = [
    ("uniform", -0.10),
    ("uniform", -0.05),
    ("uniform", 0.05),
    ("uniform", 0.10),
    ("alternating", -0.08),
    ("alternating", 0.08),
]

# (label, difficulty, capital cost in GBP). The numeric cost drives the
# resilience-per-pound ranking; ranking on raw gain alone structurally favours
# the most expensive fix, which is the opposite of the budget question an
# operator is actually asking.
COST_BY_OP = {
    "set_weight": ("GBP 12k", "medium", 12_000),
    "set_threshold": ("GBP 45k", "high", 45_000),
    "add_edge": ("GBP 30k", "medium", 30_000),
    "remove_edge": ("GBP 8k", "low", 8_000),
}

# Curated wording for the paths we expect on stage. Anything not listed falls
# back to generated wording, which is why arbitrary scenarios still read well.
CURATED_TITLES = {
    ("set_weight", "control_centre", "substation_a"): (
        "Segment Control Centre / Substation A control plane",
        "Places the SCADA operational link behind a one-way gateway so a "
        "compromised control centre cannot issue trip commands to Substation A.",
    ),
    ("set_weight", "control_centre", "traffic_mgmt"): (
        "Isolate traffic control from SCADA management VLAN",
        "Traffic signals fall back to local time-of-day plans instead of "
        "following a compromised central controller.",
    ),
    ("set_threshold", "hospital", None): (
        "Commission N+1 power feed for the Hospital",
        "A second independent feed means loss of Substation A alone no longer "
        "degrades acute care.",
    ),
    ("set_threshold", "substation_a", None): (
        "Deploy redundant protection relays at Substation A",
        "Independent relay logic keeps the substation energised when its "
        "supervisory link is lost.",
    ),
    ("set_weight", "control_centre", "emergency_services"): (
        "Provision independent dispatch comms for Emergency Services",
        "Emergency dispatch survives loss of the control centre on a separate "
        "radio bearer.",
    ),
}


def _candidate_mutations(graph: dict, result: dict) -> list[dict[str, Any]]:
    """Propose graph changes targeted at the failure paths that actually fired."""
    impacted = set(result["newly_impacted"])
    failed = set(result["failed"])
    candidates: list[dict[str, Any]] = []

    # 1. Segment the dependencies that actually carried the cascade.
    for dep in graph["dependencies"]:
        if dep["source"] in failed and dep["target"] in impacted:
            candidates.append(
                {
                    "key": ("set_weight", dep["source"], dep["target"]),
                    "operations": [
                        {
                            "op": "set_weight",
                            "source": dep["source"],
                            "target": dep["target"],
                            "dependency_type": dep["dependency_type"],
                            "value": round(dep["weight"] * SEGMENTATION_FACTOR, 3),
                        }
                    ],
                }
            )

    # 2. Harden the assets that fell over, via redundancy.
    for asset_id in sorted(impacted):
        if graph["assets"][asset_id].get("failure_threshold", 0.7) >= HARDENED_THRESHOLD:
            continue
        candidates.append(
            {
                "key": ("set_threshold", asset_id, None),
                "operations": [
                    {"op": "set_threshold", "asset_id": asset_id, "value": HARDENED_THRESHOLD}
                ],
            }
        )

    return candidates


def _measure_gain(graph: dict, seeds: list[str], mutation: dict, baseline_after: int) -> int:
    mutated = apply_mutation(graph, mutation)
    return run_cascade(mutated, seeds)["resilience_score_after"] - baseline_after


def _confidence(graph: dict, seeds: list[str], mutation: dict, gain: int) -> float:
    """Share of threshold-jittered worlds in which the gain broadly holds.

    Offsets alternate sign across assets rather than shifting every threshold
    the same way. A uniform shift only ever tests "the whole city is a bit more
    or a bit less fragile", which the cascade absorbs smoothly; alternating
    tests the mixed cases where one asset holds while its neighbour gives, and
    that is where a mitigation's value actually turns out to be brittle.
    """
    if gain <= 0:
        return 0.0

    assets = sorted(graph["assets"].items())
    holds = 0

    for mode, delta in JITTER_PROFILES:
        operations = []
        for position, (asset_id, asset) in enumerate(assets):
            signed = -delta if (mode == "alternating" and position % 2) else delta
            operations.append(
                {
                    "op": "set_threshold",
                    "asset_id": asset_id,
                    "value": max(
                        0.15, min(0.95, asset.get("failure_threshold", 0.7) + signed)
                    ),
                }
            )
        jittered = apply_mutation(graph, {"operations": operations})
        base = run_cascade(jittered, seeds)["resilience_score_after"]
        if _measure_gain(jittered, seeds, mutation, base) >= gain * 0.8:
            holds += 1

    return round(holds / len(JITTER_PROFILES), 2)


def _describe(key: tuple, graph: dict, gain: int) -> tuple[str, str]:
    if key in CURATED_TITLES:
        return CURATED_TITLES[key]

    op, first, second = key
    name = lambda aid: graph["assets"][aid]["name"] if aid in graph["assets"] else aid  # noqa: E731
    if op == "set_weight":
        return (
            f"Segment {name(first)} to {name(second)} dependency",
            f"Reduces coupling on the link that carried the failure into "
            f"{name(second)}, worth {gain} resilience points.",
        )
    return (
        f"Add redundancy at {name(first)}",
        f"Raises the failure threshold at {name(first)} so a single upstream "
        f"loss no longer takes it out, worth {gain} resilience points.",
    )


def build_recommendations(
    graph: dict, result: dict, limit: int = 5
) -> list[dict[str, Any]]:
    """Ranked mitigations whose gains are measured, not asserted."""
    seeds = result["seed_assets"]
    baseline_after = result["resilience_score_after"]
    if not seeds:
        return []

    scored: list[dict[str, Any]] = []
    seen_keys: set[tuple] = set()

    for candidate in _candidate_mutations(graph, result):
        if candidate["key"] in seen_keys:
            continue
        seen_keys.add(candidate["key"])

        mutation = {"operations": candidate["operations"]}
        gain = _measure_gain(graph, seeds, mutation, baseline_after)
        if gain <= 0:
            continue  # never show a mitigation that does not actually help

        op = candidate["key"][0]
        cost, difficulty, cost_gbp = COST_BY_OP.get(op, ("GBP 20k", "medium", 20_000))
        title, rationale = _describe(candidate["key"], graph, gain)

        scored.append(
            {
                "title": title,
                "expected_resilience_gain": gain,
                "cost_estimate": cost,
                "cost_gbp": cost_gbp,
                # Resilience points bought per GBP 10k of capital spend.
                "gain_per_10k": round(gain / (cost_gbp / 10_000), 1),
                "difficulty": difficulty,
                "confidence": _confidence(graph, seeds, mutation, gain),
                "rationale": rationale,
                "status": "pending",
                "graph_mutation": mutation,
            }
        )

    # Rank by value for money, then by absolute gain as the tie-break.
    scored.sort(
        key=lambda r: (-r["gain_per_10k"], -r["expected_resilience_gain"], r["title"])
    )
    top = scored[:limit]
    for index, rec in enumerate(top):
        rec["rank"] = index
    return top
