from __future__ import annotations

from dataclasses import replace

import pytest

from euv_analysis.metrics import OperationalMetricsCalculator
from euv_analysis.models import MetricStatus


def test_baseline_operational_metrics_match_independent_values(valid_data):
    """Catches wrong inputs or factor order in the production formulas."""
    result = OperationalMetricsCalculator().calculate(valid_data)

    assert result.fpy.value == pytest.approx(0.75)
    assert result.final_yield.value == pytest.approx(0.85)
    assert result.availability.value == pytest.approx(0.8125)
    assert result.performance.value == pytest.approx(0.9743589743589743)
    assert result.quality.value == pytest.approx(0.75)
    assert result.oee.value == pytest.approx(0.59375)
    assert result.utilization.value == pytest.approx(2.0 / 3.0)
    assert result.teep.value == pytest.approx(0.3958333333333333)


def test_baseline_cost_metrics_match_independent_values(valid_data):
    """Catches omitted or double-counted manufacturing-cost components."""
    result = OperationalMetricsCalculator().calculate(valid_data)

    assert result.energy_cost.value == pytest.approx(25_300.0)
    assert result.monthly_depreciation.value == pytest.approx(777_777.7777777778)
    assert result.total_manufacturing_cost.value == pytest.approx(1_188_077.7777777778)
    assert result.energy_intensity.value == pytest.approx(1_424.1486068111456)
    assert result.economic_intensity.value == pytest.approx(14_713.037495700035)
    assert result.cpu.value == pytest.approx(14_713.037495700035)
    assert result.raw_material_cost_proxy.value == pytest.approx(2_972.136222910217)
    assert result.mass_intensity.status is MetricStatus.NOT_COMPUTABLE
    assert result.mass_intensity.value is None


def test_full_scrap_is_controlled(valid_data):
    """Catches division by zero or infinity when no final good product exists."""
    data = replace(valid_data, first_pass_good_units=0.0, final_good_units=0.0)

    result = OperationalMetricsCalculator().calculate(data)

    assert result.fpy.value == 0.0
    assert result.final_yield.value == 0.0
    assert result.oee.value == 0.0
    assert result.cpu.status is MetricStatus.NOT_COMPUTABLE
    assert result.energy_intensity.status is MetricStatus.NOT_COMPUTABLE
    assert result.economic_intensity.status is MetricStatus.NOT_COMPUTABLE


def test_ideal_factory_has_oee_of_one(valid_data):
    """Catches an OEE implementation that cannot reach its physical upper bound."""
    data = replace(
        valid_data,
        actual_hours=480.0,
        actual_output=120.0,
        first_pass_good_units=120.0,
        final_good_units=120.0,
    )

    result = OperationalMetricsCalculator().calculate(data)

    assert result.availability.value == pytest.approx(1.0)
    assert result.performance.value == pytest.approx(1.0)
    assert result.quality.value == pytest.approx(1.0)
    assert result.oee.value == pytest.approx(1.0)


def test_material_subsidy_reduces_cost_and_intensity(valid_data):
    """Catches loss of the required negative-material-cost stress semantics."""
    baseline = OperationalMetricsCalculator().calculate(valid_data)
    subsidized = OperationalMetricsCalculator().calculate(
        replace(valid_data, raw_material_cost=-1_000.0)
    )

    assert subsidized.total_manufacturing_cost.value == pytest.approx(
        baseline.total_manufacturing_cost.value - 241_000.0
    )
    assert subsidized.cpu.value < baseline.cpu.value
    assert subsidized.economic_intensity.value < baseline.economic_intensity.value


@pytest.mark.parametrize(
    "changes, metric_name",
    [
        ({"actual_output": 0.0, "first_pass_good_units": 0.0, "final_good_units": 0.0}, "fpy"),
        ({"planned_hours": 0.0, "actual_hours": 0.0}, "availability"),
        ({"target_output": 0.0}, "performance"),
    ],
)
def test_zero_denominators_are_not_computable(valid_data, changes, metric_name):
    """Catches unhandled division by zero in individual metric factors."""
    result = OperationalMetricsCalculator().calculate(replace(valid_data, **changes))

    metric = getattr(result, metric_name)
    assert metric.status is MetricStatus.NOT_COMPUTABLE
    assert metric.value is None


def test_metric_dimensions_are_explicit(valid_data):
    """Catches loss of dimensional traceability in exported results."""
    result = OperationalMetricsCalculator().calculate(valid_data)

    assert result.fpy.unit == "dimensionless"
    assert result.energy_intensity.unit == "kWh/L"
    assert result.cpu.unit == "USD/L"
