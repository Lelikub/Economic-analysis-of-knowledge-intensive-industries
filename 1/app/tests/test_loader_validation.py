from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from euv_analysis.loader import CsvProductionLoader, DataLoadError
from euv_analysis.models import ProductionData, ScenarioMode, ValidationSeverity
from euv_analysis.validation import DataValidator


def test_loader_returns_typed_production_data(data_dir):
    """Catches a loader that leaks a DataFrame or loses source units."""
    data = CsvProductionLoader().load(data_dir / "euv_photoresist_pilot_2026.csv")

    assert isinstance(data, ProductionData)
    assert data.actual_output == pytest.approx(95.0)
    assert data.units["Actual_Output"] == "L"
    assert data.descriptions["Actual_Output"].startswith("Фактически")


def test_loader_rejects_missing_parameter(tmp_path, data_dir):
    """Catches silent defaults for a required production parameter."""
    frame = pd.read_csv(data_dir / "euv_photoresist_pilot_2026.csv")
    frame = frame[frame["Parameter_Name"] != "Actual_Output"]
    path = tmp_path / "missing.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(DataLoadError, match="Actual_Output"):
        CsvProductionLoader().load(path)


def test_loader_rejects_nan_value(tmp_path, data_dir):
    """Catches non-finite numeric values before domain calculations."""
    frame = pd.read_csv(data_dir / "euv_photoresist_pilot_2026.csv")
    frame.loc[frame["Parameter_Name"] == "Actual_Output", "Value"] = float("nan")
    path = tmp_path / "nan.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(DataLoadError, match="finite numeric"):
        CsvProductionLoader().load(path)


def test_loader_rejects_fractional_market_window_without_truncation(tmp_path, data_dir):
    """Catches an implicit float-to-int conversion that turns 0.5 into 0."""
    frame = pd.read_csv(data_dir / "euv_photoresist_pilot_2026.csv")
    frame.loc[frame["Parameter_Name"] == "Market_Window_Open", "Value"] = 0.5
    path = tmp_path / "fractional_window.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(DataLoadError, match="Market_Window_Open.*0 or 1"):
        CsvProductionLoader().load(path)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"calendar_hours": 0.0}, "NON_POSITIVE_CALENDAR"),
        ({"planned_hours": 721.0}, "PLANNED_EXCEEDS_CALENDAR"),
        ({"actual_hours": 481.0}, "ACTUAL_EXCEEDS_PLANNED"),
        ({"first_pass_good_units": 96.0}, "FPY_UNITS_EXCEED_OUTPUT"),
        ({"final_good_units": 96.0}, "FINAL_UNITS_EXCEED_OUTPUT"),
        ({"energy_kwh": -1.0}, "NEGATIVE_ENERGY"),
        ({"energy_cost_rate": -0.01}, "NEGATIVE_ENERGY_RATE"),
        ({"equipment_capex": -1.0}, "NEGATIVE_CAPEX"),
        ({"opex_overhead": -1.0}, "NEGATIVE_OPEX_OVERHEAD"),
        ({"price_erosion_rate": -0.01}, "NEGATIVE_PRICE_EROSION"),
        ({"market_window_open": 2}, "INVALID_MARKET_WINDOW"),
        ({"amortization_years_economic": 0.0}, "NON_POSITIVE_AMORTIZATION"),
        ({"market_horizon": 0.0}, "NON_POSITIVE_MARKET_HORIZON"),
    ],
)
def test_validator_reports_invalid_ranges(valid_data, changes, code):
    """Catches acceptance of physically or mathematically invalid input."""
    issues = DataValidator().validate(replace(valid_data, **changes))

    assert code in {issue.code for issue in issues}
    assert any(issue.severity is ValidationSeverity.ERROR for issue in issues if issue.code == code)


def test_negative_raw_material_cost_is_error_in_normal_mode(valid_data):
    """Catches accidental treatment of a subsidy as ordinary baseline data."""
    data = replace(valid_data, raw_material_cost=-1.0)

    issues = DataValidator().validate(data, ScenarioMode.NORMAL)

    issue = next(item for item in issues if item.code == "NEGATIVE_RAW_MATERIAL_COST")
    assert issue.severity is ValidationSeverity.ERROR
    assert issue.category == "INPUT_ERROR"


def test_negative_raw_material_cost_is_intentional_in_stress_mode(valid_data):
    """Catches a validator that blocks the required subsidy stress case."""
    data = replace(valid_data, raw_material_cost=-1.0)

    issues = DataValidator().validate(data, ScenarioMode.INTENTIONAL_STRESS)

    issue = next(item for item in issues if item.code == "NEGATIVE_RAW_MATERIAL_COST")
    assert issue.severity is ValidationSeverity.WARNING
    assert issue.category == "INTENTIONAL_STRESS_CONDITION"
