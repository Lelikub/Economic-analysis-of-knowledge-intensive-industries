# Harness Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать Harness Log как проверяемый журнал проблем разработки, сохранив числовую сверку Excel/Python под отдельным именем и включив оба результата в Excel, Markdown и Word.

**Architecture:** `1/data/harness_log.json` становится единственным структурированным источником исторических записей и загружается в неизменяемые `HarnessLogEntry`. Отдельный построитель создаёт `Harness_Log.xlsx` и добавляет тот же лист в Ground Truth; независимая числовая проверка переезжает из `harness.py` в `reconciliation.py`. Оба набора строк передаются через разные поля `ReportContext`, поэтому журнал реализации и расчётная сверка не смешиваются.

**Tech Stack:** Python 3.14, pytest, openpyxl, python-docx, Microsoft Excel COM.

**Spec:** `1/app/docs/superpowers/specs/2026-09-17-harness-log-design.md`

## Global Constraints

- Все команды выполнять из `1/app` через `../../.venv/Scripts/python.exe`.
- Использовать TDD: каждый новый контракт сначала закрепить падающим тестом, затем реализовать минимальный код и выполнить regression.
- `Harness Log` означает только исторический журнал реализации; числовая проверка называется `Сверка Excel–Python`.
- В журнал включить ровно семь подтверждённых спецификацией проблем, без вымышленных событий и заглушек.
- Формулы Excel, допуск `1e-9` и расчётные результаты не менять.
- `output/Итоговый_отчет_ЭА_EUV_оформленный.docx` принадлежит пользователю: не читать в pipeline, не изменять, не удалять и не добавлять в Git.
- Удалять разрешено только точный устаревший путь `output/harness_log.csv`.
- Не использовать Microsoft Word для генерации DOCX.
- Не выполнять push.

---

### Task 1: Structured Harness Log data and strict loader

**Files:**
- Create: `1/data/harness_log.json`
- Create: `1/app/src/euv_analysis/harness_log.py`
- Create: `1/app/tests/test_harness_log.py`

**Interfaces:**
- Produces: `HarnessLogEntry(number: int, stage: str, task: str, code_fragment: str, issue: str, cause: str, resolution: str, recheck_result: str)`.
- Produces: `HarnessLogDataError(ValueError)`.
- Produces: `HarnessLogLoader.load(path: Path) -> tuple[HarnessLogEntry, ...]`.

- [x] **Step 1: Write failing loader tests**

Create `tests/test_harness_log.py` with real behavior checks:

```python
def test_harness_log_loads_seven_verified_project_issues(data_dir):
    rows = HarnessLogLoader().load(data_dir / "harness_log.json")

    assert [row.number for row in rows] == list(range(1, 8))
    assert [row.stage for row in rows] == [
        "Аудит показателей качества",
        "Аудит параметров TTM",
        "Стресс-сценарий TTM",
        "Аудит ресурсоёмкости",
        "Пересчёт Excel",
        "Жизненный цикл COM",
        "Архитектура контрольных журналов",
    ]
    assert rows[0].recheck_result == "Тест подтверждает FPY 75 %, Final Yield 85 %"
    assert "RPC_E_DISCONNECTED" in rows[5].issue
    assert rows[6].resolution.startswith("Числовая проверка переименована")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([{"number": 1}], "missing fields"),
        ([{"number": 2, **VALID_TEXT_FIELDS}], "sequence"),
        ([{"number": 1, **VALID_TEXT_FIELDS, "extra": "x"}], "unknown fields"),
        ([{"number": 1, **{**VALID_TEXT_FIELDS, "stage": ""}}], "non-empty"),
    ],
)
def test_harness_log_rejects_invalid_schema(tmp_path, payload, message):
    path = tmp_path / "harness.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HarnessLogDataError, match=message):
        HarnessLogLoader().load(path)
```

Use this literal fixture:

