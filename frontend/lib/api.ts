import type {
  ApplyResult,
  AssetDetail,
  DashboardSummary,
  GraphResponse,
  Health,
  Recommendation,
  SimulationDetail,
  SimulationEvent,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      ...init,
    });
  } catch {
    // F-edge: a clear error state, never a spinner forever.
    throw new ApiError(
      "Cannot reach the InfraPilot API. Is the backend running on :8000?",
      0,
    );
  }
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(body || response.statusText, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  graph: () => request<GraphResponse>("/api/graph"),
  health: () => request<Health>("/api/health"),
  asset: (id: string) => request<AssetDetail>(`/api/assets/${id}`),
  dashboard: () => request<DashboardSummary>("/api/dashboard"),
  reset: () => request<{ resilience_score: number }>("/api/reset", { method: "POST" }),

  simulate: (query: string, preset?: string | null) =>
    request<{ simulation_id: string; status: string }>("/api/simulate", {
      method: "POST",
      body: JSON.stringify({ query, scenario_preset: preset ?? null }),
    }),

  simulation: (id: string) => request<SimulationDetail>(`/api/simulations/${id}`),
  events: (id: string) => request<SimulationEvent[]>(`/api/simulations/${id}/events`),

  recommendations: (simulationId: string) =>
    request<Recommendation[]>(
      `/api/recommendations?simulation_id=${encodeURIComponent(simulationId)}`,
    ),
  apply: (id: string) =>
    request<ApplyResult>(`/api/recommendations/${id}/apply`, { method: "POST" }),
  reject: (id: string) =>
    request<Recommendation>(`/api/recommendations/${id}/reject`, { method: "POST" }),

  streamUrl: (id: string) => `${API_BASE}/api/simulations/${id}/stream`,
};

export { ApiError };
