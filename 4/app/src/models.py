from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass(frozen=True)
class CargoProfile:
    material_name: str
    volume_tons: float
    price_usd_per_ton: float
    insurance_rate: float
    wacc_baseline: float
    pack_comp_cost_usd: float
    p_fail_base: float
    l_fail_loss_usd: float

@dataclass(frozen=True)
class TransportLeg:
    name: str
    distance_km: float
    tariff_usd_tkm: float
    lead_time_days: float
    emission_g_tkm: float

@dataclass(frozen=True)
class TransportRoute:
    route_id: str
    description: str
    legs: tuple[TransportLeg,...]

@dataclass(frozen=True)
class CBAMParameters:
    see_prod_tco2_per_ton: float
    benchmark_eu_tco2_per_ton: float
    p_eu_ets_eur: float
    p_carbon_origin_eur: float
    eur_usd_rate: float

@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    demand_tons_year: float

@dataclass(frozen=True)
class Facility:
    facility_id: str
    location: str
    fixed_cost_rub_year: float
    capacity_tons_year: float

@dataclass(frozen=True)
class TariffMatrix:
    # Ключ (facility_id, customer_id); значение руб/т.
    values: dict[tuple[str,str],float]

@dataclass(frozen=True)
class CFLPInput:
    customers: tuple[Customer,...]
    facilities: tuple[Facility,...]
    tariffs: TariffMatrix

@dataclass(frozen=True)
class TelemetrySample:
    index: int
    timestamp: datetime
    latitude: float
    longitude: float
    temp_celsius: float
    pressure_bar: float
    accel_x_g: float
    accel_y_g: float
    accel_z_g: float

@dataclass(frozen=True)
class TelemetryDataset:
    samples: tuple[TelemetrySample,...]
    source: Path
    interval_minutes: float = 5.0

@dataclass(frozen=True)
class ProjectInputData:
    cargo: CargoProfile
    cbam: CBAMParameters
    routes: dict[str,TransportRoute]
    cflp: CFLPInput
    telemetry: TelemetryDataset

@dataclass(frozen=True)
class TCOBreakdown:
    route_id: str
    freight_usd: float
    insurance_usd: float
    inventory_usd: float
    packaging_usd: float
    risk_usd: float
    tax_cbam_eur: float
    border_usd: float
    transport_emissions_tco2_per_t: float
    lead_time_days: float
    p_fail: float
    tco_log_usd: float
    tco_total_usd: float

@dataclass(frozen=True)
class CFLPSolution:
    model: str
    status: str
    objective_rub_year: float | None
    fixed_rub_year: float | None
    transport_rub_year: float | None
    y: dict[str,float]
    flows: dict[str,dict[str,float]]
    assignments: dict[str,dict[str,float]]
    loads: dict[str,float]
    demand_residuals: dict[str,float]
    capacity_slacks: dict[str,float]
    physical_overloads: dict[str,float]
    binary_residuals: dict[str,float]
    linking_slacks: dict[str,float]
    solve_seconds: float

@dataclass(frozen=True)
class Incident:
    kind: str
    start_index: int
    end_index: int
    start: str
    end_observed: str
    interval_end: str
    count: int
    duration_minutes: float
    minimum: float
    maximum: float
    axis: str = ''

@dataclass(frozen=True)
class DPPPassport:
    batch_id: str
    cargo_type: str
    transport_mode: str
    sha256_telemetry_digest: str
    cold_chain_status: str
    vibration_status: str
    final_disposition: str
    adjusted_tco_usd: float
    scope3_transport_emissions_tco2: float