```python
VALID_TEXT_FIELDS = {
    "stage": "Этап",
    "task": "Задача",
    "code_fragment": "result = calculate()",
    "issue": "Обнаруженная проблема",
    "cause": "Подтверждённая причина",
    "resolution": "Внесённое исправление",
    "recheck_result": "Повторная проверка пройдена",
}
```

- [x] **Step 2: Run loader tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_log.py -q
```

Expected: collection fails because `euv_analysis.harness_log` does not exist.

- [x] **Step 3: Implement the dataclass, strict loader and seven JSON rows**

Implement exact-key validation and sequential numbering:

```python
@dataclass(frozen=True, slots=True)
class HarnessLogEntry:
    number: int
    stage: str
    task: str
    code_fragment: str
    issue: str
    cause: str
    resolution: str
    recheck_result: str


class HarnessLogLoader:
    def load(self, path: Path) -> tuple[HarnessLogEntry, ...]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise HarnessLogDataError("Harness Log must be a JSON array")
        # Reject missing/unknown keys, non-positive numbers, empty strings,
        # duplicate numbers and any sequence other than 1..N.
```

Populate JSON with these exact record subjects and evidence; every phrase is stored in the corresponding schema field without abbreviation:

| № | Этап | Задача | Фрагмент кода | Ошибка | Причина | Исправление | Повторная проверка |
|---:|---|---|---|---|---|---|---|
| 1 | Аудит показателей качества | Развести FPY и итоговый выход годных | `fpy = first_pass_good_units / actual_output; final_yield = final_good_units / actual_output` | FPY и Final Yield могли быть ошибочно приняты за один показатель | Итоговый годный объём включает продукцию после переделки | Показатели реализованы и раскрыты раздельно | Тест подтверждает FPY 75 %, Final Yield 85 % |
| 2 | Аудит параметров TTM | Сопоставить параметры задания и CSV | `assignment_ttm = ttm.calculate(delay, 0.10, 0.15, 3.0, window)` | В задании `r=10 %`, `α=15 %`, а в CSV `r=12 %`, `α=18 %` | Исходные материалы задают разные сценарии | Оба сценария рассчитаны и раскрыты отдельно | Получены штрафы 26,285941 % и 28,034684 % без подмены параметров |
| 3 | Стресс-сценарий TTM | Выбрать корректную базовую задержку | `baseline_stress_ttm = ttm.calculate(comparison.delay[0], 0.10, 0.15, 3.0, window)` | Pilot CSV содержит задержку 0,5 года, comparison baseline — 0 лет | Pilot и сравнительный baseline имеют разное назначение | Для стресс-сравнения использован baseline comparison CSV | Тест подтверждает изменение штрафа TTM с 0 % до 26,285941 % |
| 4 | Аудит ресурсоёмкости | Проверить вычислимость массовой ресурсоёмкости | `mass_intensity = NOT_COMPUTABLE` | Масса сырья отсутствует, а стоимость не может заменить массу | В CSV нет `Raw_Material_Mass_kg` | Метрика помечена `НЕ РАССЧИТЫВАЕТСЯ`, стоимостной proxy показан отдельно | Excel и Python одинаково фиксируют одно невычислимое значение |
| 5 | Пересчёт Excel | Получить кэшированные результаты формул | `excel.CalculateFullRebuild(); workbook.Save()` | `openpyxl` сохраняет формулы, но не вычисляет их | Библиотека не является движком Excel | Добавлен реальный пересчёт установленным Microsoft Excel | Из кэша прочитаны FPY 0,75, OEE 0,59375 и CPU 14 713,0374957 |
| 6 | Жизненный цикл COM | Исключить сбой освобождения Excel COM | `subprocess.run([sys.executable, excel_worker.py, workbook_path])` | Первый интеграционный подход мог завершаться `RPC_E_DISCONNECTED` | COM-прокси переживали закрытие Excel в долгоживущем процессе | Пересчёт изолирован в короткоживущем worker-процессе | Интеграционный тест завершается без RPC fault и с корректным кэшем |
| 7 | Архитектура контрольных журналов | Развести журнал реализации и числовую сверку | `implementation_log_entries` и `reconciliation_rows` | Числовая сверка была ошибочно названа Harness Log | Два разных типа доказательств использовали одно название | Числовая проверка переименована в «Сверка Excel–Python», Harness Log выделен отдельно | Отчёты содержат два самостоятельных раздела и восемь обязательных артефактов |

- [x] **Step 4: Verify GREEN and non-COM regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_log.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all tests pass.

- [x] **Step 5: Commit the structured journal**

Verify `git diff --check`, stage only JSON, loader and tests, then commit:

```text
feat: add structured implementation Harness Log
```

---

### Task 2: Standalone Harness Log workbook

**Files:**
- Modify: `1/app/src/euv_analysis/harness_log.py`
- Modify: `1/app/tests/test_harness_log.py`

**Interfaces:**
- Consumes: `Sequence[HarnessLogEntry]`.
- Produces: `HarnessLogWorkbookBuilder.build(path: Path, entries: Sequence[HarnessLogEntry]) -> Path`.
- Produces: `HarnessLogWorkbookBuilder.add_sheet(workbook: Workbook, entries: Sequence[HarnessLogEntry], *, title: str = "Harness Log")`.

- [x] **Step 1: Write a failing workbook contract test**

```python
def test_harness_log_workbook_matches_approved_example(tmp_path, data_dir):
    entries = HarnessLogLoader().load(data_dir / "harness_log.json")
    path = HarnessLogWorkbookBuilder().build(tmp_path / "Harness_Log.xlsx", entries)
    workbook = load_workbook(path)
    sheet = workbook["Harness Log"]

    assert [cell.value for cell in sheet[1]] == [
        "№", "Этап", "Запрос к ИИ / задача",
        "Сгенерированный или изменённый фрагмент кода",
        "Обнаруженная ошибка / галлюцинация", "Причина",
        "Как исправлено", "Результат повторной проверки",
    ]
    assert sheet.max_row == 8
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:H8"
    assert [sheet.column_dimensions[column].width for column in "ABCDEFGH"] == [
        6.0, 24.0, 32.0, 40.0, 40.0, 35.0, 42.0, 38.0,
    ]
    assert all(cell.fill.fgColor.rgb == "001F4E78" for cell in sheet[1])
    assert all(cell.alignment.wrap_text for row in sheet.iter_rows() for cell in row)
