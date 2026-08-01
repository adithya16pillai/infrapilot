"""Calibration harness: prints the real numbers the demo script should quote.

The PRD's illustrative 84 -> 61 -> 88 triple was written before the engine
existed. Rather than tune the formula to match the story, we run the engine and
let the story match the formula -- then freeze the output into golden tests.

    python -m seed.calibrate
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.cascade import run_cascade  # noqa: E402
from app.engine.metrics import graph_metrics  # noqa: E402
from app.engine.scoring import resilience_score  # noqa: E402
from seed.seed_data import ASSETS, DEPENDENCIES  # noqa: E402


def build_graph() -> dict:
    return {
        "assets": {asset["id"]: dict(asset) for asset in ASSETS},
        "dependencies": [
            {"source": s, "target": t, "dependency_type": dt, "weight": w}
            for s, t, dt, w in DEPENDENCIES
        ],
    }


def main() -> None:
    graph = build_graph()
    assets = graph["assets"]
    baseline = {aid: a["status"] for aid, a in assets.items()}

    total = sum(a["criticality"] for a in assets.values())
    print(f"Assets: {len(assets)}   Dependencies: {len(graph['dependencies'])}")
    print(f"Total criticality: {total}")
    print(f"BASELINE SCORE: {resilience_score(assets, baseline)}")
    print(f"  pre-degraded: {sorted(a for a, s in baseline.items() if s == 'degraded')}")

    metrics = graph_metrics(graph)
    print(f"\nSPOFs: {metrics['single_points_of_failure']}")
    print("Top betweenness:")
    for row in metrics["importance_ranking"][:4]:
        print(f"  {row['asset_id']:<20} {row['betweenness']}")

    print("\n" + "=" * 68)
    for seed in [
        "control_centre",
        "substation_a",
        "telecom_hub",
        "vpn_gateway",
        "water_treatment",
        "backup_generator",
    ]:
        result = run_cascade(graph, [seed])
        print(
            f"\n{seed}: {result['resilience_score_before']} -> "
            f"{result['resilience_score_after']} "
            f"(blast {result['blast_radius']}, {result['compute_ms']}ms)"
        )
        print(f"  failed:   {result['failed']}")
        print(f"  degraded: {result['degraded']}")
        print(f"  path:     {' -> '.join(result['critical_path'])}")
        print(f"  people:   {result['estimated_population_impact']:,}")


if __name__ == "__main__":
    main()
