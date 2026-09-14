"""Independent Excel Ground Truth workbook and recalculation adapter."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill

from .models import ProductionData


LOGGER = logging.getLogger(__name__)


PARAMETER_FIELDS: tuple[tuple[str, str], ...] = (
    ("Calendar_Hours", "calendar_hours"),
    ("Planned_Hours", "planned_hours"),
    ("Actual_Hours", "actual_hours"),
    ("Target_Output", "target_output"),
    ("Actual_Output", "actual_output"),
    ("First_Pass_Good_Units", "first_pass_good_units"),
    ("Final_Good_Units", "final_good_units"),
    ("Raw_Material_Cost", "raw_material_cost"),
    ("Energy_kWh", "energy_kwh"),
    ("Energy_Cost_Rate", "energy_cost_rate"),
    ("Equipment_CAPEX", "equipment_capex"),
    ("Amortization_Years_Economic", "amortization_years_economic"),
    ("OPEX_Overhead", "opex_overhead"),
    ("Delay_Years", "delay_years"),
    ("Discount_Rate", "discount_rate"),
    ("Price_Erosion_Rate", "price_erosion_rate"),
    ("Market_Horizon", "market_horizon"),
    ("Market_Window_Open", "market_window_open"),
)


GROUND_TRUTH_CELLS: dict[str, tuple[str, str]] = {
    "FPY": ("Metrics", "D2"),
    "Final Yield": ("Metrics", "D3"),
    "Availability": ("Metrics", "D4"),
    "Performance": ("Metrics", "D5"),
    "Quality": ("Metrics", "D6"),
    "OEE": ("Metrics", "D7"),
    "Utilization": ("Metrics", "D8"),
    "TEEP": ("Metrics", "D9"),
    "Energy Intensity": ("Metrics", "D10"),
    "Economic Intensity": ("Metrics", "D11"),
    "CPU": ("Metrics", "D12"),
    "Mass Intensity": ("Metrics", "D13"),
    "TTM Penalty Assignment": ("Metrics", "D14"),
    "TTM Penalty CSV": ("Metrics", "D15"),
    "Energy Cost": ("Costs", "D2"),
    "Monthly Depreciation": ("Costs", "D3"),
    "Total Manufacturing Cost": ("Costs", "D4"),
    "Raw Material Cost Proxy": ("Costs", "D7"),
}


def _style_sheet(sheet, widths: dict[str, float]) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width


def _ttm_formula(row: int) -> str:
    return (
        f"=IF(OR(F{row}=0,E{row}>=D{row}),1,"
        f"1-(1/(1+B{row})^E{row})*EXP(-C{row}*E{row})*"
        f"((D{row}-E{row})/D{row})*F{row})"
    )


class ExcelGroundTruthBuilder:
    """Build an xlsx workbook whose results are native Excel formulas."""

    def build(
        self,
        path: Path,
        baseline: ProductionData,
        stress: ProductionData,
        *,
        opex_chart_path: Path | None = None,
        assumptions: list[dict[str, str]] | None = None,
        data_issues: list[dict[str, str]] | None = None,
    ) -> Path:
        """Create the Ground Truth workbook without using Python metrics."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        workbook.remove(workbook.active)
        workbook.calculation.calcMode = "auto"
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True

        source = workbook.create_sheet("Source Data")
        source.append(["Scenario", "Parameter", "Value", "Unit", "Description"])
        refs: dict[str, dict[str, str]] = {"Baseline": {}, "Stress": {}}
        for scenario_name, data in (("Baseline", baseline), ("Stress", stress)):
            for parameter_name, field_name in PARAMETER_FIELDS:
                row_number = source.max_row + 1
                source.append(
                    [
                        scenario_name,
                        parameter_name,
                        getattr(data, field_name),
                        data.units.get(parameter_name, ""),
                        data.descriptions.get(parameter_name, ""),
                    ]
                )
                refs[scenario_name][parameter_name] = (
                    f"'Source Data'!$C${row_number}"
                )
        _style_sheet(source, {"A": 14, "B": 36, "C": 18, "D": 16, "E": 72})

        b = refs["Baseline"]
        s = refs["Stress"]
        metrics = workbook.create_sheet("Metrics")
        metrics.append(["Metric", "Formula", "Parameters", "Value", "Unit", "Comment"])
        metric_rows = [
            (
                "FPY",
                "G_fr / N",
                "First_Pass_Good_Units, Actual_Output",
                f"={b['First_Pass_Good_Units']}/{b['Actual_Output']}",
                "dimensionless",
                "First-pass yield; not Final Yield",
            ),
            (
                "Final Yield",
                "G_final / N",
                "Final_Good_Units, Actual_Output",
                f"={b['Final_Good_Units']}/{b['Actual_Output']}",
                "dimensionless",
                "Final good output after rework",
            ),
            (
                "Availability",
                "Actual_Hours / Planned_Hours",
                "Actual_Hours, Planned_Hours",
                f"={b['Actual_Hours']}/{b['Planned_Hours']}",
                "dimensionless",
                "OEE availability factor",
            ),
            (
                "Performance",
                "(Planned_Hours / Target_Output) * Actual_Output / Actual_Hours",
                "Planned_Hours, Target_Output, Actual_Output, Actual_Hours",
                f"=({b['Planned_Hours']}/{b['Target_Output']})*{b['Actual_Output']}/{b['Actual_Hours']}",
                "dimensionless",
                "Normative cycle time is derived as h/L",
            ),
            ("Quality", "Quality = FPY", "FPY", "=D2", "dimensionless", "Lecture definition"),
            (
                "OEE",
                "Availability * Performance * Quality",
                "Availability, Performance, Quality",
                "=D4*D5*D6",
                "dimensionless",
                "Operational equipment effectiveness",
            ),
            (
                "Utilization",
                "Planned_Hours / Calendar_Hours",
                "Planned_Hours, Calendar_Hours",
                f"={b['Planned_Hours']}/{b['Calendar_Hours']}",
                "dimensionless",
                "Calendar-time utilization",
            ),
            ("TEEP", "OEE * Utilization", "OEE, Utilization", "=D7*D8", "dimensionless", "CAPEX utilization view"),
            (
                "Energy Intensity",
                "Energy_kWh / Final_Good_Units",
                "Energy_kWh, Final_Good_Units",
                f"={b['Energy_kWh']}/{b['Final_Good_Units']}",
                "kWh/L",
                "Gate-to-gate energy use per final good liter",
            ),
            ("Economic Intensity", "Total Cost / Final Good Units", "Costs!D4, Final_Good_Units", "='Costs'!D5", "USD/L", "Numerically equals CPU for this scope"),
            ("CPU", "Total Cost / Final Good Units", "Costs!D4, Final_Good_Units", "='Costs'!D6", "USD/L", "Cost per final good liter"),
            ("Mass Intensity", "Raw material mass / Final Good Units", "Raw_Material_Mass_kg", "NOT_COMPUTABLE", "kg/L", "Raw_Material_Mass_kg is absent from source data"),
            ("TTM Penalty Assignment", "Multiplicative retained-value loss", "TTM!B2:F2", "='TTM'!G2", "dimensionless", "r=10%, alpha=15%, T=3"),
            ("TTM Penalty CSV", "Multiplicative retained-value loss", "TTM!B3:F3", "='TTM'!G3", "dimensionless", "CSV rates retained separately"),
        ]
        for row in metric_rows:
            metrics.append(row)
            if isinstance(row[3], str) and row[3].startswith("="):
                LOGGER.info("EXCEL_FORMULA_WRITTEN metric=%s", row[0])
        for row in range(2, metrics.max_row + 1):
            if metrics.cell(row, 3).value == "dimensionless":
                metrics.cell(row, 4).number_format = "0.0000%"
        _style_sheet(metrics, {"A": 28, "B": 48, "C": 58, "D": 20, "E": 18, "F": 58})

        costs = workbook.create_sheet("Costs")
        costs.append(["Metric", "Formula", "Parameters", "Value", "Unit", "Comment"])
        cost_rows = [
            ("Energy Cost", "Energy_kWh * Energy_Cost_Rate", "Energy_kWh, Energy_Cost_Rate", f"={b['Energy_kWh']}*{b['Energy_Cost_Rate']}", "USD/month", "Purchased electricity"),
            ("Monthly Depreciation", "CAPEX / Economic Life / 12", "Equipment_CAPEX, Amortization_Years_Economic", f"={b['Equipment_CAPEX']}/{b['Amortization_Years_Economic']}/12", "USD/month", "30-day dataset is treated as one month"),
            ("Total Manufacturing Cost", "Raw materials + Energy + Overhead + Depreciation", "Source Data, D2, D3", f"={b['Raw_Material_Cost']}+D2+{b['OPEX_Overhead']}+D3", "USD/month", "Transparent cost build-up"),
            ("Economic Intensity", "Total Cost / Final Good Units", "D4, Final_Good_Units", f"=D4/{b['Final_Good_Units']}", "USD/L", "Full economic resource intensity"),
            ("CPU", "Total Cost / Final Good Units", "D4, Final_Good_Units", f"=D4/{b['Final_Good_Units']}", "USD/L", "Cost per unit"),
            ("Raw Material Cost Proxy", "Raw Material Cost / Final Good Units", "Raw_Material_Cost, Final_Good_Units", f"={b['Raw_Material_Cost']}/{b['Final_Good_Units']}", "USD/L", "Cost proxy; not mass intensity"),
        ]
        for row in cost_rows:
            costs.append(row)
            LOGGER.info("EXCEL_FORMULA_WRITTEN metric=%s", row[0])
        _style_sheet(costs, {"A": 30, "B": 50, "C": 52, "D": 20, "E": 18, "F": 58})

        ttm = workbook.create_sheet("TTM")
        ttm.append(["Scenario", "Discount Rate", "Price Erosion", "Market Horizon", "Delay", "Window Open", "Penalty", "Comment"])
        ttm.append(["Assignment", 0.10, 0.15, 3.0, baseline.delay_years, baseline.market_window_open, _ttm_formula(2), "Task parameters"])
        ttm.append(["CSV", baseline.discount_rate, baseline.price_erosion_rate, baseline.market_horizon, baseline.delay_years, baseline.market_window_open, _ttm_formula(3), "CSV parameters"])
        for row in (2, 3):
            LOGGER.info("EXCEL_FORMULA_WRITTEN metric=TTM row=%s", row)
            for col in (2, 3, 7):
                ttm.cell(row, col).number_format = "0.0000%"
        _style_sheet(ttm, {"A": 18, "B": 18, "C": 18, "D": 18, "E": 14, "F": 16, "G": 18, "H": 36})

        stress_sheet = workbook.create_sheet("Stress Test")
        stress_sheet.append(["Metric", "Baseline", "Stress", "Absolute Change", "Relative Change", "Interpretation"])
        baseline_cost = f"({b['Raw_Material_Cost']}+{b['Energy_kWh']}*{b['Energy_Cost_Rate']}+{b['OPEX_Overhead']}+{b['Equipment_CAPEX']}/{b['Amortization_Years_Economic']}/12)"
        stress_cost = f"({s['Raw_Material_Cost']}+{s['Energy_kWh']}*{s['Energy_Cost_Rate']}+{s['OPEX_Overhead']}+{s['Equipment_CAPEX']}/{s['Amortization_Years_Economic']}/12)"
        stress_rows = [
            ("FPY", f"={b['First_Pass_Good_Units']}/{b['Actual_Output']}", f"={s['First_Pass_Good_Units']}/{s['Actual_Output']}", "First-pass quality falls"),
            ("OEE", f"=({b['Actual_Hours']}/{b['Planned_Hours']})*(({b['Planned_Hours']}/{b['Target_Output']})*{b['Actual_Output']}/{b['Actual_Hours']})*({b['First_Pass_Good_Units']}/{b['Actual_Output']})", f"=({s['Actual_Hours']}/{s['Planned_Hours']})*(({s['Planned_Hours']}/{s['Target_Output']})*{s['Actual_Output']}/{s['Actual_Hours']})*({s['First_Pass_Good_Units']}/{s['Actual_Output']})", "Quality reduces equipment effectiveness"),
            ("TEEP", "=B3*('Source Data'!$C$3/'Source Data'!$C$2)", "=C3*('Source Data'!$C$21/'Source Data'!$C$20)", "Calendar utilization is unchanged"),
            ("Energy Cost", f"={b['Energy_kWh']}*{b['Energy_Cost_Rate']}", f"={s['Energy_kWh']}*{s['Energy_Cost_Rate']}", "Threefold tariff raises energy cost"),
            ("Economic Intensity", f"={baseline_cost}/{b['Final_Good_Units']}", f"={stress_cost}/{s['Final_Good_Units']}", "Higher energy cost raises cost per good liter"),
            ("CPU", "=B6", "=C6", "Same scoped numerator and denominator as economic intensity"),
        ]
        for metric_name, baseline_formula, stress_formula, interpretation in stress_rows:
            row_number = stress_sheet.max_row + 1
            stress_sheet.append([metric_name, baseline_formula, stress_formula, f"=C{row_number}-B{row_number}", f'=IF(B{row_number}=0,NA(),D{row_number}/ABS(B{row_number}))', interpretation])
            LOGGER.info("EXCEL_FORMULA_WRITTEN stress_metric=%s", metric_name)
        _style_sheet(stress_sheet, {"A": 26, "B": 20, "C": 20, "D": 20, "E": 20, "F": 62})

        harness = workbook.create_sheet("Harness Log")
        harness.append(["Metric", "Excel Value", "Python Value", "Absolute Delta", "Relative Delta", "Tolerance", "Status", "Probable Cause", "Timestamp"])
        _style_sheet(harness, {"A": 28, "B": 18, "C": 18, "D": 18, "E": 18, "F": 14, "G": 18, "H": 54, "I": 26})

        opex = workbook.create_sheet("OPEX")
        opex.append(["Category", "Share"])
        for category, share in (
            ("Сырье и прекурсоры", 0.25),
            ("Утилиты", 0.20),
            ("Персонал", 0.30),
            ("ТОиР", 0.15),
            ("Compliance / качество / метрология", 0.10),
        ):
            opex.append([category, share])
        chart = BarChart()
        chart.title = "Структура OPEX в High-Tech производстве"
        chart.y_axis.title = "Доля"
        chart.x_axis.title = "Категория"
        chart.add_data(Reference(opex, min_col=2, min_row=1, max_row=6), titles_from_data=True)
        chart.set_categories(Reference(opex, min_col=1, min_row=2, max_row=6))
        opex.add_chart(chart, "D2")
        if opex_chart_path and Path(opex_chart_path).is_file():
            opex.add_image(Image(str(opex_chart_path)), "D18")
        _style_sheet(opex, {"A": 40, "B": 16})

        assumptions_sheet = workbook.create_sheet("Assumptions")
        assumption_headers = ["ID", "Assumption", "Reason", "Impact", "Source", "Status"]
        assumptions_sheet.append(assumption_headers)
        default_assumptions = [
            {"ID": "A01", "Assumption": "Расчётный период — один месяц", "Reason": "Calendar_Hours = 720 = 30 × 24", "Impact": "Месячная амортизация", "Source": "CSV", "Status": "Принято"},
            {"ID": "A02", "Assumption": "Normative Cycle Time = Planned_Hours / Target_Output", "Reason": "Отдельное поле отсутствует", "Impact": "Performance и OEE", "Source": "Лекция + CSV", "Status": "Принято"},
            {"ID": "A03", "Assumption": "Знаменатель CPU — Final_Good_Units", "Reason": "Это объём после итогового контроля", "Impact": "CPU и intensity", "Source": "Лекция + задание", "Status": "Принято"},
        ]
        for item in assumptions or default_assumptions:
            assumptions_sheet.append([item.get(key, "") for key in assumption_headers])
        _style_sheet(assumptions_sheet, {"A": 10, "B": 52, "C": 48, "D": 30, "E": 24, "F": 16})

        issues_sheet = workbook.create_sheet("Data Issues")
        issue_headers = ["Issue", "Parameter", "Severity", "Effect", "Action"]
        issues_sheet.append(issue_headers)
        default_issues = [
            {"Issue": "Mass input is absent", "Parameter": "Raw_Material_Mass_kg", "Severity": "HIGH", "Effect": "Mass intensity is NOT_COMPUTABLE", "Action": "Add consumed raw-material mass in kg"},
            {"Issue": "TTM rates conflict", "Parameter": "Discount_Rate; Price_Erosion_Rate", "Severity": "MEDIUM", "Effect": "Different TTM penalties", "Action": "Report assignment and CSV scenarios separately"},
            {"Issue": "Pilot delay differs from comparison baseline", "Parameter": "Delay_Years", "Severity": "MEDIUM", "Effect": "Pilot is not the no-delay baseline", "Action": "Use comparison CSV for stress baseline validation"},
        ]
        for item in data_issues or default_issues:
            issues_sheet.append([item.get(key, "") for key in issue_headers])
        _style_sheet(issues_sheet, {"A": 38, "B": 38, "C": 14, "D": 48, "E": 56})

        workbook.save(path)
        return path


