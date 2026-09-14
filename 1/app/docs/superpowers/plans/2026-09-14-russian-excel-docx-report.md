# Russian Excel and DOCX Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Русифицировать весь видимый интерфейс расчётной книги и добавить итоговый DOCX с рассчитанными таблицами, двумя графиками, параметрами и выводами.

**Architecture:** Внутренние ключи расчёта остаются неизменными, а новый модуль локализации преобразует их только на границе представления. Excel продолжает считать независимо формулами, а Markdown и DOCX получают один и тот же `ReportContext`; DOCX не пересчитывает бизнес-метрики.

**Tech Stack:** Python 3.14, pytest, openpyxl, matplotlib, python-docx, Microsoft Excel COM для финального пересчёта XLSX.

**Spec:** `1/app/docs/superpowers/specs/2026-09-14-russian-excel-docx-report-design.md`

## Global Constraints

- Все команды выполнять из `1/app` через `../../.venv/Scripts/python.exe`.
- Внутренние имена метрик, dataclass-поля и заголовки экспортных CSV не изменять.
- Видимый пользователю слой Excel и DOCX должен быть русским; допустимы FPY, OEE, TEEP, TTM, CPU, OPEX, CAPEX, CSV и технические имена в специально обозначенных полях.
- Формулы XLSX должны оставаться настоящими формулами в международном синтаксисе функций Excel.
- DOCX и визуализации используют только рассчитанные объекты, без дублирования формул Python.
- `Mass Intensity = None` отображать как `НЕ РАССЧИТЫВАЕТСЯ`, а не как ноль.
- Выполнять каждый программный шаг по TDD: RED, минимальный GREEN, полный локальный regression.

---

### Task 1: Russian presentation catalog and Excel workbook

**Files:**
- Create: `1/app/src/euv_analysis/localization.py`
- Modify: `1/app/src/euv_analysis/excel.py`
- Modify: `1/app/tests/test_excel.py`

**Interfaces:**
- Produces: `SHEET_NAMES`, `PARAMETER_LABELS`, `PARAMETER_DESCRIPTIONS`, `METRIC_LABELS`, `UNIT_LABELS`, `STATUS_LABELS`, `SCENARIO_LABELS`, `localize_unit(value: str) -> str`, `localize_metric(value: str) -> str`, `localize_status(value: str) -> str`.
- Preserves: `GROUND_TRUTH_CELLS: dict[str, tuple[str, str]]` with English internal metric keys and Russian sheet values.

- [ ] **Step 1: Write failing Excel localization tests**

Add tests that exercise a real workbook:

```python
def test_workbook_uses_russian_sheet_names_headers_and_values(tmp_path, valid_data):
    path = ExcelGroundTruthBuilder().build(tmp_path / "ground_truth.xlsx", valid_data, valid_data)
    workbook = load_workbook(path, data_only=False)
    assert workbook.sheetnames == [
        "Исходные данные", "Метрики", "Затраты", "TTM", "Стресс-тест",
        "Журнал сверки", "Структура OPEX", "Допущения", "Проблемы данных",
    ]
    assert [cell.value for cell in workbook["Исходные данные"][1]] == [
        "Сценарий", "Параметр", "Техническое имя CSV", "Значение",
        "Единица измерения", "Описание",
    ]
    assert workbook["Исходные данные"]["A2"].value == "Базовый"
    assert workbook["Исходные данные"]["B2"].value == "Календарное время"
    assert workbook["Исходные данные"]["C2"].value == "Calendar_Hours"
    assert workbook["Метрики"]["A2"].value == "Выход годных с первого прохода (FPY)"
    assert workbook["Метрики"]["B2"].value == "Годный объём первого прохода / фактический выпуск"
    assert workbook["Метрики"]["F2"].value.startswith("Доля продукции")
    assert workbook["Метрики"]["D13"].value == "НЕ РАССЧИТЫВАЕТСЯ"
```

Update formula assertions to use Russian sheet names and add a harness display test:

```python
def test_harness_rows_are_localized_only_in_workbook(tmp_path, valid_data):
    path = ExcelGroundTruthBuilder().build(tmp_path / "ground_truth.xlsx", valid_data, valid_data)
    entry = HarnessEntry("OEE", 0.5, 0.5, 0.0, 0.0, 1e-9, "PASS", "", "2026-09-14T00:00:00+00:00")
    ExcelGroundTruthBuilder().write_harness(path, [entry])
    workbook = load_workbook(path, data_only=False)
    row = list(workbook["Журнал сверки"].iter_rows(min_row=2, values_only=True))[0]
    assert row[0] == "Общая эффективность оборудования (OEE)"
    assert row[6] == "СОВПАДАЕТ"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_excel.py -k "workbook_uses_russian or harness_rows_are_localized or workbook_contains_independent" -q
```

Expected: failures because current workbook uses `Source Data`, `Metrics`, English headers and raw harness statuses.

