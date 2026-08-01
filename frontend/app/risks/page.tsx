"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell, Card, CityViewButton, PageHeader } from "@/components/AppShell";
import { OspreyComparison, OspreyExplainer } from "@/components/OspreyComparison";
import { api } from "@/lib/api";
import type { SupplyChainResponse } from "@/lib/types";

const SEVERITY: Record<string, string> = {
  high: "text-[var(--ip-red)] border-[var(--ip-red)]/50",
  medium: "text-[var(--ip-orange)] border-[var(--ip-orange)]/50",
  low: "text-neutral-400 border-[var(--ip-grey-700)]",
};

export default function RisksPage() {
  const [data, setData] = useState<SupplyChainResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .supplyChain()
      .then(setData)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load findings"),
      );
  }, []);

  return (
    <AppShell>
      <PageHeader
        title="Supply chain risks"
        subtitle="Malicious package findings, ranked by what they would actually take down"
        actions={<CityViewButton />}
      />

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {error && (
          <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
            {error}
          </p>
        )}

        {data && (
          <>
            <div className="grid grid-cols-3 gap-4">
              <Card title="How OSSPrey reads this" className="col-span-1">
                <OspreyExplainer mode={data.mode} />
              </Card>

              <Card
                title="Same severity, different consequence"
                hint="the ranking argument"
                className="col-span-2"
              >
                {data.comparison ? (
                  <OspreyComparison comparison={data.comparison} />
                ) : (
                  <p className="font-mono text-[11px] text-neutral-600">
                    Need at least two findings of equal severity to compare.
                  </p>
                )}
              </Card>
            </div>

            <Card title="All findings" hint={`${data.findings.length} total`}>
              <div className="space-y-2">
                {data.findings.map((finding, index) => (
                  <Link
                    key={finding.id}
                    href={`/city?asset=${finding.asset_id}`}
                    className="block rounded-lg border border-[var(--ip-grey-700)] bg-black/20 p-3.5 transition hover:border-[var(--ip-blue)]"
                    data-testid="risk-row"
                  >
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 font-mono text-[13px] font-bold text-neutral-600">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-2">
                          <span className="font-mono text-[12.5px] text-neutral-100">
                            {finding.package}
                          </span>
                          <span
                            className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase ${SEVERITY[finding.severity]}`}
                          >
                            {finding.severity}
                          </span>
                          <span className="text-[12px] text-neutral-400">
                            on {finding.asset_name}
                          </span>
                        </div>
                        <p className="mt-1.5 text-[12px] leading-relaxed text-neutral-500">
                          {finding.behaviour}
                        </p>
                        <p className="mt-1.5 font-mono text-[10.5px] leading-relaxed text-neutral-500">
                          {finding.rank_reason}
                        </p>
                        {finding.chain_names.length > 1 && (
                          <p className="mt-1 font-mono text-[10px] text-[var(--ip-orange)]">
                            {finding.chain_names.join(" → ")}
                          </p>
                        )}
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="font-mono text-2xl leading-none font-bold text-[var(--ip-orange)]">
                          {finding.operational_impact}
                        </div>
                        <div className="mt-0.5 font-mono text-[9px] tracking-wider text-neutral-600 uppercase">
                          impact
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}