```

- [x] **Step 2: Run the workbook test to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_log.py -k workbook -q
```

Expected: import or attribute failure because `HarnessLogWorkbookBuilder` is absent.

- [x] **Step 3: Implement reusable sheet creation**

`add_sheet` creates the eight headers in the approved order, appends entry fields without transformation, applies `1F4E78` header fill, white bold font, top alignment and wrapping to all cells, exact widths, filter and freeze panes. `build` creates a new workbook, removes the default sheet, calls `add_sheet`, creates the parent directory and saves the file.

Core row mapping is explicit:

```python
HEADERS = (
    "№", "Этап", "Запрос к ИИ / задача",
    "Сгенерированный или изменённый фрагмент кода",
    "Обнаруженная ошибка / галлюцинация", "Причина",
    "Как исправлено", "Результат повторной проверки",
)

for entry in entries:
    sheet.append((
        entry.number, entry.stage, entry.task, entry.code_fragment,
        entry.issue, entry.cause, entry.resolution, entry.recheck_result,
    ))
sheet.freeze_panes = "A2"
sheet.auto_filter.ref = sheet.dimensions
```

- [x] **Step 4: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_log.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all tests pass.

- [x] **Step 5: Commit the workbook builder**

Verify and commit with message:

```text
feat: build Harness Log workbook
```

---

### Task 3: Rename reconciliation and separate both Excel sheets

**Files:**
- Create: `1/app/src/euv_analysis/reconciliation.py`
- Modify: `1/app/src/euv_analysis/harness.py`
- Modify: `1/app/src/euv_analysis/localization.py`
- Modify: `1/app/src/euv_analysis/excel.py`
- Modify: `1/app/tests/test_harness_stress_visualization.py`
- Modify: `1/app/tests/test_excel.py`

