"use client";

import { ArrowLeft, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ScoreCounter } from "@/components/ScoreCounter";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

const STATUS_COLOUR: Record<string, string> = {
  healthy: "var(--ip-grey-400)",
  degraded: "var(--ip-orange)",
  failed: "var(--ip-red)",
  hardened: "var(--ip-green)",
};

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] p-4 ${className}`}
    >
      <h2 className="mb-3 font-mono text-[10px] tracking-[0.14em] text-neutral-400 uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <p className="py-4 text-center font-mono text-[11px] text-neutral-600">
        Run two simulations to see a trend.
      </p>
    );
  }
  const max = Math.max(...values, 100);
  const min = Math.min(...values, 0);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 100 - ((value - min) / Math.max(max - min, 1)) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-16 w-full">
      <polyline
        points={points}
        fill="none"
        stroke="var(--ip-blue)"
        strokeWidth="2.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .dashboard()
        .then((summary) => {
          setData(summary);
          setError(null);
        })
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to load dashboard"),
        );
    void load();
    // F8 AC#1: reflects a completed simulation within 2s without a refresh.
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, []);

  const totalAssets = data
    ? Object.values(data.status_breakdown).reduce((sum, count) => sum + count, 0)
    : 0;

  return (
    <main className="min-h-screen bg-[var(--ip-grey-950)]">
      <header className="flex items-center justify-between border-b border-[var(--ip-grey-700)] px-6 py-3.5">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 font-mono text-[11px] text-neutral-500 transition hover:text-neutral-200"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Graph
          </Link>
          <div>
            <h1 className="text-[17px] font-semibold tracking-tight text-neutral-50">
              Resilience posture
            </h1>
            <p className="text-[12px] text-neutral-500">
              City-wide view for executive reporting
            </p>
          </div>
        </div>
        {data && <ScoreCounter score={data.resilience_score} label="Current score" />}
      </header>

      {error && (
        <p className="m-6 rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
          {error}
        </p>
      )}

      {!data && !error && (
        <div className="grid grid-cols-4 gap-4 p-6">
          {[...Array(8)].map((_, index) => (
            <div
              key={index}
              className="h-28 animate-pulse rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]"
            />
          ))}
        </div>
      )}

      {data && (
        <div className="grid grid-cols-4 gap-4 p-6">
          <Card title="Highest risk asset">
            <p className="text-[17px] font-medium text-neutral-100">
              {data.highest_risk_asset.name}
            </p>
            <p className="mt-1 font-mono text-[11px] text-neutral-500">
              criticality {data.highest_risk_asset.criticality}/10
            </p>
          </Card>

          <Card title="Critical assets">
            <p className="font-mono text-4xl font-bold text-neutral-100">
              {data.critical_assets}
            </p>
            <p className="mt-1 font-mono text-[11px] text-neutral-500">
              of {totalAssets} at criticality ≥ 8
            </p>
          </Card>

          <Card title="Residents at risk">
            <p className="font-mono text-4xl font-bold text-[var(--ip-orange)]">
              {(data.estimated_population_impact / 1000).toFixed(0)}k
            </p>
            <p className="mt-1 font-mono text-[11px] text-neutral-500">
              worst simulated scenario
            </p>
          </Card>

          <Card title="Score trend">
            <Sparkline values={data.score_trend} />
          </Card>

          <Card title="Operational status" className="col-span-1">
            <div className="space-y-2">
              {Object.entries(data.status_breakdown).map(([status, count]) => (
                <div key={status} className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: STATUS_COLOUR[status] }}
                  />
                  <span className="flex-1 font-mono text-[11px] text-neutral-400 capitalize">
                    {status}
                  </span>
                  <span className="font-mono text-[13px] text-neutral-100">{count}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Top supply chain risks" className="col-span-2">
            {data.top_supply_chain_risks.length === 0 ? (
              <p className="font-mono text-[11px] text-neutral-600">No findings.</p>
            ) : (
              <div className="space-y-2.5">
                {data.top_supply_chain_risks.map((finding) => (
                  <div key={finding.id}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono text-[11.5px] text-neutral-200">
                        {finding.package}
                      </span>
                      <span className="font-mono text-[11px] text-[var(--ip-orange)]">
                        impact {finding.operational_impact}
                      </span>
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] text-neutral-500">
                      {finding.chain.join(" → ") || finding.asset_name}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Pending approvals">
            {data.pending_recommendations.length === 0 ? (
              <p className="font-mono text-[11px] text-neutral-600">
                Nothing awaiting review.
              </p>
            ) : (
              <div className="space-y-2">
                {data.pending_recommendations.map((rec) => (
                  <div key={rec.id} className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[11.5px] text-neutral-300">
                      {rec.title}
                    </span>
                    <span className="shrink-0 font-mono text-[11px] text-[var(--ip-green)]">
                      +{rec.expected_resilience_gain}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Recent simulations" className="col-span-4">
            {data.recent_simulations.length === 0 ? (
              <p className="py-3 font-mono text-[11px] text-neutral-600">
                No simulations yet — run one from the graph view.
              </p>
            ) : (
              <table className="w-full text-left">
                <thead>
                  <tr className="font-mono text-[10px] tracking-wider text-neutral-600 uppercase">
                    <th className="pb-2 font-normal">Scenario</th>
                    <th className="pb-2 font-normal">Status</th>
                    <th className="pb-2 text-right font-normal">Score</th>
                    <th className="pb-2 text-right font-normal">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_simulations.map((sim) => {
                    const delta =
                      sim.score_after != null && sim.score_before != null
                        ? sim.score_after - sim.score_before
                        : null;
                    return (
                      <tr
                        key={sim.id}
                        className="border-t border-[var(--ip-grey-800)] text-[12px]"
                      >
                        <td className="max-w-md truncate py-2 text-neutral-300">
                          {sim.query}
                        </td>
                        <td className="py-2 font-mono text-[11px] text-neutral-500">
                          {sim.status}
                        </td>
                        <td className="py-2 text-right font-mono text-neutral-200">
                          {sim.score_before != null
                            ? `${sim.score_before} → ${sim.score_after}`
                            : "—"}
                        </td>
                        <td
                          className={`py-2 text-right font-mono ${
                            delta == null
                              ? "text-neutral-600"
                              : delta < 0
                                ? "text-[var(--ip-red)]"
                                : "text-[var(--ip-green)]"
                          }`}
                        >
                          {delta == null ? "—" : delta > 0 ? `+${delta}` : delta}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}

      <footer className="flex items-center gap-2 border-t border-[var(--ip-grey-700)] px-6 py-2.5">
        <ShieldCheck className="h-3.5 w-3.5 text-[var(--ip-green)]" />
        <p className="font-mono text-[10.5px] text-neutral-500">
          All figures derive from simulations against the resilience model. No live
          system is ever modified.
        </p>
      </footer>
    </main>
  );
}
