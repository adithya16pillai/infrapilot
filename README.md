# InfraPilot

**AI resilience copilot for critical infrastructure — simulate the attack, measure the fix.**

Attack-path analysis for cities: an agent picks the analyses, a deterministic
engine computes the cascade, and every mitigation is scored by re-simulation
behind a human approval gate.

Built for the Cursor Cybersecurity London hackathon.

---
## Tech Stack

### Frontend:

Next.js 14+ (App Router) with TypeScript strict mode
TailwindCSS + shadcn/ui for components
React Flow (@xyflow/react) for the infrastructure graph
Framer Motion for cascade animations and score count-ups
recharts for dashboard charts
supabase-js (realtime reads only, for streaming agent events)
Deployed on Vercel

### Backend:

FastAPI on Python 3.11+ with Pydantic v2
NetworkX for the graph algorithms (cascade BFS, articulation points, betweenness centrality)
uv as package manager
Anthropic API for the agent loop and rationale text

### Database

Supabase (Postgres + Realtime) holding assets, dependencies, simulations, events, results, recommendations, and supply chain findings

### Partner tech:

Modal: runs the heavy compute, simulate_cascade and graph_metrics as serverless functions, with a keep-warm ping and a USE_MODAL=false local fallback
Overmind: the agent orchestration layer on top of your tool-use loop, planning which analyses to run per query
OSSPrey: supply chain layer, scanning each asset's software inventory for malicious packages, re-ranked by operational impact via your cascade engine, with OSPREY_MODE=mock|live


## Run the development server

Two terminals. No cloud accounts and no API keys are required — every
integration has a working local fallback.

```bash
# 1. Backend — http://127.0.0.1:8000
cd backend
pip install -r requirements.txt
python -m seed.seed --reset          # build and seed the SQLite city
python -m uvicorn app.main:app --port 8000

# 2. Frontend — http://localhost:3000
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** for the dashboard; **City view** (top right, or
in the sidebar) is the graph.

Useful extras:

```bash
python -m seed.calibrate     # print the demo numbers straight from the engine
python -m seed.seed --reset  # restore the city between runs
python verify_planner.py     # live-check the Claude planner (needs a key)
```

> **Restart uvicorn after editing anything under `backend/`.** Seed data and
> presets are module-level constants, so a running process keeps serving the old
> values and the UI looks stale for no visible reason.

Ports are configurable: the frontend reads `NEXT_PUBLIC_API_BASE` (default
`http://127.0.0.1:8000`), the backend reads `CORS_ORIGINS`.

---

## The five things it does

**1. Simulates a cascade, deterministically.** Describe an attack in plain
English and a NetworkX engine propagates it through the city's dependency graph.
Failure pressure is summed **per dependency type** — losing half your power and
half your comms is not the same event as losing all your power, and adding them
together invents cascades that would not happen. Same input, same output, every
time.

**2. The agent chooses which analyses to run.** Not a fixed pipeline. A Claude
tool-use loop selects from six tools per question, and the difference is visible
in the event stream:

| Question | Tools it runs |
|---|---|
| "What happens if the Water Treatment Plant loses power?" | `resolve_assets` → `run_cascade` → `graph_metrics` → `rank_mitigations` |
| "What is our biggest single point of failure?" | `resolve_assets` → `graph_metrics` — **no cascade** |
| "Which packages are a supply chain risk?" | `resolve_assets` → `osprey_scan` |
| "Simulate an attack on the Atlantis Sea Gate" | `resolve_assets` → stops, names the valid assets |

**3. Narrates the attack path as a kill chain.** The critical path comes back as
numbered hops naming the mechanism that carried each failure, not a list of node
names:

```
0. Control Centre      compromised
1. Substation A        failed    via control link from Control Centre · weight 0.75
2. Traffic Management  failed    via power feed  from Substation A   · weight 0.85
```

**4. Scores every mitigation by re-simulation, behind a human approval gate.**
The engine deep-copies the graph, applies the change, re-runs the cascade and
takes the difference — the LLM may reword a title but never touches a number.
Mitigations rank by **resilience points per £10k**, because ranking on raw gain
structurally favours the most expensive fix:

