"use client";

import { animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";

function tone(score: number) {
  if (score >= 75) return "text-[var(--ip-green)]";
  if (score >= 55) return "text-[var(--ip-orange)]";
  return "text-[var(--ip-red)]";
}

/** Big number with a count-up. Direction of travel is the whole story. */
export function ScoreCounter({
  score,
  previous,
  label = "Resilience score",
}: {
  score: number;
  previous?: number | null;
  label?: string;
}) {
  const [display, setDisplay] = useState(score);
  const last = useRef(score);

  useEffect(() => {
    const controls = animate(last.current, score, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (value) => setDisplay(Math.round(value)),
    });
    last.current = score;
    return () => controls.stop();
  }, [score]);

  const delta = previous == null ? null : score - previous;

  return (
    <div className="flex flex-col items-end">
      <span className="font-mono text-[10px] tracking-[0.14em] text-neutral-500 uppercase">
        {label}
      </span>
      <div className="flex items-baseline gap-2">
        <span
          data-testid="resilience-score"
          className={`font-mono text-5xl leading-none font-bold tabular-nums ${tone(display)}`}
        >
          {display}
        </span>
        {delta != null && delta !== 0 && (
          <span
            className={`font-mono text-sm font-semibold ${
              delta > 0 ? "text-[var(--ip-green)]" : "text-[var(--ip-red)]"
            }`}
          >
            {delta > 0 ? "+" : ""}
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}
