"""Simulation orchestration and the live event stream (F2, F4, F7)."""

from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..agent import events, planner_llm, planner_rule
from ..agent.tools import ToolContext, persist_recommendations
from ..config import planner_mode
from ..db import connect
from ..models import SimulateAccepted, SimulateRequest, SimulationDetail, SimulationEvent

router = APIRouter(prefix="/api", tags=["simulate"])

#: Strong references to in-flight planner tasks (see simulate() below).
_RUNNING: set[asyncio.Task] = set()


def _new_id() -> str:
    return f"sim_{secrets.token_hex(8)}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/simulate", response_model=SimulateAccepted, status_code=202)
async def simulate(request: SimulateRequest) -> SimulateAccepted:
    """Create a simulation and start the agent. Returns immediately (F2 AC#1)."""
    simulation_id = _new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO simulations (id, query, scenario_preset, status, created_at) "
            "VALUES (?, ?, ?, 'planning', ?)",
            (simulation_id, request.query, request.scenario_preset, _now()),
        )

    # The planner is synchronous (SQLite + HTTP); run it off the event loop so
    # the SSE endpoint stays responsive while it works. The reference is held
    # until completion because asyncio only keeps a weak reference to tasks --
    # an unreferenced one can be collected mid-flight and the run vanishes.
    task = asyncio.create_task(
        asyncio.to_thread(_run_investigation, simulation_id, request.query)
    )
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)
    return SimulateAccepted(simulation_id=simulation_id, status="planning")


def _run_investigation(simulation_id: str, query: str) -> None:
    ctx = ToolContext(simulation_id, query)
    status, error = "complete", None

    try:
        planner = planner_llm if planner_llm.available() else planner_rule
        outcome = planner.plan(ctx)
        summary = outcome.get("summary", "")
        if outcome.get("unresolved"):
            status = "unresolved"
    except Exception as exc:  # noqa: BLE001
        status, error, summary = "failed", str(exc), ""
        events.emit(
            simulation_id,
            type="error",
            label="Investigation failed",
            status="failed",
            detail=str(exc),
        )

    with connect() as conn:
        conn.execute(
            "UPDATE simulations SET status = ?, summary = ?, error = ? WHERE id = ?",
            (status, summary, error, simulation_id),
        )
        if ctx.cascade_result is not None:
            payload = dict(ctx.cascade_result)
            if ctx.metrics:
                payload["single_points_of_failure"] = ctx.metrics["single_points_of_failure"]
                payload["importance_ranking"] = ctx.metrics["importance_ranking"][:5]
            payload["simulation_id"] = simulation_id
            conn.execute(
                "INSERT OR REPLACE INTO simulation_results (simulation_id, payload, created_at) "
                "VALUES (?, ?, ?)",
                (simulation_id, json.dumps(payload), _now()),
            )

    if ctx.recommendations:
        persist_recommendations(simulation_id, ctx.recommendations)

    events.emit(
        simulation_id,
        type="done",
        label="Ready",
        status="done",
        detail=f"Simulation {status}",
    )


@router.get("/simulations/{simulation_id}", response_model=SimulationDetail)
def get_simulation(simulation_id: str) -> SimulationDetail:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown simulation")
        result_row = conn.execute(
            "SELECT payload FROM simulation_results WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        recs = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM recommendations WHERE simulation_id = ? ORDER BY rank",
                (simulation_id,),
            )
        ]

    for rec in recs:
        rec["graph_mutation"] = json.loads(rec["graph_mutation"] or "{}")

    return SimulationDetail(
        id=row["id"],
        query=row["query"],
        scenario_preset=row["scenario_preset"],
        status=row["status"],
        summary=row["summary"],
        error=row["error"],
        created_at=row["created_at"],
        result=json.loads(result_row["payload"]) if result_row else None,
        recommendations=recs,
    )


@router.get("/simulations/{simulation_id}/events", response_model=list[SimulationEvent])
def list_events(simulation_id: str) -> list[SimulationEvent]:
    """Polling fallback for the realtime stream."""
    return events.load_events(simulation_id)


@router.get("/simulations/{simulation_id}/stream")
async def stream_events(simulation_id: str) -> StreamingResponse:
    """Server-Sent Events (F7).

    Replays everything already persisted before switching to live delivery, so
    a client that connects late — or reconnects — sees the whole investigation.
    """

    async def generator():
        queue = events.subscribe(simulation_id)
        try:
            seen: set[int] = set()
            for event in events.load_events(simulation_id):
                seen.add(event["seq"])
                yield events.sse_format(event)

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                # Replayed rows may also arrive live; the client dedupes on
                # (seq, status) but filtering here keeps the stream clean.
                key = event["seq"]
                if key in seen and event["status"] == "running":
                    continue
                seen.add(key)
                yield events.sse_format(event)

                if event["type"] == "done":
                    break
        finally:
            events.unsubscribe(simulation_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
