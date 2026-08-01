"""Agent event bus (F7).

Every planning step and tool call is persisted to `simulation_events` *and*
pushed to any in-memory subscriber queue. Persist-then-push means a client that
connects late (or reconnects) replays the full history and misses nothing --
which is what makes the SSE stream and the `/events` polling endpoint return
the same truth.

The event table is deliberately the only interface between planner and UI: the
LLM planner and the deterministic fallback are indistinguishable downstream.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from ..db import connect

# simulation_id -> set of subscriber queues
_subscribers: dict[str, set[asyncio.Queue]] = {}
_seq_counters: dict[str, int] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_seq(simulation_id: str) -> int:
    """Next sequence number, recovering from the database on a cold counter.

    The in-memory counter is a cache, not the source of truth. After a restart
    (or in a fresh worker) it is empty, and seeding from 0 would collide with
    rows already persisted for that simulation and silently drop events on the
    UNIQUE(simulation_id, seq) constraint.
    """
    current = _seq_counters.get(simulation_id)
    if current is None:
        with connect() as conn:
            row = conn.execute(
                "SELECT MAX(seq) AS top FROM simulation_events WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchone()
        current = (row["top"] or 0) if row else 0
    current += 1
    _seq_counters[simulation_id] = current
    return current


def emit(
    simulation_id: str,
    *,
    type: str,
    label: str,
    tool: str | None = None,
    status: str = "done",
    detail: str | None = None,
) -> dict[str, Any]:
    """Record an event and fan it out to live subscribers."""
    event = {
        "simulation_id": simulation_id,
        "seq": next_seq(simulation_id),
        "type": type,
        "label": label,
        "tool": tool,
        "status": status,
        "detail": detail,
        "ts": _now(),
    }

    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO simulation_events "
            "(simulation_id, seq, type, label, tool, status, detail, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event["simulation_id"],
                event["seq"],
                event["type"],
                event["label"],
                event["tool"],
                event["status"],
                event["detail"],
                event["ts"],
            ),
        )

    for queue in list(_subscribers.get(simulation_id, ())):
        queue.put_nowait(event)
    return event


def update_last(simulation_id: str, seq: int, *, status: str, detail: str | None = None) -> dict:
    """Flip a previously-emitted `running` row to done/failed with its detail."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM simulation_events WHERE simulation_id = ? AND seq = ?",
            (simulation_id, seq),
        ).fetchone()
        if row is None:
            return {}
        conn.execute(
            "UPDATE simulation_events SET status = ?, detail = ?, ts = ? "
            "WHERE simulation_id = ? AND seq = ?",
            (status, detail, _now(), simulation_id, seq),
        )
        event = {
            "simulation_id": simulation_id,
            "seq": seq,
            "type": row["type"],
            "label": row["label"],
            "tool": row["tool"],
            "status": status,
            "detail": detail,
            "ts": _now(),
        }

    for queue in list(_subscribers.get(simulation_id, ())):
        queue.put_nowait(event)
    return event


def load_events(simulation_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM simulation_events WHERE simulation_id = ? ORDER BY seq",
            (simulation_id,),
        ).fetchall()
    return [
        {
            "simulation_id": row["simulation_id"],
            "seq": row["seq"],
            "type": row["type"],
            "label": row["label"],
            "tool": row["tool"],
            "status": row["status"],
            "detail": row["detail"],
            "ts": row["ts"],
        }
        for row in rows
    ]


def subscribe(simulation_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(simulation_id, set()).add(queue)
    return queue


def unsubscribe(simulation_id: str, queue: asyncio.Queue) -> None:
    subscribers = _subscribers.get(simulation_id)
    if not subscribers:
        return
    subscribers.discard(queue)
    if not subscribers:
        _subscribers.pop(simulation_id, None)


def sse_format(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"
