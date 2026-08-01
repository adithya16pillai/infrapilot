"use client";

import { useEffect, useState } from "react";
import { AppShell, Card, CityViewButton, PageHeader } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";

/** Fallbacks are expected states here, not failures — labelled as such. */
const ROWS: { key: keyof Health; label: string; note: string }[] = [
  {
    key: "database",
    label: "Database",
    note: "SQLite, same schema as the specified Postgres model.",
  },
  {
    key: "modal",
    label: "Cascade engine",
    note: "The engine module is pure, so in-process and Modal execution are identical.",
  },
  {
    key: "planner",
    label: "Agent planner",
    note: "'llm' is the Claude tool-use loop; 'fallback' is the deterministic router. Both emit the same event stream.",
  },
  {
    key: "osprey",
    label: "OSSPrey",
    note: "'mock' returns representative findings in the live API's exact shape.",
  },
  {
    key: "overmind",
    label: "Overmind",
    note: "Not wired; the built-in planner covers the same interface.",
  },
];

function tone(value: string) {
  if (value === "ok" || value === "live" || value === "llm")
    return "text-[var(--ip-green)] border-[var(--ip-green)]/40";
  if (value.startsWith("error"))
    return "text-[var(--ip-red)] border-[var(--ip-red)]/40";
  return "text-neutral-400 border-[var(--ip-grey-700)]";
}

export default function HealthPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .health()
        .then(setHealth)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "API unreachable"),
        );
    void load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <AppShell>
      <PageHeader
        title="System health"
        subtitle="Which execution path is live for each integration"
        actions={<CityViewButton />}
      />

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {error && (
          <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
            {error}
          </p>
        )}

        {health && (
          <Card title="Integrations" hint="fallbacks are expected, not failures">
            <div className="space-y-2">
              {ROWS.map((row) => (
                <div
                  key={row.key}
                  className="flex items-start gap-3 border-t border-[var(--ip-grey-800)] py-2.5 first:border-t-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-neutral-100">{row.label}</div>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-neutral-500">
                      {row.note}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded border px-2 py-0.5 font-mono text-[10.5px] ${tone(health[row.key])}`}
                  >
                    {health[row.key]}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
