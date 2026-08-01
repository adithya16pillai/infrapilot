"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell, Card, CityViewButton, PageHeader } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { SimulationSummary } from "@/lib/types";

const STATUS: Record<string, string> = {
  complete: "text-[var(--ip-green)] border-[var(--ip-green)]/40",
  unresolved: "text-[var(--ip-orange)] border-[var(--ip-orange)]/40",
  failed: "text-[var(--ip-red)] border-[var(--ip-red)]/40",
  planning: "text-neutral-400 border-[var(--ip-grey-700)]",
};

export default function SimulationsPage() {
  const [rows, setRows] = useState<SimulationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .simulations()
        .then(setRows)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to load history"),
        );
    void load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <AppShell>
      <PageHeader
        title="Simulations"
        subtitle="Every investigation the agent has run — open one to replay it on the graph"
        actions={<CityViewButton />}
      />

      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
            {error}
          </p>
        )}

        {rows && rows.length === 0 && (
          <Card title="No simulations yet">
            <p className="text-[12.5px] text-neutral-500">
              Open the city view and launch a scenario — the history will appear
              here.
            </p>
          </Card>
        )}

        {rows && rows.length > 0 && (
          <Card title="History" hint={`${rows.length} runs`}>
            <div className="space-y-2">
              {rows.map((sim) => {
                const delta =
                  sim.score_after != null && sim.score_before != null
                    ? sim.score_after - sim.score_before
                    : null;
                return (
                  <Link
                    key={sim.id}
                    href={`/city?simulation=${sim.id}`}
                    data-testid="simulation-row"
                    className="flex items-start gap-3 rounded-lg border border-[var(--ip-grey-700)] bg-black/20 p-3.5 transition hover:border-[var(--ip-blue)]"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-[13px] text-neutral-100">
                          {sim.query}
                        </span>
                        <span
                          className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase ${
                            STATUS[sim.status] ?? STATUS.planning
                          }`}
                        >
                          {sim.status}
                        </span>
                      </div>
                      {sim.summary && (
                        <p className="mt-1 line-clamp-2 text-[11.5px] leading-relaxed text-neutral-500">
                          {sim.summary}
                        </p>
                      )}
                      <p className="mt-1 font-mono text-[10px] text-neutral-600">
                        {sim.id} · {new Date(sim.created_at).toLocaleTimeString()}
                        {sim.blast_radius != null &&
                          ` · blast radius ${sim.blast_radius}`}
                      </p>
                    </div>

                    <div className="shrink-0 text-right">
                      {sim.score_before != null ? (
                        <>
                          <div className="font-mono text-[15px] text-neutral-200">
                            {sim.score_before} → {sim.score_after}
                          </div>
                          <div
                            className={`font-mono text-[11px] ${
                              delta != null && delta < 0
                                ? "text-[var(--ip-red)]"
                                : "text-[var(--ip-green)]"
                            }`}
                          >
                            {delta != null && delta > 0 ? "+" : ""}
                            {delta}
                          </div>
                        </>
                      ) : (
                        <span className="font-mono text-[11px] text-neutral-600">
                          no cascade
                        </span>
                      )}
                    </div>
                    <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-neutral-600" />
                  </Link>
                );
              })}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
