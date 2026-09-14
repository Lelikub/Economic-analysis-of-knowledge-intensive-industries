"""Operational, cost, and resource-intensity calculations."""

from __future__ import annotations

from .models import MetricStatus, MetricsResult, MetricValue, ProductionData


def _not_computable(name: str, unit: str, formula: str, note: str) -> MetricValue:
    return MetricValue(
        name=name,
        value=None,
        unit=unit,
        formula=formula,
        status=MetricStatus.NOT_COMPUTABLE,
        note=note,
    )


def _ratio(
    name: str,
    numerator: float,
    denominator: float,
    unit: str,
    formula: str,
) -> MetricValue:
    if denominator == 0:
        return _not_computable(name, unit, formula, "Denominator is zero")
    return MetricValue(name, numerator / denominator, unit, formula)


class OperationalMetricsCalculator:
    """Calculate all required Python reference metrics from typed data."""

    def calculate(self, data: ProductionData) -> MetricsResult:
        """Calculate metrics without rounding intermediate results."""
        fpy = _ratio(
            "FPY",
            data.first_pass_good_units,
            data.actual_output,
            "dimensionless",
            "First_Pass_Good_Units / Actual_Output",
        )
        final_yield = _ratio(
            "Final Yield",
            data.final_good_units,
            data.actual_output,
            "dimensionless",
            "Final_Good_Units / Actual_Output",
        )
        availability = _ratio(
            "Availability",
            data.actual_hours,
            data.planned_hours,
            "dimensionless",
            "Actual_Hours / Planned_Hours",
        )

        if data.target_output == 0 or data.actual_hours == 0:
            performance = _not_computable(
                "Performance",
                "dimensionless",
                "(Planned_Hours / Target_Output) * Actual_Output / Actual_Hours",
                "Target_Output or Actual_Hours is zero",
            )
        else:
            performance = MetricValue(
                "Performance",
                (data.planned_hours / data.target_output)
                * data.actual_output
                / data.actual_hours,
                "dimensionless",
                "(Planned_Hours / Target_Output) * Actual_Output / Actual_Hours",
                note="Normative cycle time is derived as Planned_Hours / Target_Output",
            )

        quality = MetricValue(
            "Quality",
            fpy.value,
            "dimensionless",
            "Quality = FPY",
            status=fpy.status,
            note=fpy.note,
        )
        if any(
            metric.status is MetricStatus.NOT_COMPUTABLE
            for metric in (availability, performance, quality)
        ):
            oee = _not_computable(
                "OEE",
                "dimensionless",
                "Availability * Performance * Quality",
                "At least one OEE factor is not computable",
            )
        else:
            oee = MetricValue(
                "OEE",
                availability.value * performance.value * quality.value,
                "dimensionless",
                "Availability * Performance * Quality",
            )

        utilization = _ratio(
            "Utilization",
            data.planned_hours,
            data.calendar_hours,
            "dimensionless",
            "Planned_Hours / Calendar_Hours",
        )
        if oee.value is None or utilization.value is None:
            teep = _not_computable(
                "TEEP",
                "dimensionless",
                "OEE * Utilization",
                "OEE or Utilization is not computable",
            )
        else:
            teep = MetricValue(
                "TEEP",
                oee.value * utilization.value,
                "dimensionless",
                "OEE * Utilization",
            )

        energy_cost = MetricValue(
            "Energy Cost",
            data.energy_kwh * data.energy_cost_rate,
            "USD/month",
            "Energy_kWh * Energy_Cost_Rate",
        )
        if data.amortization_years_economic == 0:
            monthly_depreciation = _not_computable(
                "Monthly Depreciation",
                "USD/month",
                "Equipment_CAPEX / Amortization_Years_Economic / 12",
                "Amortization_Years_Economic is zero",
            )
            total_cost = _not_computable(
                "Total Manufacturing Cost",
                "USD/month",
                "Raw_Material_Cost + Energy_Cost + OPEX_Overhead + Monthly_Depreciation",
                "Monthly depreciation is not computable",
            )
        else:
            monthly_depreciation = MetricValue(
                "Monthly Depreciation",
                data.equipment_capex / data.amortization_years_economic / 12.0,
                "USD/month",
                "Equipment_CAPEX / Amortization_Years_Economic / 12",
            )
            total_cost = MetricValue(
                "Total Manufacturing Cost",
                data.raw_material_cost
                + energy_cost.value
                + data.opex_overhead
                + monthly_depreciation.value,
                "USD/month",
                "Raw_Material_Cost + Energy_Cost + OPEX_Overhead + Monthly_Depreciation",
            )

        mass_intensity = _not_computable(
            "Mass Intensity",
            "kg/L",
            "Raw_Material_Mass_kg / Final_Good_Units",
            "Raw_Material_Mass_kg is absent from source data",
        )
        energy_intensity = _ratio(
            "Energy Intensity",
            data.energy_kwh,
            data.final_good_units,
            "kWh/L",
            "Energy_kWh / Final_Good_Units",
        )
        raw_material_cost_proxy = _ratio(
            "Raw Material Cost Proxy",
            data.raw_material_cost,
            data.final_good_units,
            "USD/L",
            "Raw_Material_Cost / Final_Good_Units",
        )
        if total_cost.value is None:
            economic_intensity = _not_computable(
                "Economic Intensity",
                "USD/L",
                "Total_Manufacturing_Cost / Final_Good_Units",
                "Total manufacturing cost is not computable",
            )
        else:
            economic_intensity = _ratio(
                "Economic Intensity",
                total_cost.value,
                data.final_good_units,
                "USD/L",
                "Total_Manufacturing_Cost / Final_Good_Units",
            )
        cpu = MetricValue(
            "CPU",
            economic_intensity.value,
            "USD/L",
            "Total_Manufacturing_Cost / Final_Good_Units",
            status=economic_intensity.status,
            note=economic_intensity.note,
        )

        return MetricsResult(
            fpy=fpy,
            final_yield=final_yield,
            availability=availability,
            performance=performance,
            quality=quality,
            oee=oee,
            utilization=utilization,
            teep=teep,
            energy_cost=energy_cost,
            monthly_depreciation=monthly_depreciation,
            total_manufacturing_cost=total_cost,
            mass_intensity=mass_intensity,
            energy_intensity=energy_intensity,
            economic_intensity=economic_intensity,
            raw_material_cost_proxy=raw_material_cost_proxy,
            cpu=cpu,
        )

