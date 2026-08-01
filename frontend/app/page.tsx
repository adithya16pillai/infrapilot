"use client";

import { ChevronRight, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AppShell,
  Card,
  CardRow,
  CityViewButton,
  PageHeader,
} from "@/components/AppShell";
import { ScoreCounter } from "@/components/ScoreCounter";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

const STATUS_COLOUR: Record<string, string> = {
  healthy: "var(--ip-grey-400)",
  degraded: "var(--ip-orange)",
  failed: "var(--ip-red)",
  hardened: "var(--ip-green)",
};

export default function DashboardPage() {
  const router = useRouter();
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
    // Reflects a completed simulation within 2s without a refresh.
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, []);

  const totalAssets = data
    ? Object.values(data.status_breakdown).reduce((sum, count) => sum + count, 0)
    : 0;

  return (
    <AppShell>
      <PageHeader
        title="Resilience posture"
        subtitle="City-wide view for executive reporting"
        actions={
          <div className="flex items-center gap-6">
            {data && <ScoreCounter score={data.resilience_score} label="Current score" />}
            <CityViewButton />
          </div>
        }
      />

      <div className="flex-1 overflow-y-auto">
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
            <Card
              title="Highest risk asset"
              href={`/city?asset=${data.highest_risk_asset.id}`}
            >
              <p className="text-[19px] font-medium text-neutral-100">
                {data.highest_risk_asset.name}
              </p>
              <p className="mt-1 font-mono text-[11px] text-neutral-500">
                criticality {data.highest_risk_asset.criticality}/10 · most
                dependents in the city
              </p>
            </Card>

            <Card title="Critical assets" href="/assets">
              <p className="font-mono text-4xl font-bold text-neutral-100">
                {data.critical_assets}
              </p>
              <p className="mt-1 font-mono text-[11px] text-neutral-500">
                of {totalAssets} at criticality ≥ 8
              </p>
            </Card>

            <Card title="Residents at risk" href="/simulations">
              <p className="font-mono text-4xl font-bold text-[var(--ip-orange)]">
                {(data.estimated_population_impact / 1000).toFixed(0)}k
              </p>
              <p className="mt-1 font-mono text-[11px] text-neutral-500">
                worst simulated scenario to date
              </p>
            </Card>

            <Card title="Operational status" href="/assets">
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

            <Card title="Top supply chain risks" href="/risks" className="col-span-2">
              {data.top_supply_chain_risks.length === 0 ? (
                <p className="font-mono text-[11px] text-neutral-600">No findings.</p>
              ) : (
                <div className="space-y-1">
                  {data.top_supply_chain_risks.map((finding) => (
                    <CardRow
                      key={finding.id}
                      href={`/city?asset=${finding.asset_id}`}
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-[11.5px] text-neutral-200">
                          {finding.package}
                        </span>
                        <span className="shrink-0 font-mono text-[11px] text-[var(--ip-orange)]">
                          impact {finding.operational_impact}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate font-mono text-[10px] text-neutral-500">
                        {finding.chain_names?.join(" → ") || finding.asset_name}
                      </p>
                    </CardRow>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Pending approvals" href="/approvals" className="col-span-2">
              {data.pending_recommendations.length === 0 ? (
                <p className="font-mono text-[11px] text-neutral-600">
                  Nothing awaiting review.
                </p>
              ) : (
                <div className="space-y-1">
                  {data.pending_recommendations.map((rec) => (
                    <CardRow
                      key={rec.id}
                      href={`/city?simulation=${rec.simulation_id}&rec=${rec.id}`}
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-[11.5px] text-neutral-300">
                          {rec.title}
                        </span>
                        <span className="shrink-0 font-mono text-[11px] text-[var(--ip-green)]">
                          +{rec.expected_resilience_gain}
                        </span>
                      </div>
                      <p className="mt-0.5 font-mono text-[10px] text-neutral-500">
                        {rec.cost_estimate} · {rec.gain_per_10k?.toFixed(1)} pts / £10k
                      </p>
                    </CardRow>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Recent simulations" href="/simulations" className="col-span-4">
              {data.recent_simulations.length === 0 ? (
                <p className="py-3 font-mono text-[11px] text-neutral-600">
                  No simulations yet — open the city view and run one.
                </p>
              ) : (
                <table className="w-full text-left">
                  <thead>
                    <tr className="font-mono text-[10px] tracking-wider text-neutral-600 uppercase">
                      <th className="pb-2 font-normal">Scenario</th>
                      <th className="pb-2 font-normal">Status</th>
                      <th className="pb-2 text-right font-normal">Score</th>
                      <th className="pb-2 text-right font-normal">Delta</th>
                      <th className="pb-2" />
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
                          className="cursor-pointer border-t border-[var(--ip-grey-800)] text-[12px] transition hover:bg-white/5"
                          onClick={(event) => {
                            // Beat the card behind us to the click.
                            event.stopPropagation();
                            router.push(`/city?simulation=${sim.id}`);
                          }}
                          data-testid="simulation-row"
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
                          <td className="py-2 pl-3 text-right">
                            <ChevronRight className="ml-auto h-3.5 w-3.5 text-neutral-600" />
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
      </div>

      <footer className="flex shrink-0 items-center gap-2 border-t border-[var(--ip-grey-700)] px-6 py-2.5">
        <ShieldCheck className="h-3.5 w-3.5 text-[var(--ip-green)]" />
        <p className="font-mono text-[10.5px] text-neutral-500">
          All figures derive from simulations against the resilience model. No live
          system is ever modified.
        </p>
      </footer>
    </AppShell>
  );
}