**Interfaces:**
- Produces: `ReconciliationEntry` with the same numeric fields as former `HarnessEntry`.
- Produces: `MetricsReconciler(tolerance: float = 1e-9).compare(excel_values: dict[str, float | None], python_values: dict[str, float | None]) -> list[ReconciliationEntry]`.
- Changes: `ExcelGroundTruthBuilder.build` receives the keyword-only parameter `implementation_log_entries: Sequence[HarnessLogEntry] = ()` in addition to its existing arguments.
- Changes: `ExcelGroundTruthBuilder.write_reconciliation(path: Path, entries: Iterable[ReconciliationEntry]) -> None`.

- [x] **Step 1: Write failing rename and sheet-separation tests**

Update numeric tests to import `MetricsReconciler` from `reconciliation`. In `test_excel.py`, build with loaded Harness Log entries and assert exact sheets:

```python
assert workbook.sheetnames == [
    "Исходные данные", "Метрики", "Затраты", "TTM", "Стресс-тест",
    "Сверка Excel–Python", "Harness Log", "Структура OPEX",
    "Допущения", "Проблемы данных",
]
assert workbook["Harness Log"].max_row == 8
assert [cell.value for cell in workbook["Сверка Excel–Python"][1]][:3] == [
    "Метрика", "Значение Excel", "Значение Python",
]
```

Rename `test_harness_rows_are_localized_only_in_workbook` to `test_reconciliation_rows_are_localized_only_in_workbook` and call `write_reconciliation`.

- [x] **Step 2: Run focused tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_excel.py tests/test_harness_stress_visualization.py -k "reconciliation or workbook" -q
```

Expected: failures because renamed module, classes, methods and sheet names do not exist.

- [x] **Step 3: Move the numeric implementation without changing its algorithm**

Create `reconciliation.py` by renaming only the public types and module docstring. Preserve comparison order, formulas for absolute/relative delta, tolerance behavior, status strings and probable-cause text. During this intermediate task, keep `harness.py` as a compatibility re-export so pipeline and reporting remain runnable until Tasks 4–5 update every consumer:

```python
from .reconciliation import (
    MetricsReconciler as MetricsHarness,
    ReconciliationEntry as HarnessEntry,
)

__all__ = ["HarnessEntry", "MetricsHarness"]
```

The public shapes are:

```python
@dataclass(frozen=True, slots=True)
class ReconciliationEntry:
    metric: str
    excel_value: float | None
    python_value: float | None
    absolute_delta: float | None
    relative_delta: float | None
    tolerance: float
    status: str
    probable_cause: str
    timestamp: str


class MetricsReconciler:
    def compare(
        self,
        excel_values: dict[str, float | None],
        python_values: dict[str, float | None],
    ) -> list[ReconciliationEntry]:
        timestamp = datetime.now(timezone.utc).isoformat()
        entries: list[ReconciliationEntry] = []
        for metric in sorted(set(excel_values) | set(python_values)):
            excel_value = excel_values.get(metric)
            python_value = python_values.get(metric)
            if excel_value is None or python_value is None:
                missing_side = "Excel" if excel_value is None else "Python"
                entries.append(ReconciliationEntry(
                    metric, excel_value, python_value, None, None,
                    self.tolerance, "NOT_COMPUTABLE",
                    f"{missing_side} value is unavailable", timestamp,
                ))
                continue
            absolute_delta = abs(excel_value - python_value)
            relative_delta = absolute_delta / abs(excel_value) if excel_value else None
            passed = absolute_delta <= self.tolerance
            entries.append(ReconciliationEntry(
                metric, excel_value, python_value, absolute_delta, relative_delta,
                self.tolerance, "PASS" if passed else "FAIL",
                "" if passed else "Formula, input, or cached Excel value differs",
                timestamp,
            ))
        return entries
