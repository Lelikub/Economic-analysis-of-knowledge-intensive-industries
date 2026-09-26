"""Загрузка, типизация и структурный аудит источников."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .models import (
    AmmoniaFixedOpexItem, AmmoniaVariableOpexItem, CompressorData,
    CogenerationData, EconomicConstants, EnergyStream, InputDataError,
    MachineryFixedOpexItem, MachineryVariableOpexItem, ProjectInputData, SpecoStage,
)


REQUIRED = {
    "opex_ammonia_raw.csv": ["Resource_Name", "Resource_Type", "Specific_Consumption_si", "Consumption_Unit", "Price_pi_USD", "Price_Unit", "Cost_per_ton_USD"],
    "opex_ammonia_fixed.csv": ["Cost_Item", "Annual_Cost_MUSD", "Description"],
    "khimmash_bom_opex.csv": ["Cost_Item", "Cost_Per_Unit_MUSD", "Share_in_Variable_Pct", "Engineering_Details"],
    "khimmash_fixed_opex.csv": ["Cost_Item", "Annual_Cost_MUSD", "Is_Step_Fixed", "Can_Be_Saved_at_Low_Load_MUSD"],
    "streams_energy_balance.csv": ["Stream_ID", "Stream_Name", "Mass_Flow_kg_s", "Temperature_C", "Pressure_bar", "Enthalpy_kJ_kg", "Entropy_kJ_kg_K"],
    "sequential_chain_speco.csv": ["Stage_Number", "Unit_Name", "Exergy_Fuel_In_MW", "Exergy_Product_Out_MW", "Exergy_Destruction_MW", "Exergetic_Efficiency_eta", "Z_dot_USD_per_h"],
}

NUMERIC = {
    "opex_ammonia_raw.csv": ["Specific_Consumption_si", "Price_pi_USD", "Cost_per_ton_USD"],
    "opex_ammonia_fixed.csv": ["Annual_Cost_MUSD"],
    "khimmash_bom_opex.csv": ["Cost_Per_Unit_MUSD", "Share_in_Variable_Pct"],
    "khimmash_fixed_opex.csv": ["Annual_Cost_MUSD", "Can_Be_Saved_at_Low_Load_MUSD"],
    "streams_energy_balance.csv": ["Mass_Flow_kg_s", "Temperature_C", "Pressure_bar", "Enthalpy_kJ_kg", "Entropy_kJ_kg_K"],
    "sequential_chain_speco.csv": ["Stage_Number", "Exergy_Fuel_In_MW", "Exergy_Product_Out_MW", "Exergy_Destruction_MW", "Exergetic_Efficiency_eta", "Z_dot_USD_per_h"],
}


class DataLoader:
    """Читает каждый источник и фиксирует его качество без изменения данных."""
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.quality: dict[str, Any] = {"files": {}, "cross_checks": [], "status": "PASS"}
        self._csv_rows: dict[str, list[dict[str, str]]] = {}
        self._json_data: dict[str, dict] = {}

    @staticmethod
    def number(value: Any, label: str, negative_allowed: bool = False) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise InputDataError(f"Некорректное число {label}: {value!r}") from exc
        if not math.isfinite(result) or (result < 0 and not negative_allowed):
            raise InputDataError(f"Некорректный диапазон {label}: {value!r}")
        return result

    def read_csv(self, name: str) -> list[dict[str, str]]:
        path = self.data_dir / name
        if not path.is_file():
            raise InputDataError(f"Отсутствует файл {path}")
        raw = path.read_bytes()
        try:
            decoded = raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InputDataError(f"Не UTF-8 файл {name}") from exc
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames or []
            missing_columns = sorted(set(REQUIRED[name]) - set(columns))
            if missing_columns:
                raise InputDataError(f"Отсутствуют столбцы {name}: {missing_columns}")
            rows = list(reader)
        if not rows:
            raise InputDataError(f"Пустой файл {name}")
        missing = {c: sum(row.get(c) in (None, "") for row in rows) for c in columns}
        type_issues = []
        numeric_ranges: dict[str, list[float]] = {}
        for c in NUMERIC[name]:
            values = []
            for index, row in enumerate(rows, start=2):
                try:
                    values.append(self.number(row.get(c), f"{name}:{index}:{c}", c == "Temperature_C"))
                except InputDataError as exc:
                    type_issues.append(str(exc))
            if values:
                numeric_ranges[c] = [min(values), max(values)]
        if type_issues:
            raise InputDataError("; ".join(type_issues))
        duplicates = len(rows) - len({tuple(row.get(c) for c in columns) for row in rows})
        unit_issues = []
        if name == "opex_ammonia_raw.csv":
            for row in rows:
                if not row["Consumption_Unit"] or not row["Price_Unit"]:
                    unit_issues.append(row["Resource_Name"])
        self.quality["files"][name] = {
            "rows": len(rows), "columns": columns, "encoding": "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "missing_values": missing, "duplicates": duplicates, "type_issues": [],
            "unit_issues": unit_issues, "numeric_ranges": numeric_ranges,
            "status": "WARNING" if duplicates or any(missing.values()) or unit_issues else "PASS",
        }
        self._csv_rows[name] = rows
        return rows

    def read_json(self, name: str) -> dict:
        path = self.data_dir / name
        if not path.is_file():
            raise InputDataError(f"Отсутствует файл {path}")
        raw = path.read_bytes()
        try:
            result = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise InputDataError(f"Некорректный JSON {name}") from exc
        if not isinstance(result, dict):
            raise InputDataError(f"JSON {name} должен содержать объект")
        def check_numbers(node: Any, location: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    check_numbers(value, f"{location}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    check_numbers(value, f"{location}[{index}]")
            elif isinstance(node, (int, float)) and not isinstance(node, bool):
                if not math.isfinite(node) or node < 0:
                    raise InputDataError(f"Отрицательный тариф или некорректный числовой параметр JSON: {location}")
                if ("Temperature_T0_K" in location or "Annual_Work_Hours" in location or "Total_Mass_Flow" in location) and node <= 0:
                    raise InputDataError(f"Параметр JSON должен быть положительным: {location}")
        check_numbers(result, name)
        self.quality["files"][name] = {"rows": 1, "columns": list(result), "encoding": "utf-8",
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "missing_values": {}, "duplicates": 0, "type_issues": [], "unit_issues": [], "status": "PASS"}
        self._json_data[name] = result
        return result

    def audit(self) -> dict:
        """Возвращает фактический аудит после `load`."""
        return self.quality

    def _audit_workbook(self) -> None:
        path = self.data_dir / "project_input_data_module2.xlsx"
        if not path.is_file():
            raise InputDataError(f"Отсутствует файл {path}")
        book = load_workbook(path, read_only=True, data_only=True)
        sheets = {}
        sheet_values = {}
        for sheet in book:
            rows = list(sheet.values)
            sheet_values[sheet.title] = rows
            sheets[sheet.title] = {"rows": max(len(rows) - 1, 0),
                                   "columns": list(rows[0]) if rows else [],
                                   "missing_values": sum(v is None for row in rows[1:] for v in row)}
        book.close()
        raw = path.read_bytes()
        self.quality["files"][path.name] = {"rows": sum(s["rows"] for s in sheets.values()),
            "columns": list(sheets), "sheets": sheets, "encoding": "xlsx", "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "missing_values": {},
            "duplicates": 0, "type_issues": [], "unit_issues": [], "status": "PASS"}
        mapping = {"OPEX_Ammonia_Var": "opex_ammonia_raw.csv", "OPEX_Ammonia_Fix": "opex_ammonia_fixed.csv",
                   "KhimMash_BOM_Var": "khimmash_bom_opex.csv", "KhimMash_Fix": "khimmash_fixed_opex.csv",
                   "Energy_Balance": "streams_energy_balance.csv", "Sequential_Chain": "sequential_chain_speco.csv"}
        for sheet, csv_name in mapping.items():
            csv_rows = self.quality["files"][csv_name]["rows"]
            xlsx_rows = sheets[sheet]["rows"]
            workbook_rows = sheet_values[sheet]
            indices = {name: index for index, name in enumerate(workbook_rows[0])}
            differences = []
            for row_number, (csv_row, workbook_row) in enumerate(zip(self._csv_rows[csv_name], workbook_rows[1:]), start=2):
                for name in NUMERIC[csv_name]:
                    if name not in indices:
                        differences.append(f"{sheet}: нет столбца {name}")
                        continue
                    source = float(csv_row[name])
                    other = workbook_row[indices[name]]
                    if not isinstance(other, (int, float)) or not math.isclose(source, other, rel_tol=1e-10, abs_tol=1e-10):
                        differences.append(f"{sheet}:{row_number}:{name}: CSV={source}, XLSX={other}")
            self.quality["cross_checks"].append({"csv": csv_name, "sheet": sheet,
                "csv_rows": csv_rows, "xlsx_rows": xlsx_rows,
                "numeric_discrepancies": differences,
                "status": "PASS" if csv_rows == xlsx_rows and not differences else "WARNING"})
        json_mapping = {
            "Tariffs_Utilities": ("project_economic_constants.json", self._json_data["project_economic_constants.json"]["Tariffs_and_Market_Prices"]),
            "Compressors_Summary": ("compressors_parallel.json", self._json_data["compressors_parallel.json"]["Analytical_Solution"]),
            "Cogen_Turbine_Inlet": ("exergy_cogen_speco.json", self._json_data["exergy_cogen_speco.json"]["High_Pressure_Steam_Inlet"]),
        }
        for sheet, (json_name, values) in json_mapping.items():
            workbook_rows = sheet_values[sheet]
            columns, row = workbook_rows[0], workbook_rows[1]
            differences = []
            for key, value in zip(columns, row):
                if key in values and isinstance(value, (int, float)) and not math.isclose(float(value), float(values[key]), rel_tol=1e-10, abs_tol=1e-10):
                    differences.append(f"{sheet}:{key}: JSON={values[key]}, XLSX={value}")
            self.quality["cross_checks"].append({"json": json_name, "sheet": sheet,
                "numeric_discrepancies": differences, "status": "PASS" if not differences else "WARNING",
                "role": "только контроль после расчёта" if sheet != "Tariffs_Utilities" else "контроль тарифов"})
        if any(x["status"] != "PASS" for x in self.quality["cross_checks"]):
            self.quality["status"] = "WARNING"

    def load(self) -> ProjectInputData:
        a_var = self.read_csv("opex_ammonia_raw.csv")
        a_fix = self.read_csv("opex_ammonia_fixed.csv")
        m_var = self.read_csv("khimmash_bom_opex.csv")
        m_fix = self.read_csv("khimmash_fixed_opex.csv")
        streams = self.read_csv("streams_energy_balance.csv")
        chain = self.read_csv("sequential_chain_speco.csv")
        constants = self.read_json("project_economic_constants.json")
        compressors = self.read_json("compressors_parallel.json")
        cogen = self.read_json("exergy_cogen_speco.json")
        self._audit_workbook()
        if len({r["Stream_ID"] for r in streams}) != len(streams):
            raise InputDataError("Повторяющиеся Stream_ID")
        if len({r["Stage_Number"] for r in chain}) != len(chain):
            raise InputDataError("Повторяющиеся Stage_Number")
        for r in m_fix:
            if r["Is_Step_Fixed"] not in ("True", "False"):
                raise InputDataError("Некорректный bool Is_Step_Fixed")
        return ProjectInputData(
            ammonia_variable_opex=[AmmoniaVariableOpexItem(r["Resource_Name"], float(r["Specific_Consumption_si"]), r["Consumption_Unit"], float(r["Price_pi_USD"]), r["Price_Unit"], float(r["Cost_per_ton_USD"])) for r in a_var],
            ammonia_fixed_opex=[AmmoniaFixedOpexItem(r["Cost_Item"], float(r["Annual_Cost_MUSD"])) for r in a_fix],
            machinery_variable_opex=[MachineryVariableOpexItem(r["Cost_Item"], float(r["Cost_Per_Unit_MUSD"]), float(r["Share_in_Variable_Pct"])) for r in m_var],
            machinery_fixed_opex=[MachineryFixedOpexItem(r["Cost_Item"], float(r["Annual_Cost_MUSD"]), r["Is_Step_Fixed"] == "True", float(r["Can_Be_Saved_at_Low_Load_MUSD"])) for r in m_fix],
            energy_streams=[EnergyStream(r["Stream_ID"], r["Stream_Name"], float(r["Mass_Flow_kg_s"]), float(r["Temperature_C"]), float(r["Pressure_bar"]), float(r["Enthalpy_kJ_kg"]), float(r["Entropy_kJ_kg_K"])) for r in streams],
            speco_chain=[SpecoStage(int(r["Stage_Number"]), r["Unit_Name"], float(r["Exergy_Fuel_In_MW"]), float(r["Exergy_Product_Out_MW"]), float(r["Exergy_Destruction_MW"]), float(r["Exergetic_Efficiency_eta"]), float(r["Z_dot_USD_per_h"])) for r in chain],
            compressors=CompressorData(compressors), cogeneration=CogenerationData(cogen),
            economic_constants=EconomicConstants(constants),
        )
