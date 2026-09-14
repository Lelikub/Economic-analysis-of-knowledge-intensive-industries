# EUV Photoresist Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать в `1/app` воспроизводимый Python-pipeline расчёта производственно-экономических метрик EUV-фоторезиста с независимым Excel Ground Truth, harness, стресс-тестами, визуализацией, логами и отчётом.

**Architecture:** CSV загружаются в типизированные доменные объекты, после чего отдельные чистые калькуляторы выполняют Python-расчёты. Независимый Excel-контур записывает формулы на основе исходных данных, пересчитывается Microsoft Excel через COM, а harness сравнивает кэшированные результаты Excel с Python. Оркестратор формирует все выходные файлы и документирует ограничения данных.

**Tech Stack:** Python 3.14, pandas, openpyxl, matplotlib, pywin32, pytest, standard-library dataclasses/logging/csv/pathlib.

**Spec:** `1/data/ARCH.md`

## Global Constraints

- Весь исполняемый проект и его артефакты располагаются внутри `1/app`; входные CSV читаются из `1/data`.
- Промежуточные вычисления не округляются.
- Python-результаты не используются как значения Excel Ground Truth.
- Excel должен содержать реальные формулы и пересчитываться установленным Microsoft Excel; невозможность пересчёта отражается как ограничение, а не фиктивный PASS.
- Массовая ресурсоёмкость без массы сырья получает статус `NOT_COMPUTABLE`; допускается только явно названный стоимостной proxy.
- Сценарий TTM задания (`0.10/0.15/3`) и сценарий CSV (`0.12/0.18/3`) не смешиваются.
- Нельзя изменять исходные CSV, PDF и пользовательский Markdown-промт.
- Новая бизнес-логика создаётся только после наблюдаемого падения соответствующего теста.

---

### Task 1: Каркас, доменная модель, загрузчик и валидация

**Files:**
- Create: `1/app/requirements.txt`
- Create: `1/app/pytest.ini`
- Create: `1/app/src/euv_analysis/__init__.py`
- Create: `1/app/src/euv_analysis/models.py`
- Create: `1/app/src/euv_analysis/loader.py`
- Create: `1/app/src/euv_analysis/validation.py`
- Create: `1/app/tests/conftest.py`
- Create: `1/app/tests/test_loader_validation.py`

**Interfaces:**
- Produces: `ProductionData`, `ParameterMetadata`, `ValidationIssue`, `ScenarioMode`, `CsvProductionLoader.load(path) -> ProductionData`, `DataValidator.validate(data, mode) -> list[ValidationIssue]`.
- Consumes: CSV schemas from `1/data/euv_photoresist_pilot_2026.csv` and `1/data/euv_photoresist_stress_2026.csv`.

- [x] **Step 1: Add environment and test configuration**

Create `requirements.txt` with pinned-compatible lower bounds:

```text
pandas>=2.3
openpyxl>=3.1
matplotlib>=3.10
pywin32>=311; platform_system == "Windows"
pytest>=8.4
pypdf>=6.0
```

Create `pytest.ini`:

```ini
[pytest]
pythonpath = src
testpaths = tests
addopts = -ra
```

- [x] **Step 2: Install declared dependencies**

Run: `.venv/Scripts/python.exe -m pip install -r 1/app/requirements.txt`

Expected: all dependencies install successfully into the project `.venv`.

- [x] **Step 3: Write failing loader and validation tests**

Cover real CSV loading, missing parameters, NaN, invalid market window, invalid time ranges, excessive first-pass output, negative energy, and negative raw-material cost in normal versus intentional stress mode. Representative assertions:

