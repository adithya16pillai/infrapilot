"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AssetDetail } from "@/lib/types";

const SEVERITY: Record<string, string> = {
  high: "text-[var(--ip-red)] border-[var(--ip-red)]/50",
  medium: "text-[var(--ip-orange)] border-[var(--ip-orange)]/50",
  low: "text-neutral-400 border-[var(--ip-grey-700)]",
};

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="font-mono text-[10px] tracking-wide text-neutral-500 uppercase">
        {label}
      </span>
      <span className="text-right font-mono text-[11.5px] text-neutral-200">{value}</span>
    </div>
  );
}

export function NodeDetailSheet({
  assetId,
  onClose,
}: {
  assetId: string | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<AssetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!assetId) return;
    setDetail(null);
    setError(null);
    api
      .asset(assetId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [assetId]);

  return (
    <AnimatePresence>
      {assetId && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="fixed top-0 right-0 z-50 flex h-full w-[400px] flex-col border-l border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]"
          >
            <header className="flex items-start justify-between border-b border-[var(--ip-grey-700)] px-4 py-3">
              <div>
                <h2 className="text-[15px] font-semibold text-neutral-100">
                  {detail?.name ?? assetId}
                </h2>
                {detail && (
                  <p className="mt-0.5 font-mono text-[10px] tracking-wide text-neutral-500">
                    {detail.id} · {detail.type}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                className="rounded p-1 text-neutral-500 hover:bg-white/5 hover:text-neutral-200"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto p-4">
              {error && (
                <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-3 py-2 font-mono text-[11px] text-[var(--ip-red)]">
                  {error}
                </p>
              )}
              {!detail && !error && (
                <div className="space-y-2">
                  {[...Array(5)].map((_, index) => (
                    <div key={index} className="h-4 animate-pulse rounded bg-white/5" />
                  ))}
                </div>
              )}

              {detail && (
                <>
                  <section>
                    <Row label="Status" value={detail.status} />
                    <Row label="Criticality" value={`${detail.criticality} / 10`} />
                    <Row label="Failure threshold" value={detail.failure_threshold} />
                    <Row label="Suppliers" value={detail.suppliers.length} />
                    <Row label="Dependents" value={detail.dependents.length} />
                  </section>

                  <section>
                    <h3 className="mb-1.5 font-mono text-[10px] tracking-[0.14em] text-neutral-400 uppercase">
                      Software inventory
                    </h3>
                    <Row label="OS" value={detail.software_inventory.os ?? "—"} />
                    <Row label="Firmware" value={detail.software_inventory.firmware ?? "—"} />
                    <ul className="mt-1.5 space-y-1">
                      {(detail.software_inventory.packages ?? []).map((pkg) => (
                        <li
                          key={pkg}
                          className="rounded bg-black/30 px-2 py-1 font-mono text-[10.5px] text-neutral-400"
                        >
                          {pkg}
                        </li>
                      ))}
                    </ul>
                  </section>

                  {detail.finding_count > 0 && (
                    <section>
                      <h3 className="mb-1.5 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-neutral-400 uppercase">
                        Supply chain
                        <span className="rounded border border-[var(--ip-orange)]/50 px-1.5 py-0.5 text-[9px] text-[var(--ip-orange)]">
                          {detail.finding_count} · {detail.top_severity}
                        </span>
                      </h3>
                      <div className="space-y-2">
                        {detail.findings.map((finding) => (
                          <div
                            key={finding.id}
                            className="rounded border border-[var(--ip-grey-700)] bg-black/20 p-2.5"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-[11px] text-neutral-200">
                                {finding.package}
                              </span>
                              <span
                                className={`rounded border px-1.5 py-0.5 font-mono text-[9px] ${SEVERITY[finding.severity]}`}
                              >
                                {finding.severity}
                              </span>
                            </div>
                            <p className="mt-1.5 text-[11px] leading-relaxed text-neutral-500">
                              {finding.behaviour}
                            </p>
                            <p className="mt-1.5 font-mono text-[10px] text-[var(--ip-orange)]">
                              operational impact {finding.operational_impact}
                            </p>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  <section>
                    <h3 className="mb-1.5 font-mono text-[10px] tracking-[0.14em] text-neutral-400 uppercase">
                      Connected assets
                    </h3>
                    <div className="space-y-1">
                      {detail.suppliers.map((dep) => (
                        <div
                          key={`in-${dep.source}-${dep.dependency_type}`}
                          className="flex items-center justify-between font-mono text-[10.5px]"
                        >
                          <span className="text-neutral-400">← {dep.source}</span>
                          <span className="text-neutral-600">
                            {dep.dependency_type} · {dep.weight}
                          </span>
                        </div>
                      ))}
                      {detail.dependents.map((dep) => (
                        <div
                          key={`out-${dep.target}-${dep.dependency_type}`}
                          className="flex items-center justify-between font-mono text-[10.5px]"
                        >
                          <span className="text-neutral-300">→ {dep.target}</span>
                          <span className="text-neutral-600">
                            {dep.dependency_type} · {dep.weight}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
