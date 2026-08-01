"""SQLite persistence.

Schema mirrors the PRD's Postgres DDL one-for-one, so swapping in Supabase
later is a driver change rather than a redesign. Connections are per-call --
the dataset is twelve rows and a handful of events, so pooling would be
ceremony without benefit.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    criticality INTEGER NOT NULL,
    failure_threshold REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'healthy',
    position_x REAL,
    position_y REAL,
    software_inventory TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL REFERENCES assets(id),
    target TEXT NOT NULL REFERENCES assets(id),
    dependency_type TEXT NOT NULL
        CHECK (dependency_type IN ('power','comms','operational')),
    weight REAL NOT NULL,
    UNIQUE (source, target, dependency_type)
);

CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    query TEXT,
    scenario_preset TEXT,
    status TEXT NOT NULL DEFAULT 'planning',
    summary TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL REFERENCES simulations(id),
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    label TEXT,
    tool TEXT,
    status TEXT,
    detail TEXT,
    ts TEXT NOT NULL,
    UNIQUE (simulation_id, seq)
);

CREATE TABLE IF NOT EXISTS simulation_results (
    simulation_id TEXT PRIMARY KEY REFERENCES simulations(id),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL REFERENCES simulations(id),
    title TEXT NOT NULL,
    expected_resilience_gain INTEGER NOT NULL,
    cost_estimate TEXT,
    cost_gbp INTEGER DEFAULT 0,
    gain_per_10k REAL DEFAULT 0,
    difficulty TEXT,
    confidence REAL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    graph_mutation TEXT,
    rank INTEGER DEFAULT 0,
    -- The approval gate is the responsible-AI claim; without an actor and a
    -- timestamp it is a button, not an audit trail.
    decided_by TEXT,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS supply_chain_findings (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    package TEXT NOT NULL,
    severity TEXT NOT NULL,
    behaviour TEXT,
    operational_impact REAL DEFAULT 0,
    chain TEXT
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # The planner writes events from a worker thread while SSE readers poll.
    # Default rollback journaling makes those readers block on the writer.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _json_load(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def row_to_asset(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "criticality": row["criticality"],
        "failure_threshold": row["failure_threshold"],
        "status": row["status"],
        "position_x": row["position_x"],
        "position_y": row["position_y"],
        "software_inventory": _json_load(row["software_inventory"], {}),
        "metadata": _json_load(row["metadata"], {}),
    }


def load_graph() -> dict[str, Any]:
    """The graph snapshot in the exact shape the pure engine expects."""
    with connect() as conn:
        assets = {
            row["id"]: row_to_asset(row)
            for row in conn.execute("SELECT * FROM assets ORDER BY id")
        }
        dependencies = [
            {
                "source": row["source"],
                "target": row["target"],
                "dependency_type": row["dependency_type"],
                "weight": row["weight"],
            }
            for row in conn.execute(
                "SELECT * FROM dependencies ORDER BY source, target, dependency_type"
            )
        ]
    return {"assets": assets, "dependencies": dependencies}


def persist_graph(graph: dict[str, Any]) -> None:
    """Write a mutated graph back. Only ever called from the approval flow (F5)."""
    with connect() as conn:
        for asset in graph["assets"].values():
            conn.execute(
                "UPDATE assets SET status = ?, failure_threshold = ? WHERE id = ?",
                (asset["status"], asset["failure_threshold"], asset["id"]),
            )
        conn.execute("DELETE FROM dependencies")
        for dep in graph["dependencies"]:
            conn.execute(
                "INSERT OR REPLACE INTO dependencies "
                "(source, target, dependency_type, weight) VALUES (?, ?, ?, ?)",
                (dep["source"], dep["target"], dep["dependency_type"], dep["weight"]),
            )