```python
def test_loader_returns_typed_production_data(data_dir):
    data = CsvProductionLoader().load(data_dir / "euv_photoresist_pilot_2026.csv")
    assert isinstance(data, ProductionData)
    assert data.actual_output == pytest.approx(95.0)
    assert data.units["Actual_Output"] == "L"

@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"planned_hours": 721.0}, "PLANNED_EXCEEDS_CALENDAR"),
        ({"actual_hours": 481.0}, "ACTUAL_EXCEEDS_PLANNED"),
        ({"first_pass_good_units": 96.0}, "FPY_UNITS_EXCEED_OUTPUT"),
        ({"energy_kwh": -1.0}, "NEGATIVE_ENERGY"),
        ({"market_window_open": 2}, "INVALID_MARKET_WINDOW"),
    ],
)
def test_validator_reports_invalid_ranges(valid_data, changes, code):
    issues = DataValidator().validate(replace(valid_data, **changes))
    assert code in {issue.code for issue in issues}
```

- [x] **Step 4: Run tests and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_loader_validation.py -v`

Expected: collection/import failure because `euv_analysis.models`, loader, and validation do not yet exist.

- [x] **Step 5: Implement typed models and loader**

Implement frozen dataclasses with snake_case fields and metadata retained from CSV. The loader must reject duplicate/unknown/missing required parameters and non-finite values with descriptive exceptions. Pandas is restricted to I/O conversion.

- [x] **Step 6: Implement validation modes**

Implement `ScenarioMode.NORMAL` and `ScenarioMode.INTENTIONAL_STRESS`. Negative raw-material cost is an error in normal mode and a warning with category `INTENTIONAL_STRESS_CONDITION` in stress mode; structural and physical impossibilities remain errors.

- [x] **Step 7: Run tests and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_loader_validation.py -v`

Expected: all loader/validation tests PASS without warnings.

- [x] **Step 8: Commit**

```text
git add 1/app/requirements.txt 1/app/pytest.ini 1/app/src/euv_analysis 1/app/tests
git commit -m "feat: add typed production data validation"
```

---

### Task 2: Операционные метрики, затраты, ресурсоёмкость и TTM

**Files:**
- Modify: `1/app/src/euv_analysis/models.py`
- Create: `1/app/src/euv_analysis/metrics.py`
- Create: `1/app/src/euv_analysis/ttm.py`
- Create: `1/app/tests/test_metrics.py`
- Create: `1/app/tests/test_ttm.py`

**Interfaces:**
- Consumes: `ProductionData` from Task 1.
- Produces: `MetricStatus`, `MetricValue`, `MetricsResult`, `OperationalMetricsCalculator.calculate(data) -> MetricsResult`, `TTMCalculator.calculate(delay_years, discount_rate, price_erosion_rate, market_horizon, market_window_open) -> float`.

- [x] **Step 1: Write failing operational and cost tests**

Tests must derive expected values from formula inputs, cover perfect factory and full scrap, and assert `NOT_COMPUTABLE` instead of infinity when final good output is zero:

```python
def test_baseline_operational_metrics(valid_data):
    result = OperationalMetricsCalculator().calculate(valid_data)
    normative_cycle = valid_data.planned_hours / valid_data.target_output
    assert result.fpy.value == pytest.approx(71.25 / 95.0)
    assert result.final_yield.value == pytest.approx(80.75 / 95.0)
    assert result.performance.value == pytest.approx(normative_cycle * 95.0 / 390.0)
    assert result.oee.value == pytest.approx(result.availability.value * result.performance.value * result.quality.value)

def test_full_scrap_is_controlled(valid_data):
    data = replace(valid_data, first_pass_good_units=0.0, final_good_units=0.0)
    result = OperationalMetricsCalculator().calculate(data)
    assert result.fpy.value == 0.0
    assert result.oee.value == 0.0
    assert result.cpu.status is MetricStatus.NOT_COMPUTABLE
```

- [x] **Step 2: Run metrics tests and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_metrics.py -v`

Expected: import failure for missing `euv_analysis.metrics`.

- [x] **Step 3: Implement minimal metric calculators**

Implement formulas and dimensional labels from the spec. Ensure mass intensity is explicitly not computable, `raw_material_cost_per_good_liter_proxy` is separate, and zero denominators use a controlled result status.

- [x] **Step 4: Run metrics tests and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_metrics.py -v`

