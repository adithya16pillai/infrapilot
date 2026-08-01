"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell, Card, CityViewButton, PageHeader } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { GraphResponse, SupplyChainFinding } from "@/lib/types";

const STATUS: Record<string, string> = {
  healthy: "text-[var(--ip-grey-400)] border-[var(--ip-grey-700)]",
  degraded: "text-[var(--ip-orange)] border-[var(--ip-orange)]/50",
  failed: "text-[var(--ip-red)] border-[var(--ip-red)]/50",
  hardened: "text-[var(--ip-green)] border-[var(--ip-green)]/50",
};

export default function AssetsPage() {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [findings, setFindings] = useState<SupplyChainFinding[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .graph()
      .then(setGraph)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load assets"),
      );
    api
      .supplyChain()
      .then((body) => setFindings(body.findings))
      .catch(() => setFindings([]));
  }, []);

  const counts: Record<string, number> = {};
  findings.forEach((f) => {
    counts[f.asset_id] = (counts[f.asset_id] ?? 0) + 1;
  });

  const dependents: Record<string, number> = {};
  graph?.dependencies.forEach((dep) => {
    dependents[dep.source] = (dependents[dep.source] ?? 0) + 1;
  });

  return (
    <AppShell>
      <PageHeader
        title="Assets"
        subtitle="Every modelled asset in the city, with its posture and dependants"
        actions={<CityViewButton />}
      />

      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
            {error}
          </p>
        )}

        {graph && (
          <Card title="City assets" hint={`${graph.assets.length} modelled`}>
            <table className="w-full text-left">
              <thead>
                <tr className="font-mono text-[10px] tracking-wider text-neutral-600 uppercase">
                  <th className="pb-2 pr-4 font-normal">Asset</th>
                  <th className="pb-2 pr-4 font-normal">Type</th>
                  <th className="pb-2 pr-6 text-right font-normal">Criticality</th>
                  <th className="pb-2 pr-6 text-right font-normal">Supplies</th>
                  <th className="pb-2 pr-10 text-right font-normal">Findings</th>
                  <th className="pb-2 pl-2 font-normal">Status</th>
                </tr>
              </thead>
              <tbody>
                {[...graph.assets]
                  .sort((a, b) => b.criticality - a.criticality)
                  .map((asset) => (
                    <tr
                      key={asset.id}
                      className="border-t border-[var(--ip-grey-800)] text-[12.5px] transition hover:bg-white/5"
                    >
                      <td className="py-2 pr-4">
                        <Link
                          href={`/city?asset=${asset.id}`}
                          className="block text-neutral-200 hover:text-[var(--ip-blue)]"
                          data-testid="asset-row"
                        >
                          {asset.name}
                          <span className="ml-2 font-mono text-[10px] text-neutral-600">
                            {asset.id}
                          </span>
                        </Link>
                      </td>
                      <td className="py-2 pr-4 font-mono text-[11px] text-neutral-500">
                        {asset.type}
                      </td>
                      <td className="py-2 pr-6 text-right font-mono text-neutral-200">
                        {asset.criticality}
                      </td>
                      <td className="py-2 pr-6 text-right font-mono text-neutral-400">
                        {dependents[asset.id] ?? 0}
                      </td>
                      <td className="py-2 pr-10 text-right font-mono">
                        {counts[asset.id] ? (
                          <span className="text-[var(--ip-orange)]">
                            {counts[asset.id]}
                          </span>
                        ) : (
                          <span className="text-neutral-700">—</span>
                        )}
                      </td>
                      <td className="py-2 pl-2">
                        <span
                          className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase ${STATUS[asset.status]}`}
                        >
                          {asset.status}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
