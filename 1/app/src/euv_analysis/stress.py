"""Comparison-input verification and stress scenario analysis."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import pandas as pd

from .models import MetricsResult


class ComparisonDataError(ValueError):
    """Raised when the comparison CSV has no usable numeric structure."""


@dataclass(frozen=True, slots=True)
class ComparisonValidationResult:
    """Verified values and checks from the comparison CSV."""

    valid: bool
    checks: dict[str, bool]
    energy_rate: tuple[float, float]
    fpy: tuple[float, float]
    delay: tuple[float, float]
    messages: tuple[str, ...]


class ComparisonCsvValidator:
    """Validate numbers in the comparison CSV rather than trusting notes."""

    def validate(self, path: Path) -> ComparisonValidationResult:
        """Return independent checks for the three required changes."""
        frame = pd.read_csv(Path(path))
        required_columns = {
            "Parameter_Name",
            "Baseline_Value",
            "Stressed_Value",
            "Stress_Note",
        }
        missing = required_columns.difference(frame.columns)
        if missing:
            raise ComparisonDataError(
                "Missing comparison columns: " + ", ".join(sorted(missing))
            )
        if frame["Parameter_Name"].duplicated().any():
            raise ComparisonDataError("Comparison parameters must be unique")
        rows = frame.set_index("Parameter_Name")

        def pair(parameter: str) -> tuple[float, float]:
            if parameter not in rows.index:
                raise ComparisonDataError(f"Missing comparison parameter: {parameter}")
            baseline = float(rows.at[parameter, "Baseline_Value"])
            stress = float(rows.at[parameter, "Stressed_Value"])
            if not math.isfinite(baseline) or not math.isfinite(stress):
                raise ComparisonDataError(f"Non-finite comparison value: {parameter}")
            return baseline, stress

        energy_rate = pair("Energy_Cost_Rate")
        first_pass = pair("First_Pass_Good_Units")
        actual_output = pair("Actual_Output")
        delay = pair("Delay_Years")
        if actual_output[0] == 0 or actual_output[1] == 0:
            raise ComparisonDataError("Actual_Output cannot be zero for FPY comparison")
        fpy = (
            first_pass[0] / actual_output[0],
            first_pass[1] / actual_output[1],
        )
        checks = {
            "ENERGY_RATE_TRIPLED": math.isclose(
                energy_rate[1], energy_rate[0] * 3.0, rel_tol=0.0, abs_tol=1e-12
            ),
            "FPY_75_TO_40": math.isclose(fpy[0], 0.75, abs_tol=1e-12)
            and math.isclose(fpy[1], 0.40, abs_tol=1e-12),
            "DELAY_0_TO_0_5": math.isclose(delay[0], 0.0, abs_tol=1e-12)
            and math.isclose(delay[1], 0.5, abs_tol=1e-12),
        }
        messages = tuple(name for name, passed in checks.items() if not passed)
        return ComparisonValidationResult(
            valid=all(checks.values()),
            checks=checks,
            energy_rate=energy_rate,
            fpy=fpy,
            delay=delay,
            messages=messages,
        )


@dataclass(frozen=True, slots=True)
class StressComparisonRow:
    """One baseline-versus-stress metric comparison."""

    metric: str
    baseline: float | None
    stress: float | None
    absolute_change: float | None
    relative_change: float | None
    interpretation: str


class StressAnalyzer:
    """Build the required stress comparison from calculated results."""

    _INTERPRETATIONS = {
        "FPY": "Падение FPY отражает рост переделок и потерь первого прохода.",
        "OEE": "Снижение Quality напрямую уменьшает OEE.",
        "TEEP": "TEEP снижается вместе с OEE при неизменной календарной загрузке.",
        "Energy Cost": "Трёхкратный тариф увеличивает затраты на электроэнергию.",
        "Economic Intensity": "Рост затрат увеличивает стоимость ресурсов на литр годной продукции.",
        "CPU": "Рост полной стоимости повышает себестоимость итогового годного литра.",
        "TTM Penalty": "Задержка одновременно дисконтирует деньги, снижает цену и сокращает рынок.",
    }

    def compare(
        self,
        baseline: MetricsResult,
        stress: MetricsResult,
        *,
        baseline_ttm: float,
        stress_ttm: float,
    ) -> list[StressComparisonRow]:
        """Compare the seven required metrics without recomputing them."""
        value_pairs = [
            ("FPY", baseline.fpy.value, stress.fpy.value),
            ("OEE", baseline.oee.value, stress.oee.value),
            ("TEEP", baseline.teep.value, stress.teep.value),
            ("Energy Cost", baseline.energy_cost.value, stress.energy_cost.value),
            (
                "Economic Intensity",
                baseline.economic_intensity.value,
                stress.economic_intensity.value,
            ),
            ("CPU", baseline.cpu.value, stress.cpu.value),
            ("TTM Penalty", baseline_ttm, stress_ttm),
        ]
        rows: list[StressComparisonRow] = []
        for name, baseline_value, stress_value in value_pairs:
            if baseline_value is None or stress_value is None:
                absolute_change = None
                relative_change = None
            else:
                absolute_change = stress_value - baseline_value
                relative_change = (
                    absolute_change / abs(baseline_value)
                    if baseline_value != 0
                    else None
                )
            rows.append(
                StressComparisonRow(
                    name,
                    baseline_value,
                    stress_value,
                    absolute_change,
                    relative_change,
                    self._INTERPRETATIONS[name],
                )
            )
        return rows