Expected: all operational, cost, resource-intensity, perfect-factory, full-scrap, and subsidy tests PASS.

- [x] **Step 5: Write failing TTM boundary tests**

```python
def test_ttm_zero_delay_has_zero_penalty():
    assert TTMCalculator().calculate(0.0, 0.10, 0.15, 3.0, 1) == pytest.approx(0.0)

@pytest.mark.parametrize("delay", [3.0, 3.5])
def test_ttm_at_or_after_horizon_is_total_loss(delay):
    assert TTMCalculator().calculate(delay, 0.10, 0.15, 3.0, 1) == pytest.approx(1.0)

def test_ttm_matches_lecture_scenario():
    expected = 1 - (1 / (1.10 ** 0.5)) * math.exp(-0.15 * 0.5) * (2.5 / 3.0)
    assert TTMCalculator().calculate(0.5, 0.10, 0.15, 3.0, 1) == pytest.approx(expected)
```

Also test `T <= 0`, `r <= -1`, negative delay, closed window, and invalid window.

- [x] **Step 6: Run TTM tests and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_ttm.py -v`

Expected: import failure for missing `euv_analysis.ttm`.

- [x] **Step 7: Implement TTM calculator and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_ttm.py -v`

Expected: all TTM tests PASS.

- [x] **Step 8: Commit**

```text
git add 1/app/src/euv_analysis/models.py 1/app/src/euv_analysis/metrics.py 1/app/src/euv_analysis/ttm.py 1/app/tests
git commit -m "feat: calculate production metrics and TTM"
```

---

### Task 3: Независимая Excel-модель и реальный пересчёт

**Files:**
- Create: `1/app/src/euv_analysis/excel.py`
- Create: `1/app/src/euv_analysis/excel_worker.py`
- Create: `1/app/tests/test_excel.py`

**Interfaces:**
- Consumes: baseline/stress `ProductionData`, assumptions, data issues, and output paths.
- Produces: `ExcelGroundTruthBuilder.build(...) -> Path`, `ExcelRecalculator.recalculate(path) -> RecalculationResult`, `ExcelGroundTruthReader.read(path) -> dict[str, float | None]`.

- [x] **Step 1: Write failing workbook structure and formula tests**

Create a temporary workbook and assert sheet names, source values, real formulas, and lack of copied Python metric values:

```python
def test_workbook_contains_independent_formulas(tmp_path, valid_data):
    path = ExcelGroundTruthBuilder().build(tmp_path / "ground_truth.xlsx", valid_data, valid_data)
    wb = load_workbook(path, data_only=False)
    assert {"Source Data", "Metrics", "Costs", "TTM", "Harness Log", "Stress Test", "OPEX", "Assumptions", "Data Issues"} <= set(wb.sheetnames)
    formulas = [cell.value for row in wb["Metrics"].iter_rows() for cell in row if cell.data_type == "f"]
    assert formulas
    assert any("'Source Data'!" in formula for formula in formulas)
```

- [x] **Step 2: Run formula test and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_excel.py::test_workbook_contains_independent_formulas -v`

Expected: import failure for missing `euv_analysis.excel`.

- [x] **Step 3: Implement workbook builder**

Write named source rows, formulas for baseline metrics/costs/TTM, stress formulas, comments, units, number formats, assumptions and data issues. Set workbook calculation mode to automatic and insert OPEX chart when the PNG exists.

- [x] **Step 4: Verify workbook formula test GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_excel.py::test_workbook_contains_independent_formulas -v`

Expected: PASS.

- [x] **Step 5: Write failing recalculation contract tests**

Use a fake COM adapter for unit behavior and a Windows integration marker for installed Excel. Assert ordered events and clear failure state rather than fake values.