@dataclass(frozen=True, slots=True)
class RecalculationResult:
    """Outcome and auditable stage markers for Excel automation."""

    success: bool
    events: tuple[str, ...]
    error: str | None = None


class ExcelRecalculator:
    """Use installed Microsoft Excel as the formula engine."""

    def __init__(self, excel_factory: Callable[[], Any] | None = None) -> None:
        self._excel_factory = excel_factory

    def recalculate(self, path: Path) -> RecalculationResult:
        """Force a full Excel calculation, save caches, and close cleanly."""
        path = Path(path).resolve()
        events: list[str] = ["EXCEL_RECALC_STARTED"]
        LOGGER.info("EXCEL_RECALC_STARTED path=%s", path)
        if self._excel_factory is None:
            return self._recalculate_in_worker(path, events)

        return self._recalculate_direct(path, events)

    def _recalculate_in_worker(
        self, path: Path, events: list[str]
    ) -> RecalculationResult:
        """Isolate Excel's COM lifetime from subsequent workbook reads."""
        worker_path = Path(__file__).with_name("excel_worker.py")
        try:
            completed = subprocess.run(
                [sys.executable, str(worker_path), str(path)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            LOGGER.exception("Excel worker could not run for %s", path)
            return RecalculationResult(False, tuple(events), str(exc))
        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip()
            LOGGER.error("Excel worker failed for %s: %s", path, error)
            return RecalculationResult(False, tuple(events), error)
        events.append("EXCEL_RECALC_COMPLETED")
        LOGGER.info("EXCEL_RECALC_COMPLETED path=%s", path)
        return RecalculationResult(True, tuple(events))

    def _recalculate_direct(
        self, path: Path, events: list[str]
    ) -> RecalculationResult:
        """Run through an injected COM-compatible object for unit testing."""
        excel = None
        workbook = None
        try:
            excel = self._excel_factory()
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(path))
            excel.CalculateFullRebuild()
            workbook.Save()
            workbook.Close(SaveChanges=True)
            workbook = None
            events.append("EXCEL_RECALC_COMPLETED")
            LOGGER.info("EXCEL_RECALC_COMPLETED path=%s", path)
            return RecalculationResult(True, tuple(events))
        except Exception as exc:  # external COM boundary; error is returned and logged
            LOGGER.exception("Excel recalculation failed for %s", path)
            return RecalculationResult(False, tuple(events), str(exc))
        finally:
            if workbook is not None:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:
                    LOGGER.exception("Failed to close Excel workbook after error")
            if excel is not None:
                try:
                    excel.Quit()
                except Exception:
                    LOGGER.exception("Failed to quit Excel after error")


class ExcelGroundTruthReader:
    """Read only values cached by the spreadsheet calculation engine."""

    def read(self, path: Path) -> dict[str, float | None]:
        """Return the ground-truth metric mapping from cached cells."""
        workbook = load_workbook(Path(path), data_only=True, read_only=True)
        values: dict[str, float | None] = {}
        try:
            for metric_name, (sheet_name, cell_address) in GROUND_TRUTH_CELLS.items():
                value = workbook[sheet_name][cell_address].value
                values[metric_name] = float(value) if isinstance(value, (int, float)) else None
                LOGGER.info("EXCEL_VALUE_READ metric=%s value=%s", metric_name, value)
        finally:
            workbook.close()
        return values
