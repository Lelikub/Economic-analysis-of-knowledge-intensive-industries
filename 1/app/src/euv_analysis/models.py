"""Typed domain objects shared by the analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScenarioMode(str, Enum):
    """Validation policy for ordinary data and intentional anomalies."""

    NORMAL = "normal"
    INTENTIONAL_STRESS = "intentional_stress"


class ValidationSeverity(str, Enum):
    """Severity of a structured validation issue."""

    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A machine-readable input problem or intentional anomaly."""

    code: str
    parameter: str
    severity: ValidationSeverity
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class ParameterMetadata:
    """Source metadata retained from one parameter row."""

    source_name: str
    unit: str
    description: str


@dataclass(frozen=True, slots=True)
class ProductionData:
    """Typed input for one EUV photoresist production scenario."""

    calendar_hours: float
    planned_hours: float
    actual_hours: float
    target_output: float
    actual_output: float
    first_pass_good_units: float
    final_good_units: float
    raw_material_cost: float
    energy_kwh: float
    energy_cost_rate: float
    equipment_capex: float
    amortization_years_economic: float
    opex_overhead: float
    delay_years: float
    discount_rate: float
    price_erosion_rate: float
    market_horizon: float
    market_window_open: int
    units: dict[str, str] = field(default_factory=dict, compare=False)
    descriptions: dict[str, str] = field(default_factory=dict, compare=False)

