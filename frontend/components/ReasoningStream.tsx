"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { SimulationEvent } from "@/lib/types";

/** ○ pending · ● running · ✓ done · ✗ failed (F7). */
function Marker({ status }: { status: SimulationEvent["status"] }) {
  if (status === "running")
    return <span className="ip-blink text-[var(--ip-orange)]">●</span>;
  if (status === "failed") return <span className="text-[var(--ip-red)]">✗</span>;
  if (status === "done") return <span className="text-[var(--ip-green)]">✓</span>;
  return <span className="text-neutral-600">○</span>;
}

const PLANNED_STEPS = [
  "Planning investigation",
  "Identifying affected assets",
  "Calculating cascading impact",
  "Mapping structural dependencies",
  "Generating mitigation plan",
];

export function ReasoningStream({
  events,
  running,
  error,
}: {
  events: SimulationEvent[];
  running: boolean;
  error: string | null;
}) {
  const seenLabels = new Set(events.map((event) => event.label));
  const upcoming = running
    ? PLANNED_STEPS.filter((step) => !seenLabels.has(step))
    : [];

  return (
    <section className="flex h-full flex-col rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)]">
      <header className="flex items-center justify-between border-b border-[var(--ip-grey-700)] px-4 py-3">
        <h2 className="font-mono text-[11px] font-semibold tracking-[0.14em] text-neutral-300 uppercase">
          Agent reasoning
        </h2>
        {running && (
          <span className="ip-blink font-mono text-[10px] text-[var(--ip-orange)]">
            investigating
          </span>
        )}
      </header>

      {/* The stream updates while focus stays elsewhere; without a live
          region a screen-reader user gets no signal that the agent is working. */}
      <div
        className="flex-1 overflow-y-auto p-3"
        aria-live="polite"
        aria-busy={running}
        aria-label="Agent investigation steps"
      >
        {events.length === 0 && !running && !error && (
          <p className="px-1 py-6 text-center text-[13px] leading-relaxed text-neutral-600">
            Pick a scenario or ask a question.
            <br />
            The agent&apos;s investigation appears here, step by step.
          </p>
        )}

        {error && (
          <div className="rounded border border-[var(--ip-red)]/50 bg-[var(--ip-red)]/10 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-[var(--ip-red)]">
            ✗ {error}
          </div>
        )}

        <ul className="space-y-0.5">
          <AnimatePresence initial={false}>
            {events.map((event) => (
              <motion.li
                key={event.seq}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.22 }}
                className="rounded px-2 py-1.5 font-mono text-[11.5px] leading-snug hover:bg-white/[0.03]"
              >
                <div className="flex items-baseline gap-2">
                  <Marker status={event.status} />
                  <span
                    className={
                      event.status === "failed"
                        ? "text-[var(--ip-red)]"
                        : "text-neutral-200"
                    }
                  >
                    {event.label}
                  </span>
                </div>
                {event.detail && (
                  <p className="mt-0.5 pl-5 text-[10.5px] leading-relaxed text-neutral-500">
                    {event.detail}
                  </p>
                )}
                {event.tool && (
                  <p className="mt-0.5 pl-5 font-mono text-[9.5px] tracking-wide text-[var(--ip-blue)]/70">
                    {event.tool}()
                  </p>
                )}
              </motion.li>
            ))}
          </AnimatePresence>

          {upcoming.map((label) => (
            <li
              key={label}
              className="px-2 py-1.5 font-mono text-[11.5px] leading-snug text-neutral-700"
            >
              <span className="mr-2">○</span>
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
