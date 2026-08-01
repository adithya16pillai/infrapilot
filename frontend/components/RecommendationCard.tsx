"use client";

import { motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import { useState } from "react";
import type { Recommendation } from "@/lib/types";

const DIFFICULTY: Record<string, string> = {
  low: "text-[var(--ip-green)] border-[var(--ip-green)]/40",
  medium: "text-[var(--ip-orange)] border-[var(--ip-orange)]/40",
  high: "text-[var(--ip-red)] border-[var(--ip-red)]/40",
};

export function RecommendationCard({
  recommendation,
  onApprove,
  onReject,
  busy,
}: {
  recommendation: Recommendation;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  busy: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const settled = recommendation.status !== "pending";

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: settled ? 0.5 : 1, y: 0 }}
      data-testid="recommendation-card"
      data-status={recommendation.status}
      className={`rounded-lg border bg-[var(--ip-grey-900)] p-3.5 ${
        recommendation.status === "approved"
          ? "border-[var(--ip-green)]/60"
          : recommendation.status === "rejected"
            ? "border-[var(--ip-grey-700)]"
            : "border-[var(--ip-grey-700)] hover:border-[var(--ip-blue)]/50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-[13.5px] leading-snug font-medium text-neutral-100">
          {recommendation.title}
        </h3>
        <div className="shrink-0 text-right">
          <div className="font-mono text-lg leading-none font-bold text-[var(--ip-green)]">
            +{recommendation.expected_resilience_gain}
          </div>
          <div className="font-mono text-[9px] tracking-wide text-neutral-600 uppercase">
            points
          </div>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 font-mono text-[10px]">
        <span className="rounded border border-[var(--ip-grey-700)] px-1.5 py-0.5 text-neutral-400">
          {recommendation.cost_estimate}
        </span>
        <span
          className={`rounded border px-1.5 py-0.5 ${
            DIFFICULTY[recommendation.difficulty] ?? "border-[var(--ip-grey-700)] text-neutral-400"
          }`}
        >
          {recommendation.difficulty}
        </span>
        <span
          className="rounded border border-[var(--ip-grey-700)] px-1.5 py-0.5 text-neutral-400"
          title="Share of threshold-jittered simulations where this gain holds"
        >
          confidence {(recommendation.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <p
        className={`mt-2 text-[11.5px] leading-relaxed text-neutral-500 ${
          expanded ? "" : "line-clamp-2"
        }`}
        onClick={() => setExpanded((value) => !value)}
      >
        {recommendation.rationale}
      </p>

      {settled ? (
        <div className="mt-3 font-mono text-[10px] tracking-wide text-neutral-500 uppercase">
          {recommendation.status === "approved" ? (
            <span className="text-[var(--ip-green)]">✓ approved — model updated</span>
          ) : recommendation.status === "superseded" ? (
            <span>superseded by an approved change</span>
          ) : (
            <span>✗ rejected</span>
          )}
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <button
            data-testid="approve-button"
            disabled={busy}
            onClick={() => onApprove(recommendation.id)}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded bg-[var(--ip-blue)] px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-[var(--ip-blue-dark)] disabled:opacity-50"
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Approve
          </button>
          <button
            disabled={busy}
            onClick={() => onReject(recommendation.id)}
            className="inline-flex items-center justify-center gap-1.5 rounded border border-[var(--ip-grey-700)] px-3 py-1.5 text-[12px] text-neutral-400 transition hover:border-neutral-500 hover:text-neutral-200 disabled:opacity-50"
          >
            <X className="h-3.5 w-3.5" />
            Reject
          </button>
        </div>
      )}
    </motion.article>
  );
}
