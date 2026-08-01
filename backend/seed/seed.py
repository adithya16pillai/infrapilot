"""Idempotent seed. Safe to re-run at any point during the demo.

    python -m seed.seed          # upsert city, keep simulation history
    python -m seed.seed --reset  # also wipe simulations/recommendations
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect, init_db  # noqa: E402
from seed.seed_data import (  # noqa: E402
    ASSETS,
    DEPENDENCIES,
    SUPPLY_CHAIN_FINDINGS,
)


def seed(reset: bool = False) -> None:
    init_db()
    with connect() as conn:
        if reset:
            for table in (
                "simulation_events",
                "simulation_results",
                "recommendations",
                "simulations",
            ):
                conn.execute(f"DELETE FROM {table}")

        for asset in ASSETS:
            conn.execute(
                """
                INSERT INTO assets (id, name, type, criticality, failure_threshold,
                                    status, position_x, position_y,
                                    software_inventory, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    criticality = excluded.criticality,
                    failure_threshold = excluded.failure_threshold,
                    status = excluded.status,
                    position_x = excluded.position_x,
                    position_y = excluded.position_y,
                    software_inventory = excluded.software_inventory,
                    metadata = excluded.metadata
                """,
                (
                    asset["id"],
                    asset["name"],
                    asset["type"],
                    asset["criticality"],
                    asset["failure_threshold"],
                    asset["status"],
                    asset["position_x"],
                    asset["position_y"],
                    json.dumps(asset["software_inventory"]),
                    json.dumps(asset["metadata"]),
                ),
            )

        # Dependencies are rewritten wholesale: an approved mitigation may have
        # mutated them, and re-seeding is how we reset the demo to a known city.
        conn.execute("DELETE FROM dependencies")
        for source, target, dep_type, weight in DEPENDENCIES:
            conn.execute(
                "INSERT INTO dependencies (source, target, dependency_type, weight) "
                "VALUES (?, ?, ?, ?)",
                (source, target, dep_type, weight),
            )

        for finding in SUPPLY_CHAIN_FINDINGS:
            conn.execute(
                """
                INSERT INTO supply_chain_findings
                    (id, asset_id, package, severity, behaviour, operational_impact, chain)
                VALUES (?, ?, ?, ?, ?, 0, '[]')
                ON CONFLICT(id) DO UPDATE SET
                    asset_id = excluded.asset_id,
                    package = excluded.package,
                    severity = excluded.severity,
                    behaviour = excluded.behaviour
                """,
                (
                    finding["id"],
                    finding["asset_id"],
                    finding["package"],
                    finding["severity"],
                    finding["behaviour"],
                ),
            )

    print(
        f"Seeded {len(ASSETS)} assets, {len(DEPENDENCIES)} dependencies, "
        f"{len(SUPPLY_CHAIN_FINDINGS)} supply chain findings."
    )


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