```

- [x] **Step 4: Integrate separate Ground Truth sheets**

Change localization keys to:

```python
"reconciliation": "Сверка Excel–Python",
"harness_log": "Harness Log",
```

`ExcelGroundTruthBuilder.build` creates the reconciliation header sheet and calls `HarnessLogWorkbookBuilder().add_sheet(workbook, implementation_log_entries, title="Harness Log")` for the historical journal. `write_reconciliation` writes only the numeric sheet. Keep `GROUND_TRUTH_CELLS` and all formulas unchanged.

- [x] **Step 5: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_excel.py -m "not excel" -q
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_harness_stress_visualization.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all selected tests pass and at least 20 Excel formulas remain.

- [x] **Step 6: Commit the semantic split**

Verify and commit:

```text
refactor: separate Harness Log from metric reconciliation
```

---

### Task 4: Harness Log in Markdown and landscape Word section

**Files:**
- Modify: `1/app/src/euv_analysis/reporting.py`
- Modify: `1/app/src/euv_analysis/word_reporting.py`
- Modify: `1/app/src/euv_analysis/pipeline.py`
- Modify: `1/app/tests/test_word_reporting.py`
- Modify: `1/app/tests/test_pipeline.py`

**Interfaces:**
- Changes: `ReportContext.implementation_log_entries: Sequence[HarnessLogEntry]`.
- Changes: `ReportContext.reconciliation_rows: Sequence[ReconciliationEntry]` replaces `harness_rows`.
- Changes: `PipelineResult.reconciliation_rows: tuple[ReconciliationEntry, ...]` replaces `harness_rows`.
- Adds: `WordReportBuilder._add_harness_log(document: Document, entries: Sequence[HarnessLogEntry]) -> None`.

- [x] **Step 1: Write failing report tests**

Update the Word fixture to load `harness_log.json`, construct `reconciliation_rows`, and populate both fields. Assert:

```python
document = Document(result)
text = "\n".join(paragraph.text for paragraph in document.paragraphs)
table_text = "\n".join(
    cell.text for table in document.tables for row in table.rows for cell in row.cells
)
assert "Harness Log — журнал реализации" in text
assert "Архитектура контрольных журналов" in table_text
assert "Числовая проверка переименована" in table_text
assert len(document.tables) >= 9
assert any(section.orientation == WD_ORIENT.LANDSCAPE for section in document.sections)
assert document.sections[-1].orientation == WD_ORIENT.PORTRAIT
```

Add a Markdown assertion to the non-COM pipeline test:

```python
markdown = (tmp_path / "output" / "report.md").read_text(encoding="utf-8")
assert "## Harness Log — журнал реализации" in markdown
assert "## Сверка Excel–Python" in markdown
assert "RPC_E_DISCONNECTED" in markdown
```

- [x] **Step 2: Run report tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_word_reporting.py tests/test_pipeline.py -k "Harness or harness or docx" -q
```

Expected: failures because `ReportContext` and report builders do not yet expose the new journal.

- [x] **Step 3: Update ReportContext and Markdown**

Use separate typed fields. Rename the numeric Markdown heading to `Сверка Excel–Python`; add the exact eight-column Harness Log table and rows via `_escape`. Update checklist text to distinguish verified implementation issues from reconciliation failures. Update pipeline imports to `HarnessLogLoader`, `ReconciliationEntry` and `MetricsReconciler`; load `data_dir / "harness_log.json"`, pass entries into Ground Truth, populate both `ReportContext` fields, and return `PipelineResult.reconciliation_rows`. Keep the legacy numeric CSV filename only until Task 5 so this intermediate commit remains operational.

- [x] **Step 4: Add a landscape Word section**

Before the numeric reconciliation section, add heading `Harness Log — журнал реализации`, create a landscape `WD_SECTION.NEW_PAGE`, swap section width and height, add the eight-column table with 8-point font and repeat-header XML (`w:tblHeader`), then add a new portrait section and restore A4 portrait dimensions/margins. Keep the existing two images and every calculated table.

