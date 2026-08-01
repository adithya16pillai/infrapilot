"use client";

import { AnimatePresence, motion } from "framer-motion";
import { LayoutDashboard, RotateCcw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { InfraGraph } from "@/components/graph/InfraGraph";
import { KillChain } from "@/components/KillChain";
import { NodeDetailSheet } from "@/components/NodeDetailSheet";
import { ReasoningStream } from "@/components/ReasoningStream";
import { RecommendationCard } from "@/components/RecommendationCard";
import { ScenarioLauncher } from "@/components/ScenarioLauncher";
import { ScoreCounter } from "@/components/ScoreCounter";
import { api } from "@/lib/api";
import type {
  CascadeResult,
  GraphResponse,
  Recommendation,
  SimulationEvent,
  SupplyChainFinding,
} from "@/lib/types";
import { useSimulation } from "@/lib/useSimulation";

function CityView() {
  const params = useSearchParams();
  const replayId = params.get("simulation");
  const focusAsset = params.get("asset");
  const highlightRec = params.get("rec");

  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [findings, setFindings] = useState<SupplyChainFinding[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busyRec, setBusyRec] = useState<string | null>(null);

  const sim = useSimulation();
  const [liveResult, setLiveResult] = useState<CascadeResult | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [replayEvents, setReplayEvents] = useState<SimulationEvent[]>([]);
  const [replaySummary, setReplaySummary] = useState<string | null>(null);

  const loadCity = useCallback(async () => {
    try {
      const graphData = await api.graph();
      setGraph(graphData);
      setLoadError(null);
      // Findings are a nice-to-have badge; never block the graph on them.
      api
        .supplyChain()
        .then((body) => setFindings(body.findings ?? []))
        .catch(() => setFindings([]));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load the city graph");
    }
  }, []);

  useEffect(() => {
    void loadCity();
  }, [loadCity]);

  // Deep link: /city?asset=<id> opens that asset's detail sheet.
  useEffect(() => {
    if (focusAsset) setSelected(focusAsset);
  }, [focusAsset]);

  // Deep link: /city?simulation=<id> reconstructs a past run — the graph state
  // it produced, its reasoning trace, and its mitigations.
  useEffect(() => {
    if (!replayId) return;
    let cancelled = false;
    (async () => {
      try {
        const [detail, events] = await Promise.all([
          api.simulation(replayId),
          api.events(replayId).catch(() => []),
        ]);
        if (cancelled) return;
        setLiveResult(detail.result);
        setRecommendations(detail.recommendations);
        setReplayEvents(events);
        setReplaySummary(detail.summary);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            err instanceof Error ? err.message : "Could not load that simulation",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [replayId]);

  useEffect(() => {
    if (sim.detail?.result) setLiveResult(sim.detail.result);
    if (sim.detail) setRecommendations(sim.detail.recommendations);
  }, [sim.detail]);

  const findingCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    findings.forEach((finding) => {
      counts[finding.asset_id] = (counts[finding.asset_id] ?? 0) + 1;
    });
    return counts;
  }, [findings]);

  const assetNames = useMemo(() => {
    const names: Record<string, string> = {};
    graph?.assets.forEach((asset) => {
      names[asset.id] = asset.name;
    });
    return names;
  }, [graph]);

  // A replayed run shows its stored trace; a live run shows the streaming one.
  const shownEvents = sim.events.length > 0 ? sim.events : replayEvents;
  const shownSummary = sim.detail?.summary ?? replaySummary;

  const baselineScore = graph?.resilience_score ?? 100;
  const currentScore = liveResult?.resilience_score_after ?? baselineScore;
  const previousScore = liveResult?.resilience_score_before ?? null;

  const approve = async (id: string) => {
    setBusyRec(id);
    try {
      const outcome = await api.apply(id);
      setLiveResult(outcome.result);
      setRecommendations(await api.recommendations(outcome.recommendation.simulation_id));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to apply mitigation");
    } finally {
      setBusyRec(null);
    }
  };

  const reject = async (id: string) => {
    setBusyRec(id);
    try {
      const rejected = await api.reject(id);
      setRecommendations(await api.recommendations(rejected.simulation_id));
    } finally {
      setBusyRec(null);
    }
  };

  const resetCity = async () => {
    await api.reset();
    sim.reset();
    setLiveResult(null);
    setRecommendations([]);
    await loadCity();
  };

  const pending = recommendations.filter((rec) => rec.status === "pending");
  const settled = recommendations.filter((rec) => rec.status !== "pending");

  return (
    <AppShell>
      <header className="flex shrink-0 items-start justify-between border-b border-[var(--ip-grey-700)] px-6 py-3.5">
        <div>
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-[24px] font-semibold tracking-tight text-neutral-50">
              City View
            </h1>
            {replayId && (
              <span className="rounded border border-[var(--ip-grey-700)] px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-neutral-500 uppercase">
                replaying {replayId.slice(0, 12)}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[13px] text-neutral-500">
            Predict cascading infrastructure failures before they happen.
          </p>
        </div>

        <div className="flex items-center gap-5">
          <Link
            href="/"
            className="flex items-center gap-1.5 font-mono text-[11px] text-neutral-500 transition hover:text-neutral-200"
          >
            <LayoutDashboard className="h-3.5 w-3.5" />
            Dashboard
          </Link>
          <button
            onClick={resetCity}
            className="flex items-center gap-1.5 font-mono text-[11px] text-neutral-500 transition hover:text-neutral-200"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset city
          </button>
          <ScoreCounter score={currentScore} previous={previousScore} />
        </div>
      </header>

      <div className="shrink-0 border-b border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]/40 px-6 py-3">
        <ScenarioLauncher
          presets={graph?.presets ?? []}
          disabled={sim.running || !graph}
          onLaunch={(query, presetId) => {
            setLiveResult(null);
            setRecommendations([]);
            void sim.start(query, presetId);
          }}
        />
      </div>

      <div className="flex min-h-0 flex-1">
        <section className="relative min-w-0 flex-1">
          {loadError ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
              <p className="max-w-md text-[13px] leading-relaxed text-[var(--ip-red)]">
                {loadError}
              </p>
              <button
                onClick={() => void loadCity()}
                className="rounded border border-[var(--ip-grey-700)] px-3 py-1.5 text-[12px] text-neutral-300 hover:border-[var(--ip-blue)]"
              >
                Retry
              </button>
            </div>
          ) : graph ? (
            <InfraGraph
              assets={graph.assets}
              dependencies={graph.dependencies}
              statuses={sim.statuses ?? liveResult?.statuses ?? null}
              result={liveResult}
              findingCounts={findingCounts}
              onSelect={setSelected}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <span className="ip-blink font-mono text-[12px] text-neutral-600">
                loading city graph…
              </span>
            </div>
          )}

          <AnimatePresence>
            {liveResult && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                className="pointer-events-none absolute bottom-4 left-4 flex gap-4 rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]/95 px-4 py-2.5 backdrop-blur"
              >
                {[
                  ["Blast radius", `${liveResult.blast_radius} assets`],
                  ["Failed", `${liveResult.failed.length}`],
                  [
                    "Residents affected",
                    liveResult.estimated_population_impact.toLocaleString(),
                  ],
                  ["Compute", `${liveResult.compute_ms}ms`],
                ].map(([label, value]) => (
                  <div key={label}>
                    <div className="font-mono text-[9px] tracking-wider text-neutral-500 uppercase">
                      {label}
                    </div>
                    <div className="font-mono text-[13px] text-neutral-100">{value}</div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        <aside className="flex w-[360px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-[var(--ip-grey-700)] p-3">
          {/* Sized so the first mitigation card is on screen at 1280x720 —
              the approve step is the demo's payoff and must not need a scroll. */}
          <div className="h-[204px] shrink-0">
            <ReasoningStream
              events={shownEvents}
              running={sim.running}
              error={sim.error}
            />
          </div>

          {shownSummary && (
            <details className="group shrink-0 rounded-lg border border-[var(--ip-blue)]/30 bg-[var(--ip-blue)]/5 p-3">
              <summary className="cursor-pointer font-mono text-[10px] tracking-[0.14em] text-[var(--ip-blue)] uppercase marker:content-['']">
                Agent assessment
                <span className="ml-1.5 text-neutral-600 group-open:hidden">— expand</span>
              </summary>
              <p className="mt-1.5 text-[12px] leading-relaxed text-neutral-300">
                {shownSummary}
              </p>
            </details>
          )}

          {liveResult && (liveResult.kill_chain?.length ?? 0) > 0 && (
            <section className="shrink-0 rounded-lg border border-[var(--ip-red)]/30 bg-[var(--ip-red)]/[0.04] p-3">
              <h3 className="mb-2.5 text-[13px] font-semibold text-neutral-100">
                Attack path
              </h3>
              <KillChain hops={liveResult.kill_chain ?? []} names={assetNames} />
            </section>
          )}

          {recommendations.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[13px] font-semibold text-neutral-100">
                Recommended mitigations
                <span className="ml-1.5 font-mono text-[10px] font-normal text-neutral-500">
                  best value first
                </span>
              </h3>
              {pending.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  recommendation={rec}
                  onApprove={approve}
                  onReject={reject}
                  busy={busyRec === rec.id}
                  highlighted={rec.id === highlightRec}
                />
              ))}
              {settled.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  recommendation={rec}
                  onApprove={approve}
                  onReject={reject}
                  busy={false}
                />
              ))}
            </div>
          )}
        </aside>
      </div>

      <footer className="flex shrink-0 items-center gap-2 border-t border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] px-6 py-2">
        <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-[var(--ip-green)]" />
        <p className="font-mono text-[10.5px] tracking-wide text-neutral-400">
          InfraPilot never applies changes to live systems. All actions modify the
          resilience model only. Every recommendation requires human approval.
        </p>
      </footer>

      <NodeDetailSheet assetId={selected} onClose={() => setSelected(null)} />
    </AppShell>
  );
}

export default function CityPage() {
  // useSearchParams needs a Suspense boundary; the deep links (?simulation,
  // ?asset, ?rec) all read from it.
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-[var(--ip-grey-950)]">
          <span className="ip-blink font-mono text-[12px] text-neutral-600">
            loading city graph…
          </span>
        </div>
      }
    >
      <CityView />
    </Suspense>
  );
}