- [ ] **Step 3: Implement localization boundary and Russian Excel UI**

Create immutable mappings in `localization.py`, including all 18 parameters and all exported metrics. Implement pure fallbacks:

```python
def localize_unit(value: str) -> str:
    return UNIT_LABELS.get(value, value)

def localize_metric(value: str) -> str:
    return METRIC_LABELS.get(value, value)

def localize_status(value: str) -> str:
    return STATUS_LABELS.get(value, value)
```

In `excel.py`, use Russian sheet names for creation and all cross-sheet references, shift source values to column D because column C stores the original CSV name, translate every heading/formula explanation/comment/interpretation, and update `GROUND_TRUTH_CELLS` sheet values. Keep formulas starting with `=` and keep `IF`, `OR`, `EXP`, `NA`, and `ABS` unchanged. In `write_harness`, localize only the workbook display values.

- [ ] **Step 4: Run Excel unit tests to verify GREEN**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_excel.py -m "not excel" -q
```

Expected: all non-COM Excel tests pass and at least 20 real formula cells remain.

- [ ] **Step 5: Run non-COM regression and commit**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all selected tests pass with zero failures. Commit `localization.py`, `excel.py`, and `test_excel.py` with message `feat: localize Excel workbook in Russian`.

---

### Task 2: Calculated efficiency visualization

**Files:**
- Modify: `1/app/src/euv_analysis/visualization.py`
- Modify: `1/app/tests/test_harness_stress_visualization.py`

**Interfaces:**
- Consumes: `MetricsResult` for baseline and stress scenarios.
- Produces: `EfficiencyComparisonVisualizer.create(path: Path, baseline: MetricsResult, stress: MetricsResult) -> Path`.

- [ ] **Step 1: Write the failing chart test**

```python
def test_efficiency_chart_uses_calculated_metrics(tmp_path, data_dir):
    loader = CsvProductionLoader()
    calculator = OperationalMetricsCalculator()
    baseline = calculator.calculate(loader.load(data_dir / "euv_photoresist_pilot_2026.csv"))
    stress = calculator.calculate(loader.load(data_dir / "euv_photoresist_stress_2026.csv"))
    path = tmp_path / "сравнение_эффективности.png"
    result = EfficiencyComparisonVisualizer().create(path, baseline, stress)
    assert result == path
    assert path.is_file()
    assert path.stat().st_size > 10_000
```

Also strengthen the OPEX test with the literal Russian category list.

- [ ] **Step 2: Run visualization tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_stress_visualization.py -k "chart" -q
```

Expected: import or attribute failure because `EfficiencyComparisonVisualizer` does not exist.

- [ ] **Step 3: Implement the grouped percentage chart**

Add a deterministic matplotlib builder that reads only `baseline.fpy/oee/teep.value` and corresponding stress values, rejects missing values with `ValueError`, plots two series labelled `Базовый сценарий` and `Стрессовый сценарий`, and saves a closed PNG figure. Correct all OPEX strings to Russian, including `Комплаенс, качество и метрология`.

- [ ] **Step 4: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_stress_visualization.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: both commands pass. Commit with message `feat: add Russian efficiency comparison chart`.

---

### Task 3: Word report generated from ReportContext

**Files:**
- Modify: `1/app/requirements.txt`
- Create: `1/app/src/euv_analysis/word_reporting.py`
- Create: `1/app/tests/test_word_reporting.py`

**Interfaces:**
- Consumes: `ReportContext`, `opex_chart_path: Path`, `efficiency_chart_path: Path`.
- Produces: `WordReportBuilder.build(path: Path, context: ReportContext, *, opex_chart_path: Path, efficiency_chart_path: Path) -> Path`.

- [ ] **Step 1: Add and install the document dependency through the interpreter**

Add `python-docx>=1.2` to `requirements.txt`, then run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Expected: `python-docx` imports from the repository virtual environment.

- [ ] **Step 2: Write failing DOCX behavior tests**

Build a real `ReportContext` from the three repository CSV files using `CsvProductionLoader`, `OperationalMetricsCalculator`, `ComparisonCsvValidator`, `StressAnalyzer`, `TTMCalculator`, and `MetricsHarness`. Create both actual PNG files. Then assert the produced document boundary:

```python
document = Document(result)
text = "\n".join(paragraph.text for paragraph in document.paragraphs)
assert result.stat().st_size > 50_000
assert "Итоговый отчёт по экономическому анализу" in text
assert "Результаты расчёта" in text
assert "Стресс-сценарий" in text
assert "26,2859 %" in text
assert "НЕ РАССЧИТЫВАЕТСЯ" in text
assert len(document.tables) >= 6
assert len(document.inline_shapes) == 2
assert any("14 713,04" in cell.text for table in document.tables for row in table.rows for cell in row.cells)
```

Add an error test that passes a missing PNG and expects `FileNotFoundError` naming that path.

