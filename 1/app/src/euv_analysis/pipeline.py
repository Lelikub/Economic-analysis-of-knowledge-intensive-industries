"""End-to-end orchestration for the EUV production analysis."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
import logging
from pathlib import Path
from collections.abc import Sequence

from .excel import ExcelGroundTruthBuilder, ExcelGroundTruthReader, ExcelRecalculator
from .harness import HarnessEntry, MetricsHarness
from .loader import CsvProductionLoader
from .logging_config import configure_logging
from .metrics import OperationalMetricsCalculator
from .models import MetricStatus, ScenarioMode, ValidationSeverity
from .reporting import ReportBuilder, ReportContext
from .stress import (
    ComparisonCsvValidator,
    StressAnalyzer,
    StressComparisonRow,
)
from .ttm import TTMCalculator
from .validation import DataValidator
from .visualization import OpexVisualizer


LOGGER = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """Raised when a required pipeline stage cannot produce valid output."""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Final evidence returned by a successful pipeline run."""

    output_files: tuple[Path, ...]
    harness_rows: tuple[HarnessEntry, ...]
    stress_rows: tuple[StressComparisonRow, ...]
    boundary_checks: dict[str, bool]
    ttm_results: dict[str, float]
    excel_recalculation_success: bool
    comparison_valid: bool


def _log(level: int, stage: str, message: str, *args: object) -> None:
    LOGGER.log(level, message, *args, extra={"stage": stage})


