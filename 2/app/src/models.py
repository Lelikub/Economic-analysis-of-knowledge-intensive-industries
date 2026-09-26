"""Типизированные входы и результаты расчётов."""
from dataclasses import dataclass, field
from typing import Any


class ThermodynamicViolationError(ValueError):
    """Нарушен второй закон термодинамики."""


class OutOfRelevantRangeWarning(UserWarning):
    """Сценарий вне релевантного диапазона постоянных затрат."""


class InputDataError(ValueError):
    """Некорректные или неполные исходные данные."""


@dataclass(frozen=True)
class AmmoniaVariableOpexItem:
    name: str
    consumption: float
    consumption_unit: str
    price: float
    price_unit: str
    reference_cost: float


@dataclass(frozen=True)
class AmmoniaFixedOpexItem:
    name: str
    annual_musd: float


@dataclass(frozen=True)
class MachineryVariableOpexItem:
    name: str
    per_unit_musd: float
    reference_share_pct: float


@dataclass(frozen=True)
class MachineryFixedOpexItem:
    name: str
    annual_musd: float
    is_step_fixed: bool
    saving_musd: float


@dataclass(frozen=True)
class EnergyStream:
    stream_id: str
    name: str
    mass_kg_s: float
    temperature_c: float
    pressure_bar: float
    enthalpy_kj_kg: float
    entropy_kj_kg_k: float


@dataclass(frozen=True)
class SpecoStage:
    number: int
    name: str
    fuel_mw: float
    product_mw: float
    destruction_mw: float
    efficiency: float
    z_usd_h: float


@dataclass(frozen=True)
class CompressorData:
    values: dict[str, Any]


@dataclass(frozen=True)
class CogenerationData:
    values: dict[str, Any]


@dataclass(frozen=True)
class EconomicConstants:
    values: dict[str, Any]


@dataclass
class ProjectInputData:
    ammonia_variable_opex: list[AmmoniaVariableOpexItem]
    ammonia_fixed_opex: list[AmmoniaFixedOpexItem]
    machinery_variable_opex: list[MachineryVariableOpexItem]
    machinery_fixed_opex: list[MachineryFixedOpexItem]
    energy_streams: list[EnergyStream]
    speco_chain: list[SpecoStage]
    compressors: CompressorData
    cogeneration: CogenerationData
    economic_constants: EconomicConstants


@dataclass
class ProjectMetrics:
    """Контейнер рассчитанных разделов; эталоны сюда не попадают."""
    opex: dict[str, Any] = field(default_factory=dict)
    materials: dict[str, Any] = field(default_factory=dict)
    energy: dict[str, Any] = field(default_factory=dict)
    exergy: dict[str, Any] = field(default_factory=dict)
    speco: dict[str, Any] = field(default_factory=dict)
    chain: dict[str, Any] = field(default_factory=dict)
    compressors: dict[str, Any] = field(default_factory=dict)
    heat_exchanger: dict[str, Any] = field(default_factory=dict)
    sensitivity: dict[str, Any] = field(default_factory=dict)