- [ ] **Step 3: Run DOCX tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_word_reporting.py -q
```

Expected: import failure because `word_reporting.py` does not exist.

- [ ] **Step 4: Implement the DOCX builder**

Use `python-docx` to set A4 page geometry, Russian default font, heading styles, table grid style, alternating header fill, and two pictures. Implement dedicated presentation helpers for decimal, percentage, currency and missing values. Fill every section listed in the spec directly from `context`; derive narrative comparisons from the supplied values, for example selecting the smallest of FPY/availability/performance as the OEE constraint without recalculating any metric.

Validate both PNG paths before creating the document and save atomically to the requested path after making its parent directory.

- [ ] **Step 5: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_word_reporting.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: document tests and all non-COM tests pass. Commit with message `feat: generate calculated Word report`.

---

### Task 4: Pipeline integration and required artifacts

**Files:**
- Modify: `1/app/src/euv_analysis/pipeline.py`
- Modify: `1/app/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `EfficiencyComparisonVisualizer`, `WordReportBuilder`, existing `ReportContext`.
- Produces: `сравнение_эффективности.png` and `Итоговый_отчет.docx` in `PipelineResult.output_files`; log events `EFFICIENCY_CHART_CREATED` and `WORD_REPORT_CREATED`.

- [ ] **Step 1: Write a failing pipeline test with COM isolated at its boundary**

Patch only the external `ExcelRecalculator.recalculate` operation to return `RecalculationResult(False, ("EXCEL_RECALC_STARTED",), "COM unavailable in unit test")`, run the real pipeline, and assert:

```python
names = {path.name for path in result.output_files}
assert "сравнение_эффективности.png" in names
assert "Итоговый_отчет.docx" in names
document = Document(tmp_path / "output" / "Итоговый_отчет.docx")
assert len(document.inline_shapes) == 2
log = (tmp_path / "logs" / "execution.log").read_text(encoding="utf-8")
assert "EFFICIENCY_CHART_CREATED" in log
assert "WORD_REPORT_CREATED" in log
```

Update the existing real-Excel integration expectations to Russian sheet names and include the two new artifacts.

- [ ] **Step 2: Run pipeline unit test to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_pipeline.py -k "docx" -q
```

Expected: failure because the pipeline does not generate the chart or DOCX.

- [ ] **Step 3: Integrate chart and DOCX generation**

Create the efficiency PNG immediately after the OPEX PNG, build one `ReportContext` after stress analysis, pass it to both `ReportBuilder` and `WordReportBuilder`, log the two new events, and append both paths to `output_files`. Do not instantiate a second calculator inside either report builder.

- [ ] **Step 4: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_pipeline.py -k "docx" -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all selected tests pass. Commit with message `feat: publish Word report from analysis pipeline`.

---

### Task 5: User documentation, architecture and production verification

**Files:**
- Modify: `1/app/README.md`
- Modify: `1/data/ARCH.md`
- Regenerate: `1/app/output/ground_truth.xlsx`
- Regenerate: `1/app/output/opex_structure.png`
- Create: `1/app/output/сравнение_эффективности.png`
- Create: `1/app/output/Итоговый_отчет.docx`
- Regenerate: `1/app/output/report.md`
- Regenerate: `1/app/output/harness_log.csv`
- Regenerate: `1/app/output/stress_comparison.csv`
- Regenerate: `1/app/logs/execution.log`

**Interfaces:**
- Documents: exact interpreter command, output catalog, Excel language behavior, Word contents and COM limitation.
- Verifies: all acceptance criteria from the design spec.

- [ ] **Step 1: Update README and ARCH**

Document the canonical command from `1/app`:

```powershell
& '..\..\.venv\Scripts\python.exe' .\main.py
```

Document the seven required outputs, nine Russian Excel sheets, internal English formula-function requirement, DOCX sections, and shared `ReportContext` data flow. Extend `1/data/ARCH.md` with the architectural conclusion that calculation and presentation remain separate boundaries.

- [ ] **Step 2: Run documentation-adjacent non-COM verification**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: zero failed tests.

- [ ] **Step 3: Run full tests with real Excel access**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -q
```

Expected: all tests, including three marked `excel`, pass; formula caches contain FPY `0.75`, OEE `0.59375`, and CPU approximately `14713.0374957`.

- [ ] **Step 4: Generate production artifacts through the interpreter**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' .\main.py
```

Expected: exit code 0 and `PIPELINE_COMPLETED files=7 excel_success=True` in the log.

- [ ] **Step 5: Inspect artifacts programmatically through the interpreter**

Run a Python verification that opens XLSX with `openpyxl` and DOCX with `python-docx`, asserts the exact nine Russian sheet names, at least 20 formulas, Russian headers, cached core values, seven nonempty output files, at least six Word tables, exactly two inline images, and required calculated texts.

- [ ] **Step 6: Review the acceptance checklist and commit**

Run `git diff --check`, review `git diff --stat` and every changed source/test/doc path, then commit with message `docs: document Russian Excel and Word outputs`. Do not push.

