from __future__ import annotations

from pathlib import Path

import pytest

from euv_analysis.harness import MetricsHarness
from euv_analysis.loader import CsvProductionLoader
from euv_analysis.metrics import OperationalMetricsCalculator
from euv_analysis.stress import ComparisonCsvValidator, StressAnalyzer
from euv_analysis.visualization import OPEX_SHARES, OpexVisualizer


def test_harness_uses_numeric_tolerance():
    """Catches strict float equality in the Python/Excel comparison."""
    rows = MetricsHarness(tolerance=1e-9).compare(
        {"FPY": 0.75}, {"FPY": 0.7500000001}
    )

    assert rows[0].status == "PASS"
    assert rows[0].absolute_delta == pytest.approx(1e-10)
    assert rows[0].relative_delta == pytest.approx(1.333333443653829e-10)


def test_harness_detects_real_mismatch():
    """Catches a harness that creates a false PASS outside tolerance."""
    rows = MetricsHarness(tolerance=1e-9).compare(
        {"OEE": 0.59}, {"OEE": 0.60}
    )

    assert rows[0].status == "FAIL"
    assert rows[0].probable_cause == "Formula, input, or cached Excel value differs"


def test_harness_does_not_pass_missing_excel_value():
    """Catches a false PASS when Excel has not supplied a cached value."""
    rows = MetricsHarness().compare({"FPY": None}, {"FPY": 0.75})

    assert rows[0].status == "NOT_COMPUTABLE"
    assert rows[0].absolute_delta is None
    assert rows[0].probable_cause == "Excel value is unavailable"


def test_comparison_csv_validates_required_numeric_changes(data_dir):
    """Catches trusting Stress_Note without verifying comparison values."""
    result = ComparisonCsvValidator().validate(
        data_dir / "euv_photoresist_comparison_input_2026.csv"
    )

    assert result.valid is True
    assert result.energy_rate == pytest.approx((0.22, 0.66))
    assert result.fpy == pytest.approx((0.75, 0.40))
    assert result.delay == pytest.approx((0.0, 0.5))
    assert result.checks == {
        "ENERGY_RATE_TRIPLED": True,
        "FPY_75_TO_40": True,
        "DELAY_0_TO_0_5": True,
    }


def test_comparison_csv_rejects_unverified_note(tmp_path, data_dir):
    """Catches acceptance of a correct note attached to wrong numbers."""
    source = (data_dir / "euv_photoresist_comparison_input_2026.csv").read_text(
        encoding="utf-8"
    )
    path = tmp_path / "bad_comparison.csv"
    path.write_text(source.replace("0.22,0.66", "0.22,0.65"), encoding="utf-8")

    result = ComparisonCsvValidator().validate(path)

    assert result.valid is False
    assert result.checks["ENERGY_RATE_TRIPLED"] is False


def test_stress_analyzer_exports_required_changes(data_dir):
    """Catches mixing baseline and stress metrics or omitting unchanged values."""
    loader = CsvProductionLoader()
    calculator = OperationalMetricsCalculator()
    baseline = calculator.calculate(
        loader.load(data_dir / "euv_photoresist_pilot_2026.csv")
    )
    stress = calculator.calculate(
        loader.load(data_dir / "euv_photoresist_stress_2026.csv")
    )

    rows = StressAnalyzer().compare(
        baseline,
        stress,
        baseline_ttm=0.0,
        stress_ttm=0.26285941114120437,
    )
    indexed = {row.metric: row for row in rows}

    assert set(indexed) == {
        "FPY",
        "OEE",
        "TEEP",
        "Energy Cost",
        "Economic Intensity",
        "CPU",
        "TTM Penalty",
    }
    assert indexed["FPY"].baseline == pytest.approx(0.75)
    assert indexed["FPY"].stress == pytest.approx(0.40)
    assert indexed["Energy Cost"].absolute_change == pytest.approx(50_600.0)
    assert indexed["CPU"].absolute_change == pytest.approx(626.6253869969044)
    assert indexed["TTM Penalty"].baseline == 0.0


def test_opex_shares_sum_to_one_and_png_is_created(tmp_path):
    """Catches incomplete OPEX composition or an empty visualization artifact."""
    path = tmp_path / "opex.png"

    result = OpexVisualizer().create(path)

    assert sum(OPEX_SHARES.values()) == pytest.approx(1.0)
    assert result == path
    assert path.is_file()
    assert path.stat().st_size > 10_000