- [x] **Step 6: Implement Excel COM recalculation and cached-value reader**

Use `win32com.client.DispatchEx("Excel.Application")`, disable alerts, open the absolute workbook path, force full calculation, save, close, and always quit Excel in `finally`. Read values separately via `openpyxl.load_workbook(..., data_only=True)`.

- [x] **Step 7: Run Excel tests and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_excel.py -v`

Expected: unit tests PASS; installed-Excel integration test PASS on this Windows environment.

- [x] **Step 8: Commit**

```text
git add 1/app/src/euv_analysis/excel.py 1/app/tests/test_excel.py
git commit -m "feat: add independent Excel ground truth"
```

---

### Task 4: Harness, comparison CSV, stress analysis and OPEX chart

**Files:**
- Create: `1/app/src/euv_analysis/harness.py`
- Create: `1/app/src/euv_analysis/stress.py`
- Create: `1/app/src/euv_analysis/visualization.py`
- Create: `1/app/tests/test_harness_stress_visualization.py`

**Interfaces:**
- Consumes: Python metrics, Excel values, baseline/stress data, comparison CSV.
- Produces: `HarnessEntry`, `MetricsHarness.compare(...)`, `StressAnalyzer.compare(...)`, `ComparisonCsvValidator.validate(...)`, `OpexVisualizer.create(path) -> Path`.

- [x] **Step 1: Write failing harness tests**

```python
def test_harness_uses_numeric_tolerance():
    rows = MetricsHarness(tolerance=1e-9).compare({"FPY": 0.75}, {"FPY": 0.75 + 1e-10})
    assert rows[0].status == "PASS"
    assert rows[0].absolute_delta == pytest.approx(1e-10)

def test_harness_does_not_pass_missing_excel_value():
    rows = MetricsHarness().compare({"FPY": None}, {"FPY": 0.75})
    assert rows[0].status == "NOT_COMPUTABLE"
```

- [x] **Step 2: Run harness tests and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_harness_stress_visualization.py -v`

Expected: import failure for missing harness/stress/visualization modules.

- [x] **Step 3: Add comparison and stress tests**

Load the real comparison CSV and assert numerical validation of `0.22 → 0.66`, `71.25/95 → 38/95`, and `0 → 0.5`. Assert output rows for FPY, OEE, TEEP, Energy Cost, Economic Intensity, CPU, and both TTM scenarios.

- [x] **Step 4: Add OPEX chart test**

Assert percentages sum to 100, the generated PNG exists, and its size is nonzero.

- [x] **Step 5: Implement harness, comparison, stress and visualization**

Use dataclasses for exported rows. Relative delta is `None` when the reference is zero. Interpretations are derived from sign/direction and metric semantics, not hardcoded final numeric results.

