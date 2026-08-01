"use client";

import { ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell, Card, CityViewButton, PageHeader } from "@/components/AppShell";
import { RecommendationCard } from "@/components/RecommendationCard";
import { api } from "@/lib/api";
import type { Recommendation } from "@/lib/types";

export default function ApprovalsPage() {
  const [pending, setPending] = useState<Recommendation[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .pendingApprovals()
      .then(setPending)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load approvals"),
      );
  }, []);

  useEffect(load, [load]);

  const approve = async (id: string) => {
    setBusy(id);
    try {
      const outcome = await api.apply(id);
      setNote(
        `Applied. Resilience under that scenario is now ${outcome.result.resilience_score_after}. ` +
          `Remaining mitigations were re-scored against the hardened city.`,
      );
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply");
    } finally {
      setBusy(null);
    }
  };

  const reject = async (id: string) => {
    setBusy(id);
    try {
      await api.reject(id);
      load();
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Approvals"
        subtitle="Every mitigation awaiting a human decision, best value for money first"
        actions={<CityViewButton />}
      />

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {error && (
          <p className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-4 py-3 font-mono text-[12px] text-[var(--ip-red)]">
            {error}
          </p>
        )}
        {note && (
          <p className="rounded border border-[var(--ip-green)]/40 bg-[var(--ip-green)]/5 px-4 py-3 text-[12.5px] text-neutral-300">
            {note}
          </p>
        )}

        <div className="flex items-start gap-2 rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] px-4 py-3">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ip-green)]" />
          <p className="text-[12.5px] leading-relaxed text-neutral-400">
            Approving a mitigation changes the{" "}
            <span className="text-neutral-200">resilience model only</span> — it
            never touches a live system. Each gain shown is measured by re-running
            the cascade with that change applied, and approving one re-scores the
            rest, because mitigations are not independent.
          </p>
        </div>

        {pending && pending.length === 0 && (
          <Card title="Nothing to review">
            <p className="text-[12.5px] text-neutral-500">
              No mitigations are awaiting approval. Run a simulation from the city
              view to generate some.
            </p>
          </Card>
        )}

        {pending && pending.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {pending.map((rec) => (
              <RecommendationCard
                key={rec.id}
                recommendation={rec}
                onApprove={approve}
                onReject={reject}
                busy={busy === rec.id}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