class AnalysisPipeline:
    """Execute every required stage through the Python interpreter."""

    def __init__(self, data_dir: Path, work_dir: Path) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.work_dir = Path(work_dir).resolve()
        self.output_dir = self.work_dir / "output"
        self.log_dir = self.work_dir / "logs"

    def run(self) -> PipelineResult:
        """Run load, validate, calculate, Excel, harness, stress, and report."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        configure_logging(self.log_dir / "execution.log")
        _log(logging.INFO, "startup", "PIPELINE_STARTED work_dir=%s", self.work_dir)

        loader = CsvProductionLoader()
        input_paths = {
            "pilot": self.data_dir / "euv_photoresist_pilot_2026.csv",
            "stress": self.data_dir / "euv_photoresist_stress_2026.csv",
            "comparison": self.data_dir / "euv_photoresist_comparison_input_2026.csv",
        }
        for name, path in input_paths.items():
            _log(logging.INFO, "discovery", "FILE_FOUND type=%s path=%s", name, path)

        baseline = loader.load(input_paths["pilot"])
        _log(logging.INFO, "load", "CSV_READ scenario=pilot rows=18")
        stress = loader.load(input_paths["stress"])
        _log(logging.INFO, "load", "CSV_READ scenario=stress rows=18")
        comparison = ComparisonCsvValidator().validate(input_paths["comparison"])
        _log(
            logging.INFO,
            "load",
            "CSV_READ scenario=comparison checks=%s",
            comparison.checks,
        )
        if not comparison.valid:
            raise PipelineError(
                "Comparison CSV does not match the required stress scenario: "
                + ", ".join(comparison.messages)
            )

        validator = DataValidator()
        baseline_issues = validator.validate(baseline, ScenarioMode.NORMAL)
        stress_issues = validator.validate(stress, ScenarioMode.NORMAL)
        validation_issues = [*baseline_issues, *stress_issues]
        errors = [
            issue
            for issue in validation_issues
            if issue.severity is ValidationSeverity.ERROR
        ]
        _log(
            logging.INFO,
            "validation",
            "VALIDATION_COMPLETED issues=%d errors=%d",
            len(validation_issues),
            len(errors),
        )
        if errors:
            raise PipelineError(
                "Input validation failed: "
                + "; ".join(f"{issue.code}: {issue.message}" for issue in errors)
            )

        metric_calculator = OperationalMetricsCalculator()
        baseline_metrics = metric_calculator.calculate(baseline)
        stress_metrics = metric_calculator.calculate(stress)
        for scenario, result in (
            ("baseline", baseline_metrics),
            ("stress", stress_metrics),
        ):
            _log(
                logging.INFO,
                "python_metrics",
                "PYTHON_METRICS_CALCULATED scenario=%s values=%s",
                scenario,
                result.numeric_values(),
            )

        ttm = TTMCalculator()
        assignment_ttm = ttm.calculate(
            baseline.delay_years, 0.10, 0.15, 3.0, baseline.market_window_open
        )
        csv_ttm = ttm.calculate(
            baseline.delay_years,
            baseline.discount_rate,
            baseline.price_erosion_rate,
            baseline.market_horizon,
            baseline.market_window_open,
        )
        baseline_stress_ttm = ttm.calculate(
            comparison.delay[0], 0.10, 0.15, 3.0, baseline.market_window_open
        )
        stress_ttm = ttm.calculate(
            comparison.delay[1], 0.10, 0.15, 3.0, stress.market_window_open
        )
        _log(
            logging.INFO,
            "ttm",
            "TTM_CALCULATED assignment=%s csv=%s stress=%s",
            assignment_ttm,
            csv_ttm,
            stress_ttm,
        )

        boundary_checks = self._run_boundary_checks(baseline)
        _log(
            logging.INFO,
            "tests",
            "BOUNDARY_TESTS_COMPLETED results=%s",
            boundary_checks,
        )
        if not all(boundary_checks.values()):
            raise PipelineError("One or more programmatic boundary checks failed")

        opex_path = OpexVisualizer().create(
            self.output_dir / "opex_structure.png"
        )
        _log(logging.INFO, "visualization", "OPEX_CHART_CREATED path=%s", opex_path)

        workbook_path = self.output_dir / "ground_truth.xlsx"
        excel_builder = ExcelGroundTruthBuilder()
        excel_builder.build(
            workbook_path,
            baseline,
            stress,
            opex_chart_path=opex_path,
        )
        _log(logging.INFO, "excel", "EXCEL_WORKBOOK_CREATED path=%s", workbook_path)

        recalculator = ExcelRecalculator()
        first_recalculation = recalculator.recalculate(workbook_path)
        if first_recalculation.success:
            excel_values = ExcelGroundTruthReader().read(workbook_path)
        else:
            _log(
                logging.WARNING,
                "excel",
                "EXCEL_RECALC_UNAVAILABLE error=%s",
                first_recalculation.error,
            )
            excel_values = {
                name: None for name in baseline_metrics.numeric_values()
            }
            excel_values.update(
                {"TTM Penalty Assignment": None, "TTM Penalty CSV": None}
            )

        python_values = baseline_metrics.numeric_values()
        python_values.update(
            {
                "TTM Penalty Assignment": assignment_ttm,
                "TTM Penalty CSV": csv_ttm,
            }
        )
        harness_rows = MetricsHarness(tolerance=1e-9).compare(
            excel_values, python_values
        )
        _log(
            logging.INFO,
            "harness",
            "HARNESS_COMPLETED pass=%d fail=%d not_computable=%d",
            sum(row.status == "PASS" for row in harness_rows),
            sum(row.status == "FAIL" for row in harness_rows),
            sum(row.status == "NOT_COMPUTABLE" for row in harness_rows),
        )
        self._write_harness_csv(
            self.output_dir / "harness_log.csv", harness_rows
        )

        excel_builder.write_harness(workbook_path, harness_rows)
        second_recalculation = recalculator.recalculate(workbook_path)
        excel_success = (
            first_recalculation.success and second_recalculation.success
        )
        if not second_recalculation.success:
            _log(
                logging.WARNING,
                "excel",
                "EXCEL_FINAL_RECALC_UNAVAILABLE error=%s",
                second_recalculation.error,
            )

        stress_rows = StressAnalyzer().compare(
            baseline_metrics,
            stress_metrics,
            baseline_ttm=baseline_stress_ttm,
            stress_ttm=stress_ttm,
        )
        self._write_stress_csv(
            self.output_dir / "stress_comparison.csv", stress_rows
        )
        _log(
            logging.INFO,
            "stress",
            "STRESS_TEST_COMPLETED rows=%d",
            len(stress_rows),
        )

        report_path = ReportBuilder().build(
            self.output_dir / "report.md",
            ReportContext(
                baseline=baseline,
                stress=stress,
                baseline_metrics=baseline_metrics,
                stress_metrics=stress_metrics,
                excel_values=excel_values,
                harness_rows=harness_rows,
                stress_rows=stress_rows,
                comparison=comparison,
                validation_issues=validation_issues,
                boundary_checks=boundary_checks,
                assignment_ttm=assignment_ttm,
                csv_ttm=csv_ttm,
                stress_ttm=stress_ttm,
                excel_recalculation_success=excel_success,
            ),
        )
        _log(logging.INFO, "report", "REPORT_CREATED path=%s", report_path)

        output_files = (
            workbook_path,
            self.output_dir / "harness_log.csv",
            self.output_dir / "stress_comparison.csv",
            opex_path,
            report_path,
        )
        missing_outputs = [
            path for path in output_files if not path.is_file() or path.stat().st_size == 0
        ]
        if missing_outputs:
            raise PipelineError(
                "Missing or empty outputs: "
                + ", ".join(str(path) for path in missing_outputs)
            )
        _log(
            logging.INFO,
            "complete",
            "PIPELINE_COMPLETED files=%d excel_success=%s",
            len(output_files),
            excel_success,
        )
        return PipelineResult(
            output_files=output_files,
            harness_rows=tuple(harness_rows),
            stress_rows=tuple(stress_rows),
            boundary_checks=boundary_checks,
            ttm_results={
                "assignment": assignment_ttm,
                "csv": csv_ttm,
                "stress_baseline": baseline_stress_ttm,
                "stress": stress_ttm,
            },
            excel_recalculation_success=excel_success,
            comparison_valid=comparison.valid,
        )

    @staticmethod
    def _run_boundary_checks(baseline):
        calculator = OperationalMetricsCalculator()
        full_scrap = calculator.calculate(
            replace(
                baseline,
                first_pass_good_units=0.0,
                final_good_units=0.0,
            )
        )
        ideal = calculator.calculate(
            replace(
                baseline,
                actual_hours=baseline.planned_hours,
                actual_output=baseline.target_output,
                first_pass_good_units=baseline.target_output,
                final_good_units=baseline.target_output,
            )
        )
        subsidized = calculator.calculate(
            replace(baseline, raw_material_cost=-1_000.0)
        )
        subsidy_issues = DataValidator().validate(
            replace(baseline, raw_material_cost=-1_000.0),
            ScenarioMode.INTENTIONAL_STRESS,
        )
        zero_time = calculator.calculate(
            replace(baseline, planned_hours=0.0, actual_hours=0.0)
        )
        ttm = TTMCalculator()
        return {
            "A_FULL_SCRAP": full_scrap.fpy.value == 0.0
            and full_scrap.oee.value == 0.0
            and full_scrap.cpu.status is MetricStatus.NOT_COMPUTABLE,
            "B_IDEAL_FACTORY": ideal.oee.value == 1.0,
            "C_RAW_MATERIAL_SUBSIDY": subsidized.cpu.value < calculator.calculate(
                baseline
            ).cpu.value
            and any(
                issue.category == "INTENTIONAL_STRESS_CONDITION"
                for issue in subsidy_issues
            ),
            "ZERO_TIME_DENOMINATOR": zero_time.availability.status
            is MetricStatus.NOT_COMPUTABLE,
            "TTM_DELAY_ZERO": ttm.calculate(0.0, 0.10, 0.15, 3.0, 1) == 0.0,
            "TTM_DELAY_AT_HORIZON": ttm.calculate(3.0, 0.10, 0.15, 3.0, 1)
            == 1.0,
            "TTM_DELAY_AFTER_HORIZON": ttm.calculate(3.5, 0.10, 0.15, 3.0, 1)
            == 1.0,
        }

    @staticmethod
    def _write_harness_csv(path: Path, rows: Sequence[HarnessEntry]) -> None:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "Metric",
                    "Excel Value",
                    "Python Value",
                    "Absolute Delta",
                    "Relative Delta",
                    "Tolerance",
                    "Status",
                    "Probable Cause",
                    "Timestamp",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "Metric": row.metric,
                        "Excel Value": row.excel_value,
                        "Python Value": row.python_value,
                        "Absolute Delta": row.absolute_delta,
                        "Relative Delta": row.relative_delta,
                        "Tolerance": row.tolerance,
                        "Status": row.status,
                        "Probable Cause": row.probable_cause,
                        "Timestamp": row.timestamp,
                    }
                )

    @staticmethod
    def _write_stress_csv(
        path: Path, rows: Sequence[StressComparisonRow]
    ) -> None:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "Metric",
                    "Baseline",
                    "Stress",
                    "Absolute Change",
                    "Relative Change",
                    "Interpretation",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "Metric": row.metric,
                        "Baseline": row.baseline,
                        "Stress": row.stress,
                        "Absolute Change": row.absolute_change,
                        "Relative Change": row.relative_change,
                        "Interpretation": row.interpretation,
                    }
                )
