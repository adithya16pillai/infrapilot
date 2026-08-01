"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AssetStatus, SimulationDetail, SimulationEvent } from "./types";

/** Minimum time a reasoning row is on screen before the next appears (F7). */
const ROW_INTERVAL_MS = 400;

export interface SimulationState {
  simulationId: string | null;
  events: SimulationEvent[];
  detail: SimulationDetail | null;
  running: boolean;
  error: string | null;
  /** Status overrides applied to the graph as the cascade lands. */
  statuses: Record<string, AssetStatus> | null;
}

export function useSimulation() {
  const [state, setState] = useState<SimulationState>({
    simulationId: null,
    events: [],
    detail: null,
    running: false,
    error: null,
    statuses: null,
  });

  // seq -> event. Later deliveries of the same seq overwrite (running -> done),
  // which is what lets a row flip in place instead of duplicating.
  const buffer = useRef(new Map<number, SimulationEvent>());
  const revealed = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const source = useRef<EventSource | null>(null);

  const stopTimers = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    source.current?.close();
    source.current = null;
  }, []);

  useEffect(() => stopTimers, [stopTimers]);

  const publish = useCallback(() => {
    const ordered = [...buffer.current.values()].sort((a, b) => a.seq - b.seq);
    setState((prev) => ({ ...prev, events: ordered.slice(0, revealed.current) }));
  }, []);

  const start = useCallback(
    async (query: string, preset?: string | null) => {
      stopTimers();
      buffer.current.clear();
      revealed.current = 0;
      setState({
        simulationId: null,
        events: [],
        detail: null,
        running: true,
        error: null,
        statuses: null,
      });

      let simulationId: string;
      try {
        ({ simulation_id: simulationId } = await api.simulate(query, preset));
      } catch (err) {
        setState((prev) => ({
          ...prev,
          running: false,
          error: err instanceof Error ? err.message : "Failed to start simulation",
        }));
        return;
      }

      setState((prev) => ({ ...prev, simulationId }));

      // Throttle the reveal so the audience can actually read the stream, even
      // though the backend finishes in well under a second.
      timer.current = setInterval(() => {
        if (revealed.current < buffer.current.size) {
          revealed.current += 1;
          publish();
        }
      }, ROW_INTERVAL_MS);

      const finish = async () => {
        try {
          const detail = await api.simulation(simulationId);
          // Hold the graph animation until every row has been shown.
          const waitForRows = setInterval(() => {
            if (revealed.current >= buffer.current.size) {
              clearInterval(waitForRows);
              setState((prev) => ({
                ...prev,
                detail,
                running: false,
                statuses: detail.result?.statuses ?? null,
              }));
            }
          }, 120);
        } catch (err) {
          setState((prev) => ({
            ...prev,
            running: false,
            error: err instanceof Error ? err.message : "Failed to load result",
          }));
        }
      };

      const es = new EventSource(api.streamUrl(simulationId));
      source.current = es;

      es.onmessage = (message) => {
        const event = JSON.parse(message.data) as SimulationEvent;
        buffer.current.set(event.seq, event);
        // Re-publish so an already-visible row can flip running -> done.
        publish();
        if (event.type === "done") {
          es.close();
          void finish();
        }
      };

      es.onerror = async () => {
        // SSE dropped — fall back to polling so the demo still completes.
        es.close();
        for (let attempt = 0; attempt < 40; attempt += 1) {
          try {
            const events = await api.events(simulationId);
            events.forEach((event) => buffer.current.set(event.seq, event));
            publish();
            if (events.some((event) => event.type === "done")) {
              await finish();
              return;
            }
          } catch {
            /* keep polling */
          }
          await new Promise((resolve) => setTimeout(resolve, 400));
        }
        setState((prev) => ({ ...prev, running: false, error: "Lost connection to the agent." }));
      };
    },
    [publish, stopTimers],
  );

  const patch = useCallback((updater: (prev: SimulationState) => SimulationState) => {
    setState(updater);
  }, []);

  const reset = useCallback(() => {
    stopTimers();
    buffer.current.clear();
    revealed.current = 0;
    setState({
      simulationId: null,
      events: [],
      detail: null,
      running: false,
      error: null,
      statuses: null,
    });
  }, [stopTimers]);

  return { ...state, start, reset, patch };
}
