"""Pydantic contracts. Single source of truth for every payload the frontend sees."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AssetStatus = Literal["healthy", "degraded", "failed", "hardened"]
DependencyType = Literal["power", "comms", "operational"]


class AssetOut(BaseModel):
    id: str
    name: str
    type: str
    criticality: int
    failure_threshold: float
    status: AssetStatus
    position_x: float
    position_y: float
    software_inventory: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyOut(BaseModel):
    source: str
    target: str
    dependency_type: DependencyType
    weight: float


class ScenarioPreset(BaseModel):
    id: str
    label: str
    query: str


class GraphResponse(BaseModel):
    assets: list[AssetOut]
    dependencies: list[DependencyOut]
    presets: list[ScenarioPreset]
    resilience_score: int


class SimulateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    scenario_preset: str | None = None


class SimulateAccepted(BaseModel):
    simulation_id: str
    status: str


class SimulationEvent(BaseModel):
    simulation_id: str
    seq: int
    type: str
    label: str
    tool: str | None = None
    status: str
    detail: str | None = None
    ts: str


class ImportanceEntry(BaseModel):
    asset_id: str
    betweenness: float


class KillChainHop(BaseModel):
    """One attacker hop along the critical path, with the mechanism named."""

    step: int
    source: str
    target: str
    dependency_type: str
    weight: float
    resulting_status: str
    via: str


class CascadeResult(BaseModel):
    """The F3 output contract."""

    simulation_id: str | None = None
    seed_assets: list[str]
    failed: list[str]
    degraded: list[str]
    newly_impacted: list[str]
    resilience_score_before: int
    resilience_score_after: int
    blast_radius: int
    critical_path: list[str]
    kill_chain: list[KillChainHop] = Field(default_factory=list)
    single_points_of_failure: list[str] = Field(default_factory=list)
    importance_ranking: list[ImportanceEntry] = Field(default_factory=list)
    estimated_population_impact: int
    affected_services: list[str]
    statuses: dict[str, AssetStatus]
    compute_ms: float


class Recommendation(BaseModel):
    id: str
    simulation_id: str
    title: str
    expected_resilience_gain: int
    cost_estimate: str
    cost_gbp: int = 0
    #: Resilience points bought per GBP 10k — the ranking key.
    gain_per_10k: float = 0.0
    difficulty: str
    confidence: float
    rationale: str
    status: str
    graph_mutation: dict[str, Any]


class SimulationDetail(BaseModel):
    id: str
    query: str
    scenario_preset: str | None
    status: str
    summary: str | None
    error: str | None
    created_at: str
    result: CascadeResult | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)


class SupplyChainFinding(BaseModel):
    id: str
    asset_id: str
    asset_name: str
    package: str
    severity: str
    behaviour: str
    operational_impact: float
    downstream_criticality: float
    chain: list[str]


class AssetDetail(AssetOut):
    suppliers: list[DependencyOut]
    dependents: list[DependencyOut]
    findings: list[SupplyChainFinding]
    finding_count: int
    top_severity: str | None


class ApplyResult(BaseModel):
    recommendation: Recommendation
    result: CascadeResult
    resilience_score: int


class HealthResponse(BaseModel):
    modal: str
    database: str
    overmind: str
    osprey: str
    planner: str
