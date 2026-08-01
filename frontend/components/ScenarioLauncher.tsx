"use client";

import { CornerDownLeft, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ScenarioPreset } from "@/lib/types";

export function ScenarioLauncher({
  presets,
  onLaunch,
  disabled,
}: {
  presets: ScenarioPreset[];
  onLaunch: (query: string, presetId?: string | null) => void;
  disabled: boolean;
}) {
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);

  // Cmd+K / Ctrl+K focuses the query box.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.current?.focus();
        input.current?.select();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-1.5">
        {presets.map((preset) => (
          <button
            key={preset.id}
            data-testid={`preset-${preset.id}`}
            disabled={disabled}
            onClick={() => onLaunch(preset.query, preset.id)}
            className="rounded-full border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] px-3 py-1.5 text-[12px] text-neutral-300 transition hover:border-[var(--ip-blue)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {preset.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim() && !disabled) {
            onLaunch(query.trim(), null);
            setQuery("");
          }
        }}
        className="relative"
      >
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-neutral-600" />
        <input
          ref={input}
          data-testid="query-input"
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask anything — e.g. what happens if the Telecom Hub goes down?"
          className="w-full rounded-lg border border-[var(--ip-grey-700)] bg-[var(--ip-grey-900)] py-2.5 pr-24 pl-9 text-[13px] text-neutral-100 placeholder:text-neutral-600 focus:border-[var(--ip-blue)] focus:outline-none disabled:opacity-50"
        />
        <div className="absolute top-1/2 right-3 flex -translate-y-1/2 items-center gap-1.5">
          <kbd className="rounded border border-[var(--ip-grey-700)] px-1.5 py-0.5 font-mono text-[9px] text-neutral-600">
            ⌘K
          </kbd>
          <button
            type="submit"
            disabled={disabled || !query.trim()}
            className="rounded p-1 text-neutral-500 transition hover:text-[var(--ip-blue)] disabled:opacity-30"
          >
            <CornerDownLeft className="h-3.5 w-3.5" />
          </button>
        </div>
      </form>
    </div>
  );
}