```
Segment Control Centre / Substation A control plane  +14  £12k  11.7 pts/£10k
Provision independent dispatch comms                  +5  £12k   4.2
Deploy redundant protection relays at Substation A   +10  £45k   2.2  <- biggest gain, worst value
```

`POST /api/recommendations/{id}/apply` is the only code path that mutates the
stored graph, and only a human clicking Approve reaches it. Approvals record
`decided_by` and `decided_at`. Approving one mitigation re-scores the rest,
because they are not independent.

**5. Ranks supply chain findings by operational consequence, not severity.**
OSSPrey detects malicious packages by *behaviour* rather than CVE matching. That
says how malicious a package is; it cannot say how much it matters to this city.
InfraPilot supplies the second half:

```
impact = severity_weight × downstream_criticality(asset)

node-ipc@10.1.1     on Control Centre  HIGH  impact 36.0  ← cascade reaches the Hospital
event-stream@3.3.6  on Data Centre     HIGH  impact 10.5  ← cascade stops at the Control Centre
```

Same severity, 3.4× different priority.

---

## Integrations

All three are wired behind flags with working fallbacks, so the demo never
depends on a network. `GET /api/health` reports which path is live —
`overmind: fallback` and `osprey: mock` are expected states, not failures.

### Modal — cascade compute

| | |
|---|---|
| Env | `USE_MODAL=false`, `MODAL_FUNCTION=infrapilot/simulate_cascade` |
| Status | **Not deployed.** The in-process engine runs instead. |

`app/engine/` is deliberately pure — dict in, dict out, no I/O, no database — so
the identical module runs in-process, inside a pytest, or inside a Modal
function with no changes. To move it:

```python
# modal_app.py
import modal

image = modal.Image.debian_slim().pip_install("networkx")
app = modal.App("infrapilot", image=image)

@app.function()
def simulate_cascade(graph: dict, seed_assets: list[str]) -> dict:
    from app.engine.cascade import run_cascade
    return run_cascade(graph, seed_assets)
```

`modal deploy modal_app.py`, then set `USE_MODAL=true`. The call site is
`modal.Function.from_name(MODAL_FUNCTION).remote(graph, seeds)`. Because both
paths run the same function, `test_local_fallback_equals_modal` becomes a direct
equality assertion the moment the deploy exists.

### OSSPrey — supply chain findings

| | |
|---|---|
| Env | `OSPREY_MODE=mock` \| `live` |
| Status | **Mock.** Returns representative findings in the live API's exact shape. |

You do **not** need OSSPrey credentials or sample packages to run this.
InfraPilot does not scan manifests — it consumes findings and re-ranks them, so
the only integration work is mapping their response onto the three fields the
adapter reads:

```python
{"package": str, "severity": "high" | "medium" | "low", "behaviour": str}
```

Adapter: `app/osprey/adapter.py`. `scan_asset()` and `scan_all()` are the seams;
swap the SQLite read for an HTTP call and everything downstream — impact
ranking, the comparison panel, the node badges — is unchanged.

> **Security note.** `behaviour` and `package` are authored by whoever published
> the package, so under `OSPREY_MODE=live` they are attacker-controlled text
> entering an LLM's context. They are stripped of delimiters, collapsed to one
> line, length-capped and wrapped in `<untrusted>` fences before reaching the
> planner, which is instructed to treat fenced content as inert data. The UI
> still renders the original text.

### Overmind — agent orchestration

| | |
|---|---|
| Env | none yet |
| Status | **Not wired.** The built-in Claude tool-use planner covers the same interface. |

The planner is already swappable: `app/agent/planner_llm.py` and
`planner_rule.py` both expose `plan(ctx) -> {"summary", "unresolved"}` and write
to the same event bus, so a `planner_overmind.py` implementing that signature
drops in without touching the API or the frontend. The six tools are registered
in `app/agent/tools.py` with JSON-Schema definitions Overmind can consume
directly.

**The event table is the contract.** Because both existing planners emit
identical streams, the UI cannot tell which one ran — which is also why killing
the LLM mid-demo degrades invisibly.