Use explicit section transitions:

```python
landscape = document.add_section(WD_SECTION.NEW_PAGE)
landscape.orientation = WD_ORIENT.LANDSCAPE
landscape.page_width, landscape.page_height = Cm(29.7), Cm(21)
self._add_harness_log_table(document, context.implementation_log_entries)
portrait = document.add_section(WD_SECTION.NEW_PAGE)
portrait.orientation = WD_ORIENT.PORTRAIT
portrait.page_width, portrait.page_height = Cm(21), Cm(29.7)
```

- [x] **Step 5: Verify GREEN and regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_word_reporting.py -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: all tests pass; Word has at least nine tables, a landscape section and two images.

- [x] **Step 6: Commit report integration**

Verify and commit:

```text
feat: add implementation Harness Log to reports
```

---

### Task 5: Pipeline outputs, migration and protected user file

**Files:**
- Modify: `1/app/src/euv_analysis/pipeline.py`
- Delete: `1/app/src/euv_analysis/harness.py`
- Modify: `1/app/tests/test_pipeline.py`
- Modify: `1/app/tests/test_excel.py`

**Interfaces:**
- Consumes: `PipelineResult.reconciliation_rows` and loaded `HarnessLogEntry` established in Task 4.
- Produces: `output/Harness_Log.xlsx`.
- Produces: `output/excel_python_reconciliation.csv`.
- Logs: `HARNESS_LOG_LOADED`, `HARNESS_LOG_CREATED`, `RECONCILIATION_COMPLETED`, `LEGACY_HARNESS_CSV_REMOVED` when applicable.

- [x] **Step 1: Write failing end-to-end artifact and preservation tests**

In the non-COM pipeline test, create a protected sentinel before running:

```python
output = tmp_path / "output"
output.mkdir()
protected = output / "Итоговый_отчет_ЭА_EUV_оформленный.docx"
protected.write_bytes(b"user-owned-report")
(output / "harness_log.csv").write_text("legacy", encoding="utf-8")

result = AnalysisPipeline(data_dir=data_dir, work_dir=tmp_path).run()

assert protected.read_bytes() == b"user-owned-report"
assert not (output / "harness_log.csv").exists()
assert {path.name for path in result.output_files} >= {
    "ground_truth.xlsx", "Harness_Log.xlsx",
    "excel_python_reconciliation.csv", "stress_comparison.csv",
    "opex_structure.png", "сравнение_эффективности.png",
    "report.md", "Итоговый_отчет.docx",
}
```

Open `Harness_Log.xlsx`, assert seven data rows, and assert `result.reconciliation_rows` has 17 `PASS`, zero `FAIL`, one `NOT_COMPUTABLE` in the real-Excel test.

- [x] **Step 2: Run pipeline tests to verify RED**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_pipeline.py -k "docx" -q
```

Expected: missing `Harness_Log.xlsx`, old output name and old `PipelineResult` field cause failures.

- [x] **Step 3: Integrate loader, builders and renamed reconciliation**

Using the entries and reconciler already wired in Task 4, create standalone `Harness_Log.xlsx`, write `excel_python_reconciliation.csv`, call `write_reconciliation`, and update `output_files` to the exact eight required artifacts. Remove the temporary `harness.py` compatibility re-export only after `rg` confirms that source and tests contain no imports from `euv_analysis.harness` or `.harness`.

- [x] **Step 4: Implement exact legacy cleanup**

Before writing new outputs:

```python
legacy_harness_csv = self.output_dir / "harness_log.csv"
if legacy_harness_csv.is_file():
    legacy_harness_csv.unlink()
    _log(logging.INFO, "migration", "LEGACY_HARNESS_CSV_REMOVED path=%s", legacy_harness_csv)
```

Do not enumerate or remove any other file. Rename `_write_harness_csv` to `_write_reconciliation_csv` and change its output filename only; keep CSV columns and UTF-8 BOM unchanged.

- [x] **Step 5: Verify GREEN and full non-COM regression**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest tests/test_pipeline.py -k "docx" -q
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q
```

