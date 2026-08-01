"""Live check of the Claude planner. Run once ANTHROPIC_API_KEY is set.

    cd backend
    python verify_planner.py

Drives four real queries through the agent and prints the tool sequence each
one chose. The point is the *differences* between them: if the agent runs the
same tools for every question, it is not selecting analyses and F4's second
acceptance criterion is not met.

Exits non-zero if the live agent misbehaves, so it doubles as a pre-demo gate.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agent import events, planner_llm  # noqa: E402
from app.agent.tools import ToolContext  # noqa: E402
from app.config import PLANNER_MODEL  # noqa: E402
from app.db import connect, init_db  # noqa: E402

CASES = [
    (
        "Simulate a ransomware attack on the Control Centre",
        {"resolve_assets", "run_cascade", "rank_mitigations"},
        set(),
    ),
    (
        "What is our biggest single point of failure?",
        {"graph_metrics"},
        {"run_cascade"},  # a structural question must not simulate an incident
    ),
    (
        "Which software packages put us most at risk?",
        {"osprey_scan"},
        set(),
    ),
    (
        "Simulate an attack on the Atlantis Sea Gate",
        set(),
        {"run_cascade"},  # unknown asset: answer, do not invent a cascade
    ),
]


def main() -> int:
    if not planner_llm.available():
        print("ANTHROPIC_API_KEY is not set — the deterministic router would run.")
        print("Add it to backend/.env, then re-run this script.")
        return 1

    init_db()
    print(f"Planner model: {PLANNER_MODEL}\n")
    failures = 0

    for index, (query, required, forbidden) in enumerate(CASES, start=1):
        simulation_id = f"verify_{int(time.time())}_{index}"
        with connect() as conn:
            conn.execute(
                "INSERT INTO simulations (id, query, status, created_at) "
                "VALUES (?, ?, 'planning', datetime('now'))",
                (simulation_id, query),
            )

        started = time.perf_counter()
        try:
            outcome = planner_llm.plan(ToolContext(simulation_id, query))
        except Exception as exc:  # noqa: BLE001
            print(f"[{index}] {query}\n    EXCEPTION: {exc}\n")
            failures += 1
            continue
        elapsed = time.perf_counter() - started

        used = [e["tool"] for e in events.load_events(simulation_id) if e["tool"]]
        fell_back = any(
            e["label"] == "Switching to built-in planner"
            for e in events.load_events(simulation_id)
        )

        missing = required - set(used)
        banned = forbidden & set(used)
        ok = not missing and not banned and not fell_back

        print(f"[{index}] {query}")
        print(f"    tools   : {' -> '.join(used) or '(none)'}")
        print(f"    summary : {(outcome.get('summary') or '')[:110]}")
        print(f"    {elapsed:.1f}s")
        if fell_back:
            print("    FAIL: fell back to the deterministic router")
        if missing:
            print(f"    FAIL: never called {sorted(missing)}")
        if banned:
            print(f"    FAIL: should not have called {sorted(banned)}")
        if ok:
            print("    OK")
        print()
        failures += 0 if ok else 1

    if failures:
        print(f"{failures}/{len(CASES)} case(s) failed — the demo will use the router.")
        return 1

    print("All cases passed. The agent is selecting analyses per question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
