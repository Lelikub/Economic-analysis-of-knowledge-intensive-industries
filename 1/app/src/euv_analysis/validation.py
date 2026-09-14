"""Business validation for production scenarios."""

from __future__ import annotations

from .models import (
    ProductionData,
    ScenarioMode,
    ValidationIssue,
    ValidationSeverity,
)


class DataValidator:
    """Return all input problems without hiding intentional anomalies."""

    def validate(
        self,
        data: ProductionData,
        mode: ScenarioMode = ScenarioMode.NORMAL,
    ) -> list[ValidationIssue]:
        """Validate physical ranges and scenario-specific policies."""
        issues: list[ValidationIssue] = []

        def error(code: str, parameter: str, message: str) -> None:
            issues.append(
                ValidationIssue(
                    code=code,
                    parameter=parameter,
                    severity=ValidationSeverity.ERROR,
                    category="INPUT_ERROR",
                    message=message,
                )
            )

        checks: list[tuple[bool, str, str, str]] = [
            (
                data.calendar_hours <= 0,
                "NON_POSITIVE_CALENDAR",
                "Calendar_Hours",
                "Calendar_Hours must be greater than zero",
            ),
            (
                data.planned_hours < 0,
                "NEGATIVE_PLANNED_HOURS",
                "Planned_Hours",
                "Planned_Hours cannot be negative",
            ),
            (
                data.planned_hours > data.calendar_hours,
                "PLANNED_EXCEEDS_CALENDAR",
                "Planned_Hours",
                "Planned_Hours cannot exceed Calendar_Hours",
            ),
            (
                data.actual_hours < 0,
                "NEGATIVE_ACTUAL_HOURS",
                "Actual_Hours",
                "Actual_Hours cannot be negative",
            ),
            (
                data.actual_hours > data.planned_hours,
                "ACTUAL_EXCEEDS_PLANNED",
                "Actual_Hours",
                "Actual_Hours cannot exceed Planned_Hours",
            ),
            (
                data.target_output < 0,
                "NEGATIVE_TARGET_OUTPUT",
                "Target_Output",
                "Target_Output cannot be negative",
            ),
            (
                data.actual_output < 0,
                "NEGATIVE_ACTUAL_OUTPUT",
                "Actual_Output",
                "Actual_Output cannot be negative",
            ),
            (
                data.first_pass_good_units < 0,
                "NEGATIVE_FPY_UNITS",
                "First_Pass_Good_Units",
                "First_Pass_Good_Units cannot be negative",
            ),
            (
                data.final_good_units < 0,
                "NEGATIVE_FINAL_UNITS",
                "Final_Good_Units",
                "Final_Good_Units cannot be negative",
            ),
            (
                data.first_pass_good_units > data.actual_output,
                "FPY_UNITS_EXCEED_OUTPUT",
                "First_Pass_Good_Units",
                "First_Pass_Good_Units cannot exceed Actual_Output",
            ),
            (
                data.final_good_units > data.actual_output,
                "FINAL_UNITS_EXCEED_OUTPUT",
                "Final_Good_Units",
                "Final_Good_Units cannot exceed Actual_Output",
            ),
            (
                data.amortization_years_economic <= 0,
                "NON_POSITIVE_AMORTIZATION",
                "Amortization_Years_Economic",
                "Amortization_Years_Economic must be greater than zero",
            ),
            (
                data.market_horizon <= 0,
                "NON_POSITIVE_MARKET_HORIZON",
                "Market_Horizon",
                "Market_Horizon must be greater than zero",
            ),
            (
                data.market_window_open not in (0, 1),
                "INVALID_MARKET_WINDOW",
                "Market_Window_Open",
                "Market_Window_Open must be 0 or 1",
            ),
            (
                data.energy_kwh < 0,
                "NEGATIVE_ENERGY",
                "Energy_kWh",
                "Energy_kWh cannot be negative",
            ),
            (
                data.delay_years < 0,
                "NEGATIVE_DELAY",
                "Delay_Years",
                "Delay_Years cannot be negative",
            ),
            (
                data.discount_rate <= -1,
                "INVALID_DISCOUNT_RATE",
                "Discount_Rate",
                "Discount_Rate must be greater than -1",
            ),
        ]
        for failed, code, parameter, message in checks:
            if failed:
                error(code, parameter, message)

        if data.raw_material_cost < 0:
            if mode is ScenarioMode.INTENTIONAL_STRESS:
                issues.append(
                    ValidationIssue(
                        code="NEGATIVE_RAW_MATERIAL_COST",
                        parameter="Raw_Material_Cost",
                        severity=ValidationSeverity.WARNING,
                        category="INTENTIONAL_STRESS_CONDITION",
                        message="Negative material cost models an explicit subsidy",
                    )
                )
            else:
                error(
                    "NEGATIVE_RAW_MATERIAL_COST",
                    "Raw_Material_Cost",
                    "Raw_Material_Cost cannot be negative in a normal scenario",
                )

        return issues
