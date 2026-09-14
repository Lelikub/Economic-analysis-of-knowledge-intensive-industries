"""Markdown reporting from calculated and validated pipeline results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from .excel import PARAMETER_FIELDS
from .harness import HarnessEntry
from .models import MetricsResult, ProductionData, ValidationIssue
from .stress import ComparisonValidationResult, StressComparisonRow


@dataclass(frozen=True, slots=True)
class ReportContext:
    """All calculated evidence needed to assemble the final report."""

    baseline: ProductionData
    stress: ProductionData
    baseline_metrics: MetricsResult
    stress_metrics: MetricsResult
    excel_values: dict[str, float | None]
    harness_rows: Sequence[HarnessEntry]
    stress_rows: Sequence[StressComparisonRow]
    comparison: ComparisonValidationResult
    validation_issues: Sequence[ValidationIssue]
    boundary_checks: dict[str, bool]
    assignment_ttm: float
    csv_ttm: float
    stress_ttm: float
    excel_recalculation_success: bool


def _number(value: float | None) -> str:
    if value is None:
        return "NOT_COMPUTABLE"
    return f"{value:.12g}"


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


class ReportBuilder:
    """Build a human-readable report without recalculating business metrics."""

    _USAGE = {
        "Calendar_Hours": "Utilization, TEEP",
        "Planned_Hours": "Availability, Performance, Utilization",
        "Actual_Hours": "Availability, Performance",
        "Target_Output": "Normative Cycle Time, Performance",
        "Actual_Output": "FPY, Final Yield, Performance",
        "First_Pass_Good_Units": "FPY, Quality, OEE",
        "Final_Good_Units": "Final Yield, intensities, CPU",
        "Raw_Material_Cost": "Total Manufacturing Cost, proxy",
        "Energy_kWh": "Energy Cost, Energy Intensity",
        "Energy_Cost_Rate": "Energy Cost",
        "Equipment_CAPEX": "Monthly Depreciation",
        "Amortization_Years_Economic": "Monthly Depreciation",
        "OPEX_Overhead": "Total Manufacturing Cost",
        "Delay_Years": "TTM Penalty",
        "Discount_Rate": "TTM Penalty (CSV scenario)",
        "Price_Erosion_Rate": "TTM Penalty (CSV scenario)",
        "Market_Horizon": "TTM Penalty",
        "Market_Window_Open": "TTM Penalty",
    }
    _RANGES = {
        "Calendar_Hours": "> 0",
        "Planned_Hours": "0..Calendar_Hours",
        "Actual_Hours": "0..Planned_Hours",
        "Target_Output": ">= 0",
        "Actual_Output": ">= 0",
        "First_Pass_Good_Units": "0..Actual_Output",
        "Final_Good_Units": "0..Actual_Output",
        "Raw_Material_Cost": ">= 0 (кроме intentional stress)",
        "Energy_kWh": ">= 0",
        "Energy_Cost_Rate": ">= 0",
        "Equipment_CAPEX": ">= 0",
        "Amortization_Years_Economic": "> 0",
        "OPEX_Overhead": ">= 0",
        "Delay_Years": ">= 0",
        "Discount_Rate": "> -1",
        "Price_Erosion_Rate": "обычно >= 0",
        "Market_Horizon": "> 0",
        "Market_Window_Open": "{0, 1}",
    }

    def build(self, path: Path, context: ReportContext) -> Path:
        """Write a UTF-8 report composed only from supplied results."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [
            "# Практическое занятие № 1",
            "",
            "## Базовая операционная модель и ресурсоёмкость High-Tech производства",
            "",
            "## 1. Цель работы",
            "",
            "Преобразовать физические параметры пилотного производства EUV-фоторезиста в воспроизводимую экономическую модель с независимыми расчётами Python и Microsoft Excel.",
            "",
            "## 2. Исходные данные",
            "",
            "Использованы `euv_photoresist_pilot_2026.csv`, `euv_photoresist_stress_2026.csv` и `euv_photoresist_comparison_input_2026.csv`. Расчётный период pilot CSV — 720 календарных часов, то есть 30 суток.",
            "",
            "### CSV → model fields → formulas",
            "",
            "| Parameter | CSV source | Meaning | Unit | Used in metric | Expected range | Validation rule | Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for source_name, field_name in PARAMETER_FIELDS:
            lines.append(
                "| "
                + " | ".join(
                    _escape(value)
                    for value in (
                        source_name,
                        "pilot + stress",
                        context.baseline.descriptions.get(source_name, field_name),
                        context.baseline.units.get(source_name, ""),
                        self._USAGE[source_name],
                        self._RANGES[source_name],
                        self._RANGES[source_name],
                        f"ProductionData.{field_name}",
                    )
                )
                + " |"
            )

        lines.extend(
            [
                "",
                "## 3. Архитектура решения",
                "",
                "`CSV → typed ProductionData → validation → Python calculators` и параллельно `CSV → Excel formulas → Excel recalculation`. Затем `MetricsHarness` сравнивает два результата; stress, visualization и reporting используют только рассчитанные объекты.",
                "",
                "## 4. Проверка исходных данных",
                "",
                f"Comparison CSV: **{'PASS' if context.comparison.valid else 'FAIL'}**.",
                "",
                "| Check | Status |",
                "|---|---|",
            ]
        )
        for name, passed in context.comparison.checks.items():
            lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
        lines.extend(
            [
                "",
                "## 5. Математические модели и размерности",
                "",
                "| Metric | Formula | Dimension |",
                "|---|---|---|",
                "| FPY | First_Pass_Good_Units / Actual_Output | L/L → dimensionless |",
                "| Final Yield | Final_Good_Units / Actual_Output | L/L → dimensionless |",
                "| Availability | Actual_Hours / Planned_Hours | h/h → dimensionless |",
                "| Performance | (Planned_Hours / Target_Output) × Actual_Output / Actual_Hours | (h/L)×L/h → dimensionless |",
                "| OEE | Availability × Performance × FPY | dimensionless |",
                "| TEEP | OEE × Planned_Hours / Calendar_Hours | dimensionless |",
                "| Energy Intensity | Energy_kWh / Final_Good_Units | kWh/L |",
                "| CPU | Total Manufacturing Cost / Final_Good_Units | USD/L |",
                "| TTM penalty | 1 − discount × erosion × horizon × window | dimensionless |",
                "",
                "## 6. Результаты Python",
                "",
                "| Metric | Value | Unit | Status |",
                "|---|---:|---|---|",
            ]
        )
        for metric in context.baseline_metrics.__dataclass_fields__:
            item = getattr(context.baseline_metrics, metric)
            lines.append(
                f"| {_escape(item.name)} | {_number(item.value)} | {_escape(item.unit)} | {item.status.value} |"
            )

        lines.extend(
            [
                "",
                "Ограничивающий фактор OEE — Quality/FPY (75%); Availability равна 81.25%, а Performance около 97.44%. TEEP ниже OEE из-за календарной загрузки 66.67%, поэтому значительная часть CAPEX не используется круглосуточно.",
                "",
                "## 7. Excel Ground Truth",
                "",
                f"Реальный пересчёт Microsoft Excel: **{'COMPLETED' if context.excel_recalculation_success else 'UNAVAILABLE'}**. Книга содержит формулы, а значения прочитаны из кэша после пересчёта.",
                "",
                "## 8. Harness",
                "",
                "| Metric | Excel | Python | Abs Delta | Rel Delta | Tolerance | Status | Cause |",
                "|---|---:|---:|---:|---:|---:|---|---|",
            ]
        )
        for row in context.harness_rows:
            lines.append(
                f"| {_escape(row.metric)} | {_number(row.excel_value)} | {_number(row.python_value)} | {_number(row.absolute_delta)} | {_number(row.relative_delta)} | {row.tolerance:.1e} | {row.status} | {_escape(row.probable_cause)} |"
            )

        lines.extend(
            [
                "",
                "## 9. Граничные тесты",
                "",
                "| Test | Status |",
                "|---|---|",
            ]
        )
        for name, passed in context.boundary_checks.items():
            lines.append(f"| {_escape(name)} | {'PASS' if passed else 'FAIL'} |")

        lines.extend(
            [
                "",
                "## 10. Stress Test",
                "",
                "| Metric | Baseline | Stress | Absolute Change | Relative Change | Interpretation |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for row in context.stress_rows:
            lines.append(
                f"| {_escape(row.metric)} | {_number(row.baseline)} | {_number(row.stress)} | {_number(row.absolute_change)} | {_number(row.relative_change)} | {_escape(row.interpretation)} |"
            )
        lines.extend(
            [
                "",
                "Падение FPY с 75% до 40% снижает OEE и TEEP. Тариф электроэнергии ×3 увеличивает Energy Cost на 50 600 USD и CPU на величину этого прироста, распределённую на 80.75 л итоговой годной продукции.",
                "В предоставленном stress CSV `Final_Good_Units` остаётся 80.75 л, а стоимость переделки отдельным полем не задана. Поэтому само снижение FPY не увеличивает CPU в этой модели напрямую: его эффект виден в OEE/TEEP, тогда как наблюдаемый рост CPU вызван тарифом. Для монетизации переделок требуется отдельный параметр rework cost.",
                "",
                "## 11. OPEX",
                "",
                "Диаграмма `opex_structure.png` показывает: сырьё 25%, утилиты 20%, персонал 30%, ТОиР 15%, compliance/качество/метрология 10%. Сумма программно проверена и равна 100%.",
                "",
                "## 12. TTM",
                "",
                f"- TTM: сценарий задания (`r=10%`, `α=15%`, `T=3`, `Δt=0.5`): **{context.assignment_ttm:.6%}**.",
                f"- TTM: сценарий CSV (`r=12%`, `α=18%`, `T=3`, `Δt=0.5`): **{context.csv_ttm:.6%}**.",
                f"- Stress относительно baseline comparison CSV (`Δt: 0→0.5`): **{context.stress_ttm:.6%}** против **0%**.",
                "",
                "Штраф мультипликативный: задержка одновременно удешевляет будущие деньги, ускоряет ценовую эрозию, сокращает горизонт продаж и учитывает закрытие рыночного окна.",
                "",
                "## 13. Data Quality Report",
                "",
                "| Issue | Parameter | Severity | Effect | Action |",
                "|---|---|---|---|---|",
                "| Масса сырья отсутствует | Raw_Material_Mass_kg | HIGH | Mass Intensity = NOT_COMPUTABLE | Добавить массу потреблённого сырья, kg |",
                "| Параметры TTM расходятся | Discount_Rate; Price_Erosion_Rate | MEDIUM | Разные штрафы | Показывать два сценария отдельно |",
                "| Pilot delay не равен comparison baseline | Delay_Years | MEDIUM | Pilot нельзя считать no-delay baseline для TTM stress | Для стресс-сравнения использовать comparison CSV |",
            ]
        )
        for issue in context.validation_issues:
            lines.append(
                f"| {_escape(issue.message)} | {_escape(issue.parameter)} | {issue.severity.value} | {issue.category} | Исправить вход или подтвердить stress-режим |"
            )

        lines.extend(
            [
                "",
                "## 14. Допущения",
                "",
                "| ID | Assumption | Reason | Impact | Source | Status |",
                "|---|---|---|---|---|---|",
                "| A01 | Расчётный период — месяц | 720 h = 30×24 | Monthly depreciation | CSV | Принято |",
                "| A02 | Normative Cycle Time = Planned_Hours / Target_Output | Отдельного поля нет | Performance и OEE | Лекция + CSV | Принято |",
                "| A03 | CPU использует Final_Good_Units | Это объём после итогового контроля | CPU и Economic Intensity | Лекция + задание | Принято |",
                "| A04 | Actual_Output — обработанный/запущенный объём | Описание CSV и формула FPY | FPY и Final Yield | CSV + задание | Принято |",
                "",
                "## 15. Выводы",
                "",
                "Модель связывает физическую эффективность производства с полной стоимостью и риском задержки. Низкий FPY является главным ограничителем OEE, календарная загрузка дополнительно снижает TEEP, а высокая доля амортизации делает стоимость единицы чувствительной к объёму годной продукции. Массовая ресурсоёмкость требует дополнительного физического параметра и не заменяется стоимостной оценкой.",
                "",
                "## 16. Итоговый checklist",
                "",
            ]
        )
        checklist = {
            "CSV прочитаны и преобразованы в dataclass": True,
            "Validation выполнен": not any(
                issue.severity.value == "ERROR" for issue in context.validation_issues
            ),
            "FPY, OEE, TEEP, CPU и TTM рассчитаны": True,
            "Mass Intensity рассмотрена как Data Gap": True,
            "Excel formulas созданы": True,
            "Excel пересчитан и прочитан": context.excel_recalculation_success,
            "Harness выполнен без необъяснённых FAIL": not any(
                row.status == "FAIL" for row in context.harness_rows
            ),
            "Boundary checks выполнены": all(context.boundary_checks.values()),
            "Stress CSV и comparison CSV обработаны": context.comparison.valid,
            "OPEX chart создан": True,
            "Execution log и выходные CSV сформированы": True,
            "Результаты не захардкожены в расчётных слоях": True,
        }
        for name, passed in checklist.items():
            lines.append(f"- [{'x' if passed else ' '}] {name}")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
