"""CSV adapters that construct typed production input."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from .models import ProductionData


class DataLoadError(ValueError):
    """Raised when a CSV cannot be mapped to the domain model."""


CSV_TO_FIELD: dict[str, str] = {
    "Calendar_Hours": "calendar_hours",
    "Planned_Hours": "planned_hours",
    "Actual_Hours": "actual_hours",
    "Target_Output": "target_output",
    "Actual_Output": "actual_output",
    "First_Pass_Good_Units": "first_pass_good_units",
    "Final_Good_Units": "final_good_units",
    "Raw_Material_Cost": "raw_material_cost",
    "Energy_kWh": "energy_kwh",
    "Energy_Cost_Rate": "energy_cost_rate",
    "Equipment_CAPEX": "equipment_capex",
    "Amortization_Years_Economic": "amortization_years_economic",
    "OPEX_Overhead": "opex_overhead",
    "Delay_Years": "delay_years",
    "Discount_Rate": "discount_rate",
    "Price_Erosion_Rate": "price_erosion_rate",
    "Market_Horizon": "market_horizon",
    "Market_Window_Open": "market_window_open",
}


class CsvProductionLoader:
    """Load the parameter-per-row CSV representation."""

    def load(self, path: Path) -> ProductionData:
        """Read *path*, validate its structure, and return typed data."""
        path = Path(path)
        if not path.is_file():
            raise DataLoadError(f"CSV file not found: {path}")

        frame = pd.read_csv(path)
        required_columns = {"Parameter_Name", "Value", "Unit"}
        missing_columns = required_columns.difference(frame.columns)
        if missing_columns:
            raise DataLoadError(
                "Missing CSV columns: " + ", ".join(sorted(missing_columns))
            )

        names = frame["Parameter_Name"].astype(str)
        duplicate_names = sorted(names[names.duplicated()].unique())
        if duplicate_names:
            raise DataLoadError(
                "Duplicate parameters: " + ", ".join(duplicate_names)
            )

        rows = frame.set_index("Parameter_Name", drop=False)
        missing_parameters = sorted(set(CSV_TO_FIELD).difference(rows.index))
        if missing_parameters:
            raise DataLoadError(
                "Missing required parameters: " + ", ".join(missing_parameters)
            )

        values: dict[str, float | int] = {}
        units: dict[str, str] = {}
        descriptions: dict[str, str] = {}
        for source_name, field_name in CSV_TO_FIELD.items():
            row = rows.loc[source_name]
            try:
                numeric_value = float(row["Value"])
            except (TypeError, ValueError) as exc:
                raise DataLoadError(
                    f"{source_name} must contain a finite numeric value"
                ) from exc
            if not math.isfinite(numeric_value):
                raise DataLoadError(
                    f"{source_name} must contain a finite numeric value"
                )
            values[field_name] = numeric_value
            units[source_name] = str(row["Unit"])
            if "Description" in frame.columns and pd.notna(row.get("Description")):
                descriptions[source_name] = str(row["Description"])
            elif "Group" in frame.columns and pd.notna(row.get("Group")):
                descriptions[source_name] = str(row["Group"])
            else:
                descriptions[source_name] = ""

        values["market_window_open"] = int(values["market_window_open"])
        return ProductionData(
            **values,
            units=units,
            descriptions=descriptions,
        )

