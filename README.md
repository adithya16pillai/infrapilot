# InfraPilot

**AI resilience copilot for critical infrastructure.** Describe an attack in plain
English; an agent decides which analyses to run, a NetworkX engine computes the
cascade, and every mitigation it offers is scored by re-simulation — not by an LLM
guessing a number.

Built for the Cursor Cybersecurity London hackathon.

---

## Run it

Two terminals, no cloud accounts, no API keys required.

```bash
# 1. Backend  (http://127.0.0.1:8000)
cd backend
pip install -r requirements.txt
python -m seed.seed --reset
python -m uvicorn app.main:app --port 8000

# 2. Frontend (http://localhost:3000)
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** — the dashboard. **City view** (top right, or in
the sidebar) is the graph.

To enable the Claude planner, `cp backend/.env.example backend/.env`, set
`ANTHROPIC_API_KEY`, restart the API, then:

```bash
cd backend && python verify_planner.py
```

That drives four real queries through the agent and fails loudly if it stops
selecting analyses per question. Everything works without a key — see
*Degradation* below.

## Navigation

| Route | What it is |
|---|---|
| `/` | Dashboard — posture, status mix, top risks, pending approvals, recent runs. Every tile deep-links. |
| `/city` | The graph. Launch scenarios, watch the agent, approve mitigations. |
| `/assets` | All 12 assets: criticality, dependants, findings, status. |
| `/approvals` | Every mitigation awaiting a decision, best value for money first. |
| `/risks` | Supply chain findings, the OSSPrey explainer, and the impact comparison. |
| `/simulations` | Full history. Click any run to replay it on the graph. |
| `/health` | Which execution path is live for each integration. |

Deep links carry state: `/city?simulation=<id>` replays a past run in the exact
graph state it produced, `/city?asset=<id>` opens that asset's detail sheet, and
`/city?simulation=<id>&rec=<id>` highlights a specific mitigation.

> Profile and Sign out are presentational. This build ships no authentication
> (a stated non-goal) — Sign out is deliberately disabled rather than faking a
> session, and the profile popover says so.

---

## The demo (3 minutes)

| Time | Beat | What you see |
|---|---|---|
| 0:00 | Landing | 12 interdependent assets. Resilience **84** — not 100, because the city already carries five known posture issues (degraded telecom ring, data-centre cooling fault, unpatched VPN gateway, Substation B at reduced capacity, generator overdue service). |
| 0:20 | Click *Ransomware on Control Centre* | The agent's investigation streams step by step: resolve → cascade → metrics → rank. |
| 0:50 | The cascade lands | Control Centre → Substation A → Traffic Management fail. Hospital, Emergency Services and the Water Plant degrade. Score counts down **84 → 43**. ~348,000 residents affected. |
| 1:20 | "The agent chose which analyses to run" | Click *Biggest single point of failure?* — it runs `graph_metrics` **only**, no cascade. Same agent, different plan. |
| 1:50 | Supply chain | Open the Control Centre. The same-severity flagged package outranks the Data Centre's because its cascade reaches the Hospital. |
| 2:15 | Approve *Segment Control Centre / Substation A control plane* | Score climbs **43 → 57**. Approve two more: **→ 68**. "The AI recommends. The human approves. Nothing touches live systems." |
| 2:45 | `/dashboard` | Posture, trend, pending approvals, impact-ranked supply chain risks. |

Hit **Reset city** between runs.

### The demo numbers are measured, not chosen

The PRD sketched 84 → 61 → 88 before the engine existed. The engine says
**84 → 43 → 68**, so the script quotes the engine. `python -m seed.calibrate`
prints these from the seed graph, and `tests/test_cascade.py` pins them, so a
seed edit fails a test rather than surprising you on stage.

---

## How it works

```
Next.js :3000  ──REST──▶  FastAPI :8000  ──▶ app/engine/  (pure NetworkX)
     ▲                         │
     └────── SSE ──────────────┤──▶ app/agent/   Claude tool-use loop │ rule router
      /simulations/{id}/stream ├──▶ app/osprey/  mock │ live
                               └──▶ SQLite       (the PRD's Postgres schema, verbatim)
```

`app/engine/` is pure: dict in, dict out, no I/O. That is what lets the identical
code run in-process, inside a pytest, or inside a Modal function.

### Three things that are real, not staged

**The agent genuinely selects analyses.** Not a fixed pipeline — the tool
sequence differs by question:

| Question | Tools it runs |
|---|---|
| "What happens if the Water Treatment Plant loses power?" | `resolve_assets` → `run_cascade` → `graph_metrics` → `rank_mitigations` |
| "What is our biggest single point of failure?" | `resolve_assets` → `graph_metrics` — **no cascade** |
| "Which packages are a supply chain risk?" | `resolve_assets` → `osprey_scan` |
| "Simulate an attack on the Atlantis Sea Gate" | `resolve_assets` → stops, names the valid assets |

**Every advertised gain is a measured delta.** For each candidate mitigation the
engine deep-copies the graph, applies the change, and re-runs the cascade.
Confidence is a real sensitivity analysis: the gain is re-measured under jittered
failure thresholds, and confidence is the share of those runs where it holds.
The LLM may reword a title; it never touches a number.

Mitigations rank by **resilience points per £10k**, not raw gain. Ranking on gain
alone structurally favours the most expensive fix, which is the opposite of the
budget question an operator is actually asking:

```
Segment Control Centre / Substation A control plane  +14  £12k  11.7 pts/£10k
Provision independent dispatch comms                  +5  £12k   4.2
Segment Substation A to Hospital                      +5  £12k   4.2
Segment Control Centre to Water Treatment             +4  £12k   3.3
Deploy redundant protection relays at Substation A   +10  £45k   2.2   <- biggest gain, worst value
```

Mitigations are not independent, so **approving one re-scores the rest**. Once the
control plane is segmented, "add redundancy at Substation A" is worth nothing — it
drops to `superseded` instead of advertising a stale +10.

**One code path mutates the graph.** `POST /api/recommendations/{id}/apply`, reached
only by a human clicking Approve. `test_no_autonomous_apply_path` asserts no other
route can.

**The attack path names its mechanism.** The critical path is returned as numbered
hops rather than a list of node names, because a security audience reads an attack
as a sequence of mechanisms:

```
0. Control Centre      compromised
1. Substation A        failed    via control link from Control Centre · weight 0.75
2. Traffic Management  failed    via power feed  from Substation A   · weight 0.85
```

**Supply chain findings are ranked by consequence, not severity.** OSSPrey detects
malicious packages by *behaviour* — install-time filesystem writes, obfuscated
payloads, maintainer-handover takeovers — which catches compromised releases
carrying no CVE at all. That tells you how malicious a package is; it cannot tell
you how much it matters to this city. InfraPilot supplies the second half:

```
impact = severity_weight × downstream_criticality(asset)

node-ipc@10.1.1      on Control Centre   HIGH   impact 36.0   ← cascade reaches the Hospital
event-stream@3.3.6   on Data Centre      HIGH   impact 10.5   ← cascade stops at the Control Centre
```

Same severity, 3.4× different priority. `/risks` shows that side by side.

---

## Degradation

Nothing in the demo path needs the network. Each integration fails soft:

| If this is unavailable | What happens |
|---|---|
| `ANTHROPIC_API_KEY` unset, or the API errors mid-run | Deterministic router plans the investigation and emits an identical event stream. The UI cannot tell. |
| Modal | `USE_MODAL=false` runs the same engine module in-process. |
| OSSPrey API | `OSPREY_MODE=mock` returns findings in the live API's shape. |
| SSE connection drops | The hook falls back to polling `/events`. |

`GET /api/health` reports which path is live. `overmind: fallback` and
`osprey: mock` are expected, not failures.

---

## Tests

```bash
cd backend  && python -m pytest -q      # 29 passed
cd frontend && npx playwright test      # 9 passed
```

The Playwright suite **is** the demo rehearsal — it drives the exact click path
above at 1280×720 and asserts the score lands on 43, then on 43 + the claimed
gain. Run it before walking to the stage.

Notable cases: `test_cascade_determinism`, `test_cascade_control_centre` (golden),
`test_recommendation_gain_is_real`, `test_no_autonomous_apply_path`,
`test_supply_chain_ranked_by_operational_impact`, `test_unknown_asset_query`.

`tests/test_planner_llm.py` drives the Claude tool-use loop with a scripted fake
client, so the parts that are ours — tool dispatch, the assistant/tool_result
message shape the API requires, event emission, error handling, refusal fallback
— are proven without a key. `verify_planner.py` is the live counterpart.

---

## Scoring

```
score = 100 × (1 − Σ(criticality × impact) / Σ(criticality))     failed = 1.0, degraded = 0.5
```

Population impact is derived from the **share of critical-service capacity lost**,
not by summing each asset's `population_served` — those overlap heavily (the same
resident depends on power, water and telecoms), so summing them would report more
casualties than the city has people.

Propagation sums failed-supplier weights **per dependency type**: losing 0.5 of
power and 0.5 of comms is not the same as losing 1.0 of power, and conflating them
overstates cascades.

---

## Known gaps

- Seed data only. No real SCADA/OT telemetry — that is the roadmap, not a claim.
- No auth or multi-tenancy; single demo workspace.
- Deterministic cascade only. The engine interface leaves room for Monte Carlo.
- Desktop only, 1280×720 target.
- Modal and Overmind are wired as flags but not deployed — the fallbacks are what run.
