"use client";

import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { KillChainHop } from "@/lib/types";

const TYPE_COPY: Record<string, { label: string; colour: string }> = {
  power: { label: "power feed", colour: "text-[var(--ip-blue)]" },
  comms: { label: "comms link", colour: "text-[#5a8dee]" },
  operational: { label: "control link", colour: "text-neutral-400" },
  unknown: { label: "dependency", colour: "text-neutral-500" },
};

/**
 * The critical path rendered the way a security audience reads an attack:
 * numbered hops, each naming the mechanism that carried the failure and the
 * weight that breached the target's threshold.
 */
export function KillChain({
  hops,
  names,
  compact = false,
}: {
  hops: KillChainHop[];
  names: Record<string, string>;
  compact?: boolean;
}) {
  if (hops.length === 0) {
    return (
      <p className="font-mono text-[11px] text-neutral-600">
        No propagation — the seed asset failed in isolation.
      </p>
    );
  }

  const origin = hops[0].source;

  return (
    <ol className="space-y-1.5">
      <li className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--ip-red)] font-mono text-[10px] font-bold text-white">
          0
        </span>
        <span className="text-[12.5px] font-medium text-neutral-100">
          {names[origin] ?? origin}
        </span>
        <span className="font-mono text-[10px] tracking-wide text-[var(--ip-red)] uppercase">
          compromised
        </span>
      </li>

      {hops.map((hop) => {
        const copy = TYPE_COPY[hop.dependency_type] ?? TYPE_COPY.unknown;
        return (
          <motion.li
            key={hop.step}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: hop.step * 0.08 }}
            className="flex items-start gap-2"
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[var(--ip-grey-700)] font-mono text-[10px] text-neutral-400">
              {hop.step}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <ChevronRight className="h-3 w-3 shrink-0 text-neutral-700" />
                <span className="text-[12.5px] font-medium text-neutral-100">
                  {names[hop.target] ?? hop.target}
                </span>
                <span
                  className={`font-mono text-[10px] tracking-wide uppercase ${
                    hop.resulting_status === "failed"
                      ? "text-[var(--ip-red)]"
                      : "text-[var(--ip-orange)]"
                  }`}
                >
                  {hop.resulting_status}
                </span>
              </div>
              {!compact && (
                <p className="mt-0.5 pl-4.5 font-mono text-[10.5px] leading-relaxed text-neutral-500">
                  via <span className={copy.colour}>{copy.label}</span> from{" "}
                  {names[hop.source] ?? hop.source} · weight{" "}
                  <span className="text-neutral-300">{hop.weight.toFixed(2)}</span>
                </p>
              )}
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