- [x] **Step 6: Run tests and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_harness_stress_visualization.py -v`

Expected: all tests PASS.

- [x] **Step 7: Commit**

```text
git add 1/app/src/euv_analysis/harness.py 1/app/src/euv_analysis/stress.py 1/app/src/euv_analysis/visualization.py 1/app/tests/test_harness_stress_visualization.py
git commit -m "feat: add harness stress analysis and OPEX chart"
```

---

### Task 5: Логирование, отчёт и единая точка запуска

**Files:**
- Create: `1/app/src/euv_analysis/logging_config.py`
- Create: `1/app/src/euv_analysis/reporting.py`
- Create: `1/app/src/euv_analysis/pipeline.py`
- Create: `1/app/main.py`
- Create: `1/app/tests/test_pipeline.py`

**Interfaces:**
- Consumes: all components from Tasks 1–4 and project paths.
- Produces: `configure_logging`, `ReportBuilder.build`, `AnalysisPipeline.run() -> PipelineResult`, command `python main.py`.

- [ ] **Step 1: Write failing integration test**

Run the pipeline in a temporary output root while reading real `1/data` inputs. Assert required files and semantic content:

```python
def test_pipeline_creates_required_artifacts(tmp_path, project_data_dir):
    result = AnalysisPipeline(data_dir=project_data_dir, work_dir=tmp_path).run()
    required = {
        "ground_truth.xlsx", "harness_log.csv", "stress_comparison.csv",
        "opex_structure.png", "report.md",
    }
    assert required <= {path.name for path in result.output_files}
    assert (tmp_path / "logs" / "execution.log").exists()
    assert "Data Quality Report" in (tmp_path / "output" / "report.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run integration test and verify RED**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_pipeline.py -v`

Expected: import failure for missing `euv_analysis.pipeline`.

- [ ] **Step 3: Implement structured logging and report builder**

Add console/file handlers, stable stage fields, UTF-8 file output, assumptions and issues tables, formulas with dimensions, Python/Excel results, harness, boundary-test summary, stress comparison, TTM interpretation, OPEX image reference, and completion checklist.

- [ ] **Step 4: Implement pipeline orchestration and CLI**

Resolve paths relative to `main.py`, not the current shell. Sequence load → validate → Python metrics → OPEX → Excel formulas → Excel recalc → Excel values → harness → stress → exports → report. Return nonzero on an unhandled failure and log exception context.

- [ ] **Step 5: Run integration test and verify GREEN**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests/test_pipeline.py -v`

Expected: PASS with actual Excel recalc available; if COM is unavailable, integration result must explicitly carry the limitation and harness cannot report false PASS.

- [ ] **Step 6: Commit**

```text
git add 1/app/src/euv_analysis/logging_config.py 1/app/src/euv_analysis/reporting.py 1/app/src/euv_analysis/pipeline.py 1/app/main.py 1/app/tests/test_pipeline.py
git commit -m "feat: orchestrate EUV analysis pipeline"
```

---

### Task 6: Документация, полный запуск и проверка артефактов

**Files:**
- Create: `1/app/README.md`
- Modify: `1/data/ARCH.md`
- Generate: `1/app/output/ground_truth.xlsx`
- Generate: `1/app/output/harness_log.csv`
- Generate: `1/app/output/stress_comparison.csv`
- Generate: `1/app/output/opex_structure.png`
- Generate: `1/app/output/report.md`
- Generate: `1/app/logs/execution.log`

**Interfaces:**
- Consumes: finished pipeline.
- Produces: reproducible usage documentation and verified final artifacts.

- [ ] **Step 1: Write README**

Document environment setup, exact launch command, test command, output files, Excel dependency, formula provenance, `NOT_COMPUTABLE` policy and known data gaps.

- [ ] **Step 2: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest 1/app/tests -v`

Expected: all tests PASS with no unexpected warnings.

- [ ] **Step 3: Run production pipeline**

Run from `1/app`: `..\..\.venv\Scripts\python.exe main.py`

Expected: exit code 0; console and file logs show every pipeline stage, Excel formula write/recalc/read events, harness result, stress result, chart creation and report creation.

- [ ] **Step 4: Verify final artifacts programmatically**

Check existence and nonzero size of all required files; open workbook twice (`data_only=False` and `True`) to confirm formulas and cached results; parse harness CSV to confirm no unexplained `FAIL`; parse report checklist for completion.

- [ ] **Step 5: Reconcile ARCH.md with implementation**

Update module names, file layout, fallback behavior and assumptions if actual implementation differs from the approved design. Do not rewrite historical conclusions to hide limitations.

- [ ] **Step 6: Inspect working tree and commit only task files**

```text
git status --short
git add 1/app 1/data/ARCH.md
git commit -m "feat: complete EUV production analysis"
```

- [ ] **Step 7: Final evidence summary**

Report exact test count, Excel/Python harness status, key baseline/stress figures, data gaps, assumptions, generated file paths and any remaining limitation.
