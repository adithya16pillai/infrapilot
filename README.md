# InfraPilot

**AI resilience copilot for critical infrastructure — simulate the attack, measure the fix.**

Attack-path analysis for cities: an agent picks the analyses, a deterministic
engine computes the cascade, and every mitigation is scored by re-simulation
behind a human approval gate.

Built for the Cursor Cybersecurity London hackathon.

---

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

### Claude — the planner itself

```bash
cp backend/.env.example backend/.env   # then set ANTHROPIC_API_KEY
python verify_planner.py               # four real queries, fails loudly on regression
```

Without a key the deterministic router plans instead and emits the same events.
`tests/test_planner_llm.py` proves the tool-use loop against a scripted client,
so the code is verified even before a key exists.

---

## Navigation

| Route | What it is |
|---|---|
| `/` | Dashboard — posture, status mix, top risks, pending approvals, recent runs. Every section deep-links. |
| `/city` | The graph. Launch scenarios, watch the agent, approve mitigations. |
| `/assets` | All 12 assets: criticality, dependants, findings, status. |
| `/approvals` | Every mitigation awaiting a decision, best value first. |
| `/risks` | Supply chain findings, the OSSPrey explainer, and the impact comparison. |
| `/simulations` | Full history. Click any run to replay it on the graph. |
| `/health` | Which execution path is live for each integration. |

Deep links carry state: `/city?simulation=<id>` replays a past run in the exact
graph state it produced, `/city?asset=<id>` opens that asset's detail sheet, and
`/city?simulation=<id>&rec=<id>` highlights a mitigation.

> Profile and Sign out are presentational. This build ships no authentication (a
> stated non-goal) — Sign out is deliberately disabled rather than faking a
> session.

---

## The demo (3 minutes)

| Time | Beat | What you see |
|---|---|---|
| 0:00 | Landing | 12 interdependent assets. Resilience **84** — not 100, because the city carries five known posture issues. |
| 0:20 | Click *Ransomware on Control Centre* | The investigation streams step by step: resolve → cascade → metrics → rank. |
| 0:50 | The cascade lands | Control Centre → Substation A → Traffic Management fail. Hospital, Emergency Services and the Water Plant degrade. **84 → 43**. ~348,000 residents affected. |
| 1:20 | "The agent chose which analyses to run" | Type *What is our biggest single point of failure?* — `graph_metrics` only, no cascade. |
| 1:50 | Supply chain | Open `/risks`. Same severity, 3.4× different priority, because one cascade reaches the Hospital. |
| 2:15 | Approve the top mitigation | **43 → 57**. Approve two more: **→ 68**. "The AI recommends. The human approves. Nothing touches live systems." |
| 2:45 | Dashboard | Posture, status mix, pending approvals, impact-ranked risks. |

Hit **Reset city** between runs.

### The demo numbers are measured, not chosen

The PRD sketched 84 → 61 → 88 before the engine existed. The engine says
**84 → 43 → 68**, so the script quotes the engine. `python -m seed.calibrate`
prints them and `tests/test_cascade.py` pins them, so a seed edit fails a test
rather than surprising you on stage.

---

## Architecture

```
Next.js :3000  ──REST──▶  FastAPI :8000  ──▶ app/engine/  (pure NetworkX)
     ▲                         │
     └────── SSE ──────────────┤──▶ app/agent/   Claude tool-use loop │ rule router
      /simulations/{id}/stream ├──▶ app/osprey/  mock │ live
                               └──▶ SQLite       (the PRD's Postgres schema, verbatim)
```

Scoring, propagation and the confidence method — including their
simplifications — are documented in **[docs/SCORING.md](docs/SCORING.md)**.

---

## Degradation

Nothing on the demo path needs the network.

| If this is unavailable | What happens |
|---|---|
| `ANTHROPIC_API_KEY` unset, or the API errors mid-run | Deterministic router plans the investigation and emits an identical event stream. |
| Modal | `USE_MODAL=false` runs the same engine module in-process. |
| OSSPrey API | `OSPREY_MODE=mock` returns findings in the live API's shape. |
| Overmind | The built-in planner covers the same interface. |
| SSE connection drops | The hook falls back to polling `/events`. |

---

## Tests

```bash
cd backend  && python -m pytest -q      # 32 passed
cd frontend && npx playwright test      # 10 passed
```

The Playwright suite **is** the demo rehearsal — it drives the exact click path
at 1280×720 and asserts the score lands on 43, then on 43 + the claimed gain.
Run it before walking to the stage.

Notable cases: `test_cascade_control_centre` (golden),
`test_recommendation_gain_is_real`, `test_no_autonomous_apply_path` (fingerprints
the graph and exercises every other route rather than grepping source),
`test_untrusted_finding_text_is_fenced_before_it_reaches_the_planner`,
`test_decisions_are_attributable`.

---

## Secrets

No credentials are committed. `backend/.env.example` is the only env file in the
repo and its values are blank.

- `.gitignore` covers `.env*` (except `.env.example`), `*.pem`, `*.key`, `*.p12`,
  `id_rsa*`, `credentials.json`, `secrets.json`, `.netrc`, `*.db`, `*.log` and
  `node_modules/`.
- The API key is read from the environment at startup and is never logged,
  echoed in a response, or written to the database.
- Error strings that reach `simulations.error` and the SSE stream pass through a
  redactor that strips credential-shaped tokens — that is the one path where
  upstream exception text could carry a header into something a browser renders
  and a database keeps.

---

## Known gaps

**Modelling**
- Degraded assets do not propagate; only failed suppliers exert pressure. This
  makes cascades conservative, never overstated.
- `single_points_of_failure` uses articulation points on the *undirected*
  projection, so it ignores dependency direction. The Hospital appears because
  the Backup Generator reaches the graph only through it. For "what hurts most",
  seed the cascade at each asset and compare blast radius.
- Betweenness is a structural hint about flow concentration, not a claim about
  operational importance.
- Mitigation costs are indicative planning figures assigned per mutation type,
  not quotes. The ordering logic is the contribution; the numbers are placeholders.
- Population impact is the resilience delta restated on a population scale, not
  an independent measurement.

**Security posture of this build**
- No authentication. `POST /api/simulate` and `POST /api/reset` are
  unauthenticated and unbounded, and simulate can spend Anthropic tokens. Fine
  for a single-operator demo on localhost, not for anything exposed.
- Decisions record an actor, but with no auth it is a placeholder.
- Untrusted third-party text is fenced and the planner told to treat it as data.
  That is defence in depth, not a proof — an agent with tools and
  attacker-influenced input deserves a red-team pass before production.

**Scope**
- Seed data only. No real SCADA/OT telemetry — that is the roadmap, not a claim.
- Deterministic cascade only; the engine interface leaves room for Monte Carlo.
- Desktop only, 1280×720 target.
