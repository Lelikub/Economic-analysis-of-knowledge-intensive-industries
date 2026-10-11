"""Типизированные данные, сохраняющие исходные величины и единицы."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np


@dataclass(frozen=True)
class NodeParameters:
    node_id: str
    name_ru: str
    reliability: float
    unreliability: float
    availability: float
    failure_rate_year: float
    mtbf_hours: float
    mttr_hours: float
    lead_time_days: float
    criticality: str
    supplier_cluster: str
    source: str


@dataclass(frozen=True)
class FinancialParameters:
    c_day: float
    c_scrap: float
    annual_budget: float
    currency: str = "USD millions"


@dataclass(frozen=True)
class DowntimeDistributionParameters:
    lognorm_mu: float
    lognorm_sigma: float
    pareto_alpha: float
    pareto_xm_days: float


@dataclass(frozen=True)
class RedundancyCostParameters:
    capex_qual: float
    r_amor: float
    opex_audit: float
    delta_c_proc: float
    stated_tco: float


@dataclass(frozen=True)
class CorrelationMatrix:
    names: tuple[str, ...]
    values: np.ndarray
    kind: str = "target_binary_pearson"


@dataclass(frozen=True)
class HistoricalIncident:
    incident_id: str
    date: date
    failed_node: str
    root_cause: str
    downtime_days: float
    direct_loss: float


@dataclass(frozen=True)
class SupplyChainData:
    nodes: dict[str, NodeParameters]
    financial: FinancialParameters
    downtime: DowntimeDistributionParameters
    redundancy: RedundancyCostParameters
    base_matrix: CorrelationMatrix
    stress_matrix: CorrelationMatrix
    frechet_rows: tuple[dict[str, str], ...]
    incidents: tuple[HistoricalIncident, ...]
    raw_json: dict[str, Any]
    source_records: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    description: str
    dual: bool
    stress: bool
    correlation: str
    duration: str = "lognormal"


@dataclass(frozen=True)
class ReliabilityMetrics:
    r_sys: float | None
    p_fail: float | None
    method: str
    status: str


@dataclass(frozen=True)
class FinancialMetrics:
    el_med: float | None
    el_lognorm: float | None
    tco: float
    avoided_loss: float | None
    roi: float | None
    units: str = "USD millions/year"


@dataclass(frozen=True)
class RiskMetrics:
    var95: float | None
    cvar95: float | None
    var99: float | None
    cvar99: float | None
    n: int
    units: str = "USD millions per annual scenario"


@dataclass(frozen=True)
class ScenarioResult:
    definition: ScenarioDefinition
    reliability: ReliabilityMetrics
    financial: FinancialMetrics
    risk: RiskMetrics
    simulation: dict[str, Any] = field(default_factory=dict)