Expected: tests pass and protected sentinel bytes remain unchanged.

- [x] **Step 6: Commit pipeline integration**

Verify and commit:

```text
feat: publish Harness Log as required artifact
```

---

### Task 6: Documentation, production regeneration and final verification

**Files:**
- Modify: `1/app/README.md`
- Modify: `1/data/ARCH.md`
- Delete: `1/app/output/harness_log.csv`
- Regenerate: `1/app/output/ground_truth.xlsx`
- Create: `1/app/output/Harness_Log.xlsx`
- Create: `1/app/output/excel_python_reconciliation.csv`
- Regenerate: `1/app/output/report.md`
- Regenerate: `1/app/output/Итоговый_отчет.docx`
- Regenerate: `1/app/logs/execution.log`
- Preserve untracked: `1/app/output/Итоговый_отчет_ЭА_EUV_оформленный.docx`

**Interfaces:**
- Documents: distinction between Harness Log, reconciliation and execution log.
- Verifies: all acceptance criteria in the spec and unchanged user-owned file metadata.

- [ ] **Step 1: Update README and ARCH**

README lists eight required outputs and explains:

```text
Harness_Log.xlsx — журнал проблем реализации, причин, исправлений и повторных проверок.
excel_python_reconciliation.csv — независимая числовая сверка Excel/Python.
execution.log — техническая хронология текущего запуска.
```

ARCH adds `harness_log.py`, `reconciliation.py`, JSON data flow, separate report fields, landscape Word section and the architectural conclusion that historical audit and numerical verification are different evidence types.

- [ ] **Step 2: Run fresh non-COM and full COM test suites**

From `1/app` run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -m "not excel" -q -p no:cacheprovider
& '..\..\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp='.pytest-tmp-harness-final-20260917'
```

The full command runs with system access so Excel COM can recalculate. Expected: zero failures.

- [ ] **Step 3: Capture protected-file metadata and run production pipeline**

Read, but do not open for writing, the exact user path metadata (`Length`, `CreationTimeUtc`, `LastWriteTimeUtc`). If Windows permits, also calculate SHA-256. Run:

```powershell
& '..\..\.venv\Scripts\python.exe' .\main.py
```

Expected log: `PIPELINE_COMPLETED files=8 excel_success=True`. Re-read protected-file metadata and assert it is identical. If the file remains locked by Word, compare length and timestamps; do not close Word or retry with write access.

- [ ] **Step 4: Inspect all generated artifacts through the interpreter**

Use `openpyxl`, `csv`, `json` and `python-docx` to assert:

```text
- harness_log.json has seven sequential valid rows;
- Harness_Log.xlsx has headers A1:H1, seven data rows, filter and A2 freeze;
- ground_truth.xlsx contains Harness Log and Сверка Excel–Python;
- ground_truth.xlsx still contains 51 formulas;
- cached FPY=0.75, OEE=0.59375, CPU≈14713.0374957;
- reconciliation statuses are PASS=17, FAIL=0, NOT_COMPUTABLE=1;
- report.md contains both separate sections;
- Word contains at least nine tables, two images and a landscape section;
- the eight required output paths are nonempty;
- output/harness_log.csv is absent;
- execution.log contains no ERROR event.
```

- [ ] **Step 5: Clean only owned pytest temporary directory**

Resolve the exact `.pytest-tmp-harness-final-20260917` path, verify it starts with the resolved `1/app` path plus a directory separator, then remove only that directory with native PowerShell `Remove-Item -LiteralPath -Recurse -Force`.

- [ ] **Step 6: Review diff and commit final artifacts**

Run `git diff --check`, inspect `git diff --stat` and `git status --short`. Stage README, ARCH, generated required outputs, deletion of legacy CSV and the implementation-plan checkboxes. Explicitly exclude `output/Итоговый_отчет_ЭА_EUV_оформленный.docx`. Commit:

```text
docs: publish final Harness Log evidence
```
