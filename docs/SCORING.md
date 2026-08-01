# Scoring, and what it does not mean

Every number InfraPilot shows comes from the formulas below. This page exists so
they can be argued with rather than taken on trust — including the places where
the model is deliberately simpler than reality.

## Resilience score

```
score = 100 × (1 − Σ(criticality_i × impact_i) / Σ(criticality_i))

impact:  failed = 1.0    degraded = 0.5    healthy = 0    hardened = 0
```

Rounded to an integer. Criticality is an integer 1–10 assigned per asset in
`backend/seed/seed_data.py`.

**The seed city scores 84, not 100.** An all-healthy graph would score 100; the
seed carries five pre-existing degradations representing known posture debt — a
partial fibre fault on the telecom ring, a data-centre cooling redundancy fault,
an unpatched VPN gateway, Substation B at reduced capacity, and a backup
generator overdue for service. That is why hardening can push the score *above*
its starting point: mitigations can address weaknesses that were already there.

Criticality values were tuned so the demo scenario lands on memorable numbers.
`python -m seed.calibrate` prints the baseline and every single-seed cascade;
`tests/test_cascade.py` pins them so a seed edit fails a test rather than
surprising anyone mid-demo.

## Cascade propagation

For each asset, sum the weights of its **failed** suppliers **per dependency
type**. If any single type reaches the asset's `failure_threshold` (default 0.7)
it fails; if any reaches 0.4 it degrades.

Per-type rather than global summation is deliberate: losing 0.5 of power and 0.5
of comms is not the same event as losing 1.0 of power, and adding them together
would invent cascades that would not happen.

### Known simplifications

- **Degraded assets do not propagate.** Only failed suppliers exert pressure. In
  reality a degraded substation stresses its dependants. This is a v1
  simplification that keeps the model deterministic and explainable; it makes
  cascades *conservative*, i.e. the real blast radius would be at least this
  large, never smaller.
- **No timing.** Propagation is instantaneous. Real cascades have latency, and
  the order of failures affects what operators can intervene on.
- **No probability.** One deterministic outcome per input. The engine interface
  leaves room for Monte Carlo; the PRD scoped it out for v1.

## Population impact

```
residents_affected = CITY_POPULATION × (score_before − score_after) / 100
```

**This is the resilience delta restated on a population scale. It is not an
independent measurement** and carries no information the score does not. It
exists because "348,000 residents" lands with an audience in a way that "41
points" does not.

It is computed this way rather than by summing each asset's `population_served`
because those figures overlap heavily — the same resident depends on power,
water *and* telecoms — so summing them reports more casualties than the city has
people. Bounded by `CITY_POPULATION` by construction. One implementation:
`population_from_score_delta()` in `app/engine/cascade.py`.

## Mitigation gain and value for money

`expected_resilience_gain` is measured, never estimated: the engine deep-copies
the graph, applies the mutation, re-runs the cascade from the same seeds, and
takes the difference. `test_recommendation_gain_is_real` asserts the round trip
with ±0 tolerance.

```
gain_per_10k = gain ÷ (cost_gbp ÷ 10,000)
```

**Costs are indicative planning figures, not quotes.** They are assigned per
mutation *type* in `app/recommendations/rules.py` — segmentation £12k, added
redundancy £45k, a new path £30k — not derived from any real procurement data.
The ranking they produce is therefore only as good as those constants, and a
real deployment would replace them with the operator's own cost model. The
ordering logic is the contribution; the numbers are placeholders.

Mitigations are **not independent**. Approving one re-scores the rest against
the hardened graph, and any whose value has been absorbed drop to `superseded`
rather than continuing to advertise a gain that no longer exists.

## Confidence

A sensitivity analysis, not a model-reported probability. Each mitigation's gain
is re-measured across six worlds with perturbed failure thresholds; confidence
is the share of those worlds where the gain holds to within 80%.

Four worlds shift every threshold the same way (the whole city becoming more or
less fragile at once) and two move neighbours in opposite directions. Both
matter: correlated shifts test whether a mitigation survives a generally weaker
grid, alternating ones test whether it depends on one specific asset holding
while its neighbour gives. Using only alternating offsets made every mitigation
score 1.00, which is not a useful signal.

The unjittered world is deliberately excluded: scoring it would hand every
positive mitigation a free 1/N and put a floor under confidence it had not
earned.

## Structural metrics

`single_points_of_failure` are articulation points of the **undirected**
projection of the dependency graph. This ignores direction, which is a real
limitation: it can flag an asset as a cut vertex when the dependency only runs
one way. The Hospital appears in the list for exactly this reason — the Backup
Generator connects to the rest of the graph only through it, even though the
Hospital does not supply anything.

For "what would actually hurt most if it failed", the cascade is the honest
answer, not this metric — run each asset as a seed and compare blast radius.
Betweenness centrality is likewise a structural hint about flow concentration,
not a claim about operational importance.
