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


class MetricStatus(str, Enum):
    """Computability status for an exported metric."""

    OK = "OK"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"


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


@dataclass(frozen=True, slots=True)
class MetricValue:
    """One calculated value with traceable formula and dimensions."""

    name: str
    value: float | None
    unit: str
    formula: str
    status: MetricStatus = MetricStatus.OK
    note: str = ""


@dataclass(frozen=True, slots=True)
class MetricsResult:
    """Complete operational and cost result for one scenario."""

    fpy: MetricValue
    final_yield: MetricValue
    availability: MetricValue
    performance: MetricValue
    quality: MetricValue
    oee: MetricValue
    utilization: MetricValue
    teep: MetricValue
    energy_cost: MetricValue
    monthly_depreciation: MetricValue
    total_manufacturing_cost: MetricValue
    mass_intensity: MetricValue
    energy_intensity: MetricValue
    economic_intensity: MetricValue
    raw_material_cost_proxy: MetricValue
    cpu: MetricValue

    def numeric_values(self) -> dict[str, float | None]:
        """Return stable export names without exposing calculation internals."""
        return {
            "FPY": self.fpy.value,
            "Final Yield": self.final_yield.value,
            "Availability": self.availability.value,
            "Performance": self.performance.value,
            "Quality": self.quality.value,
            "OEE": self.oee.value,
            "Utilization": self.utilization.value,
            "TEEP": self.teep.value,
            "Energy Cost": self.energy_cost.value,
            "Monthly Depreciation": self.monthly_depreciation.value,
            "Total Manufacturing Cost": self.total_manufacturing_cost.value,
            "Mass Intensity": self.mass_intensity.value,
            "Energy Intensity": self.energy_intensity.value,
            "Economic Intensity": self.economic_intensity.value,
            "Raw Material Cost Proxy": self.raw_material_cost_proxy.value,
            "CPU": self.cpu.value,
        }
