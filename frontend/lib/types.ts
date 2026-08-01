// Mirrors backend/app/models.py. Kept hand-written and small so the contract
// stays obvious at a glance during the demo.

export type AssetStatus = "healthy" | "degraded" | "failed" | "hardened";
export type DependencyType = "power" | "comms" | "operational";

export interface Asset {
  id: string;
  name: string;
  type: string;
  criticality: number;
  failure_threshold: number;
  status: AssetStatus;
  position_x: number;
  position_y: number;
  software_inventory: {
    os?: string;
    firmware?: string;
    packages?: string[];
  };
  metadata: Record<string, unknown>;
}

export interface Dependency {
  source: string;
  target: string;
  dependency_type: DependencyType;
  weight: number;
}

export interface ScenarioPreset {
  id: string;
  label: string;
  query: string;
}

export interface GraphResponse {
  assets: Asset[];
  dependencies: Dependency[];
  presets: ScenarioPreset[];
  resilience_score: number;
}

export interface SimulationEvent {
  simulation_id: string;
  seq: number;
  type: string;
  label: string;
  tool: string | null;
  status: "running" | "done" | "failed";
  detail: string | null;
  ts: string;
}

export interface KillChainHop {
  step: number;
  source: string;
  target: string;
  dependency_type: DependencyType | "unknown";
  weight: number;
  resulting_status: AssetStatus;
  via: string;
}

export interface CascadeResult {
  simulation_id?: string;
  seed_assets: string[];
  failed: string[];
  degraded: string[];
  newly_impacted: string[];
  resilience_score_before: number;
  resilience_score_after: number;
  blast_radius: number;
  critical_path: string[];
  kill_chain: KillChainHop[];
  single_points_of_failure: string[];
  importance_ranking: { asset_id: string; betweenness: number }[];
  estimated_population_impact: number;
  affected_services: string[];
  statuses: Record<string, AssetStatus>;
  compute_ms: number;
}

export interface Recommendation {
  id: string;
  simulation_id: string;
  title: string;
  expected_resilience_gain: number;
  cost_estimate: string;
  cost_gbp: number;
  /** Resilience points bought per GBP 10k — the ranking key. */
  gain_per_10k: number;
  difficulty: string;
  confidence: number;
  rationale: string;
  status: "pending" | "approved" | "rejected" | "superseded";
  graph_mutation: Record<string, unknown>;
}

export interface SimulationDetail {
  id: string;
  query: string;
  scenario_preset: string | null;
  status: "planning" | "complete" | "unresolved" | "failed";
  summary: string | null;
  error: string | null;
  created_at: string;
  result: CascadeResult | null;
  recommendations: Recommendation[];
}

export interface SupplyChainFinding {
  id: string;
  asset_id: string;
  asset_name: string;
  package: string;
  severity: "high" | "medium" | "low";
  behaviour: string;
  operational_impact: number;
  downstream_criticality: number;
  severity_weight: number;
  rank_reason: string;
  chain: string[];
  chain_names: string[];
}

export interface ImpactComparison {
  severity: string;
  higher: SupplyChainFinding;
  lower: SupplyChainFinding;
  ratio: number;
  explanation: string;
}

export interface SupplyChainResponse {
  mode: "mock" | "live";
  findings: SupplyChainFinding[];
  comparison: ImpactComparison | null;
}

export interface SimulationSummary {
  id: string;
  query: string;
  scenario_preset: string | null;
  status: string;
  summary: string | null;
  created_at: string;
  score_before: number | null;
  score_after: number | null;
  blast_radius: number | null;
  seed_assets: string[];
}

export interface AssetDetail extends Asset {
  suppliers: Dependency[];
  dependents: Dependency[];
  findings: SupplyChainFinding[];
  finding_count: number;
  top_severity: string | null;
}

export interface ApplyResult {
  recommendation: Recommendation;
  result: CascadeResult;
  resilience_score: number;
}

export interface DashboardSummary {
  resilience_score: number;
  status_breakdown: Record<AssetStatus, number>;
  critical_assets: number;
  highest_risk_asset: { id: string; name: string; criticality: number };
  estimated_population_impact: number;
  score_trend: number[];
  recent_simulations: {
    id: string;
    query: string;
    status: string;
    created_at: string;
    score_before: number | null;
    score_after: number | null;
  }[];
  pending_recommendations: Recommendation[];
  top_supply_chain_risks: SupplyChainFinding[];
}

export interface Health {
  modal: string;
  database: string;
  overmind: string;
  osprey: string;
  planner: string;
}
