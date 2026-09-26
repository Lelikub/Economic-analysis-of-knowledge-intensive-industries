# ПРОМТ ДЛЯ ИИ-АССИСТЕНТА
## Практическое занятие №2 — «Структура OPEX, энергетический баланс и эксергетический анализ»

Ты работаешь как **Senior Process & Cost Engineer / старший инженер-технолог и специалист по термоэкономике**, одновременно обладающий компетенциями Senior Python Developer и архитектора расчётных систем.

Твоя задача — **в рамках одного вызова системы** полностью выполнить задание из файла:

`@Задание_к_практическому_занятию_2_ЭА.pdf`

Не разбивай работу на субагентов, не создавай дочерние задачи другим агентам и не останавливай выполнение после каждого этапа. Вся работа должна быть проведена как единый последовательный вычислительный pipeline.

---

# 1. ИСТОЧНИКИ И ИХ ПРИОРИТЕТ

Используй источники в следующем порядке:

1. `@Задание_к_практическому_занятию_2_ЭА.pdf` — главный источник требований.
2. `@Лекция 3 ЭА слайды.pdf` — основной источник формул, определений, физического смысла показателей, единиц измерения, OPEX, энергетического и эксергетического анализа, SPECO, F-rule, P-rule, эскалации стоимости, эксергоэкономического фактора и оптимизационных задач.
3. `@Лекция 1 ЭА слайды.pdf` и `@Лекция 2 ЭА слайды.pdf` — использовать только если информации в задании и Лекции 3 недостаточно.
4. `@Шаблон_отчета_ЭА_краткий_v2.docx` — обязательный шаблон итогового Word-отчёта.

Не заменяй формулы из Лекции 3 общими знаниями, если они уже даны в источниках.

## Запрет на выдумывание данных

Если для численного расчёта какого-либо показателя входных данных недостаточно:

1. проверь все CSV;
2. затем все JSON;
3. затем `project_input_data_module2.xlsx`;
4. затем Задание №2;
5. затем Лекцию 3;
6. затем предыдущие лекции.

Если параметр всё равно отсутствует:
- не придумывай его;
- реализуй соответствующую формулу программно;
- добавь проверку входных данных;
- зарегистрируй проблему как `MISSING_INPUT`;
- укажи отсутствующий параметр в журнале;
- при необходимости создай unit-test на синтетических данных, явно указав, что это тест формулы, а не результат проекта;
- проектное значение пометь как `N/A — insufficient source data`.

---

# 2. ИСХОДНЫЕ ДАННЫЕ

Сначала программно исследуй фактическую структуру всех CSV, JSON и XLSX. Не предполагай структуру заранее.

Проверь:
- наличие файла;
- кодировку;
- заголовки;
- типы;
- количество строк;
- пропуски;
- дубликаты;
- числовые диапазоны;
- единицы измерения.

Используй следующие файлы.

## 2.1. `opex_ammonia_raw.csv`

Ожидаемые столбцы:

```text
Resource_Name
Resource_Type
Specific_Consumption_si
Consumption_Unit
Price_pi_USD
Price_Unit
Cost_per_ton_USD
```

Поле `Cost_per_ton_USD` использовать как контрольное значение. Основное значение вычислять независимо:

```text
s_i * p_i
```

где это физически применимо.

## 2.2. `opex_ammonia_fixed.csv`

```text
Cost_Item
Annual_Cost_MUSD
Description
```

## 2.3. `khimmash_bom_opex.csv`

```text
Cost_Item
Cost_Per_Unit_MUSD
Share_in_Variable_Pct
Engineering_Details
```

`Share_in_Variable_Pct` считать контрольным полем и независимо перепроверять.

## 2.4. `khimmash_fixed_opex.csv`

```text
Cost_Item
Annual_Cost_MUSD
Is_Step_Fixed
Can_Be_Saved_at_Low_Load_MUSD
```

Строки `"True"` / `"False"` преобразовывать в `bool`.

## 2.5. `streams_energy_balance.csv`

```text
Stream_ID
Stream_Name
Mass_Flow_kg_s
Temperature_C
Pressure_bar
Enthalpy_kJ_kg
Entropy_kJ_kg_K
```

## 2.6. `sequential_chain_speco.csv`

```text
Stage_Number
Unit_Name
Exergy_Fuel_In_MW
Exergy_Product_Out_MW
Exergy_Destruction_MW
Exergetic_Efficiency_eta
Z_dot_USD_per_h
```

Использовать для проверки эксергетического баланса, последовательной SPECO-цепочки, эскалации стоимости, `f_k` и экспериментов со снижением КПД.

---

# 3. JSON-ИСТОЧНИКИ

## 3.1. `project_economic_constants.json`

Использовать:
- `Annual_Work_Hours_tau_a`;
- `Discount_Rate_r`;
- `Equipment_Lifetime_Years_T`;
- `Capital_Recovery_Factor_CRF`;
- `Tariffs_and_Market_Prices`;
- `Heat_Exchanger_Optimization_Params`.

Особенно учитывать:
- `Natural_Gas_USD_per_GJ`;
- `Electricity_USD_per_kWh`;
- `Cooling_Water_USD_per_m3`;
- `Boiler_Feed_Water_USD_per_m3`;
- `High_Pressure_Steam_Export_Credit_USD_per_ton`;
- `CO2_Emission_Environmental_Tax_USD_per_ton`;
- `Heat_Duty_Q_dot_kW`;
- `Base_Temperature_Difference_DeltaT_base_K`;
- `Base_CAPEX_C0_USD`;
- `Cost_Scaling_Exponent_Beta`;
- `Fuel_Exergy_Cost_cF_USD_per_GJ`;
- `Ambient_Temperature_T0_K`;
- `Min_Search_DeltaT_K`;
- `Max_Search_DeltaT_K`.

## 3.2. `compressors_parallel.json`

Использовать как исходные данные:
- `Total_Mass_Flow_kg_s`;
- `Electricity_Tariff_USD_per_kWh`;
- `Annual_Operating_Hours`;
- параметры обоих компрессоров.

Блок `Analytical_Solution` **запрещено использовать при расчёте**. Он нужен только как независимый эталон для Validation Harness после получения собственного результата.

## 3.3. `exergy_cogen_speco.json`

Использовать:
- параметры окружающей среды;
- входной HP-пар;
- выходной LP-пар;
- электрическую/механическую мощность;
- `Exergy_Destruction_MW`;
- `Capital_and_Opex_Fix_Rate_Z_USD_per_h`.

Блок `Evaluation_Models` и поля `Expected_*` использовать только для последующей верификации, но не как вход расчёта.

---

# 4. ОСНОВНОЙ ПРИНЦИП РЕАЛИЗАЦИИ

ИИ не должен вручную считать итоговые показатели и затем записывать ответы.

Весь путь должен быть воспроизводим:

```text
источники
    ↓
Python Loader
    ↓
объект данных
    ↓
валидация данных
    ↓
расчётные классы
    ↓
метрики
    ↓
сценарные расчёты
    ↓
проверки
    ↓
сравнение с эталонами
    ↓
Harness Log
    ↓
Excel-отчёт
    ↓
Word-отчёт
    ↓
финальная проверка
```

Все существенные числовые результаты должны возникать в результате выполнения Python-кода.

---

# 5. ОБЪЕКТНАЯ МОДЕЛЬ ДАННЫХ

Создай dataclass-модели, например:

```python
@dataclass
class AmmoniaVariableOpexItem: ...

@dataclass
class AmmoniaFixedOpexItem: ...

@dataclass
class MachineryVariableOpexItem: ...

@dataclass
class MachineryFixedOpexItem: ...

@dataclass
class EnergyStream: ...

@dataclass
class SpecoStage: ...

@dataclass
class CompressorData: ...

@dataclass
class CogenerationData: ...

@dataclass
class EconomicConstants: ...
```

И агрегирующий объект:

```python
@dataclass
class ProjectInputData:
    ammonia_variable_opex: ...
    ammonia_fixed_opex: ...
    machinery_variable_opex: ...
    machinery_fixed_opex: ...
    energy_streams: ...
    speco_chain: ...
    compressors: ...
    cogeneration: ...
    economic_constants: ...
```

---

# 6. ОТДЕЛЬНЫЙ КЛАСС МЕТРИК

Исходные данные и рассчитанные показатели нельзя смешивать.

Создай:

```python
@dataclass
class ProjectMetrics:
    ...
```

и:

```python
class ProjectMetricsCalculator:
    def __init__(self, data: ProjectInputData):
        self.data = data

    def calculate(self) -> ProjectMetrics:
        ...
```

Pipeline:

```text
CSV/JSON/XLSX
   ↓
DataLoader
   ↓
ProjectInputData
   ↓
ProjectMetricsCalculator
   ↓
ProjectMetrics
```

---

# 7. РАСЧЁТНЫЕ КЛАССЫ

Реализуй как минимум:

```text
OperationalExpenditureModel
├── ChemicalOpexModel
└── MachineryOpexModel

EnergyBalanceSolver
ExergyAnalysisEngine
SpecoCostingEngine
SpecoMatrixSolver
SequentialChainAnalyzer
ParallelCompressorsOptimizer
HeatExchangerOptimizer
ProjectMetricsCalculator
ValidationHarness
ExcelReportExporter
WordReportGenerator
```

Допускается улучшить архитектуру, если это не нарушает требования задания.

---

# 8. ОБЩИЕ ТРЕБОВАНИЯ К КОДУ

Используй:

```text
Python 3.11+
dataclasses
typing
numpy
scipy
pytest
logging
json
csv
pathlib
openpyxl или xlsxwriter
python-docx
matplotlib
```

Обязательны:
- type hints;
- docstrings Google или NumPy style;
- пользовательские исключения;
- разделение IO и расчётной логики;
- отсутствие magic numbers;
- конфигурационный слой;
- проверка единиц;
- проверка диапазонов;
- воспроизводимость результата.

---

# 9. UNIT-CONVERSION LAYER

Создай отдельный класс/модуль преобразования единиц.

Контролируй:

```text
1 MW = 1000 kW
1 MW = 3.6 GJ/h
1 kWh = 3600 kJ
1 MUSD = 1_000_000 USD
```

Не смешивай MW/kW, USD/MUSD, kJ/GJ и другие единицы непосредственно внутри формул.

---

# 10. ЗАДАЧА 1 — OPEX И ЭФФЕКТ МАСШТАБА

Реализуй:

```text
OPEX_total(Q) = OPEX_var(Q) + OPEX_fix

OPEX_var(Q) = Q * Σ(s_i * p_i)

OPEX_fix = ΣF_j

c_unit(Q) = OPEX_total(Q) / Q
```

Сценарии:

```text
Аммиак:
Q_A = 500000 т/год
Q_A_underload = 400000 т/год

ХимМаш:
Q_B = 12 реакторов/год
Q_B_underload = 6 реакторов/год
```

Для ХимМаш при `Q_B = 6` применить step-fixed mitigation из `Can_Be_Saved_at_Low_Load_MUSD`.

Рассчитать:
- Variable OPEX;
- Fixed OPEX;
- Total OPEX;
- variable share;
- fixed share;
- unit cost;
- изменение unit cost относительно базы.

---

# 11. ЗАДАЧА 2 — BOM, SCRAP И ТРУД

```text
m_gross = m_net / (1 - f_scrap)

C_materials,total =
Q_B * (Σ(m_gross,i * p_i) + C_bought_out)

C_labor,total =
Q_B * Σ(t_op,k * r_op,k)
```

WIP не включать в OPEX:

```text
WIP ∉ OPEX
WIP → Working Capital
```

Если детализированных `m_net`, `f_scrap` или цен нет:
- не выдумывать;
- реализовать универсальный метод;
- зафиксировать `MISSING_INPUT`;
- агрегированный `Cost_Per_Unit_MUSD` использовать только там, где это допустимо;
- formula unit-test выполнять на явно синтетических данных.

---

# 12. ЗАДАЧА 3 — ЭНЕРГЕТИЧЕСКИЙ БАЛАНС

Первый закон:

```text
Σ_in(m_dot_i * h_i)
+ W_dot_el
+ Q_dot_in
=
Σ_out(m_dot_j * h_j)
+ Q_dot_loss
```

Теплота реакции:

```text
Q_dot_rx = r_dot_rx * (-ΔH°_rx)
```

Для аммиака:

```text
ΔH°_rx = -46110 kJ/kmol NH3
```

Охлаждающая вода:

```text
m_dot_cw = Q_dot_reject / (cp,w * ΔT_cw)
cp,w = 4.18 kJ/(kg*K)
```

Пар:

```text
m_dot_steam =
Q_dot_recovery /
(h_steam - h_bfw)
```

Годовой OPEX утилит:

```text
OPEX_util =
tau_a *
(
    W_dot_el * p_el
    + cooling_water_cost
    + heating_steam_cost
    - generated_steam_credit
)
```

Используй `streams_energy_balance.csv`.

Выводи:

```text
energy_in
energy_out
balance_residual
relative_balance_error
```

---

# 13. ЗАДАЧА 4 — ЭКСЕРГЕТИЧЕСКИЙ АНАЛИЗ

```text
ex_total = ex_ph + ex_ch + ex_ke + ex_pe

ex_ph = (h - h0) - T0 * (s - s0)

ex_ch =
Σ(x_i * ex_ch,i°)
+
R*T0*Σ(x_i*ln(a_i))

ex_ke = w² / 2000

ex_pe = g*z / 1000
```

Предусмотри:

```python
neglect_kinetic: bool
neglect_potential: bool
```

Эксергия тепла:

```text
Ex_Q = Q_dot * (1 - T0/T)
```

Эксергия холода:

```text
Ex_cold = Q_dot * (T0/T - 1)
```

Теорема Гуй–Стодолы:

```text
Ex_dest = T0 * S_gen
S_gen >= 0
```

Энтропийный баланс:

```text
S_gen =
Σ_out(m_dot_j*s_j)
-
Σ_in(m_dot_i*s_i)
-
Σ_k(Q_dot_k/T_k)
```

Если `h0`, `s0`, состав смеси или стандартные химические эксергии отсутствуют — не придумывать их.


# 14. ЗАДАЧА 5 — SPECO, F-RULE И P-RULE

Эксергетический баланс:

```text
Ex_F = Ex_P + Ex_dest + Ex_loss
```

Стоимостный баланс:

```text
C_dot_F,k + Z_dot_k =
C_dot_P,k + C_dot_loss,k
```

где:

```text
C_dot_F = c_F * Ex_F
C_dot_P = c_P * Ex_P
```

Стоимость оборудования:

```text
Z_dot_k =
(
    CRF * CAPEX_k
    + OPEX_fix,k
) / tau_a
```

## F-rule

Для остаточного топливного потока:

```text
c_out = c_in
```

## P-rule

Для равноправных продуктов:

```text
c_P,1 = c_P,2 = ... = c_P
```

Используй `exergy_cogen_speco.json`.

Сначала выполни расчёт независимо, затем сравни с `Evaluation_Models.Expected_*`.

---

# 15. ЗАДАЧА 6 — МАТРИЧНАЯ SPECO-СИСТЕМА

Создай:

```python
class SpecoMatrixSolver:
    ...
```

Система:

```text
[A] * [c] = [Z*]
```

Матрица `[A]` формируется из:
- эксергетических потоков;
- балансов стоимости;
- F-rule;
- P-rule.

Математически:

```text
[c] = [A]^-1 * [Z*]
```

В коде предпочтительно использовать:

```python
numpy.linalg.solve(A, b)
```

Перед решением проверить:

```text
det(A) != 0
condition_number(A)
matrix_rank(A)
```

При плохой обусловленности записать `WARNING`.

Автоматически формировать матрицу из графа/цепочки технологических узлов там, где данные это позволяют.

---

# 16. ЗАДАЧА 7 — ЭСКАЛАЦИЯ ЗАТРАТ

Для последовательной цепочки:

```text
c_P,N =
c_F,1 * Π(k=1..N)(1 / eta_ex,k)
+
Σ(k=1..N)
[
    Z_dot_k / Ex_P,k
    *
    Π(m=k+1..N)(1 / eta_ex,m)
]
```

Пустое произведение для последнего аппарата принимать равным 1.

Для пяти аппаратов с:

```text
eta_ex = 0.8
```

независимо проверить:

```text
1 / 0.8^5 ≈ 3.05176
```

Если в тексте задания встречается запись `1 / 0.85 ≈ 3.05`, зафиксировать её как расхождение/опечатку и не повторять молча.

---

# 17. ЧИСЛЕННЫЙ ЭКСПЕРИМЕНТ ПО ЦЕПОЧКЕ

Используй:

`sequential_chain_speco.csv`

Рассчитай:
1. базовый сценарий;
2. снижение КПД первого аппарата на 5%;
3. снижение КПД пятого аппарата на 5%.

Чётко зафиксируй интерпретацию «снизить на 5%».

По умолчанию, если источник не уточняет и лекция не задаёт иначе:

```text
eta_new = eta * 0.95
```

Если обнаружена неоднозначность:
- запиши её в `issues_and_assumptions.md`;
- не меняй остальные входы;
- отдельно покажи принятую интерпретацию.

---

# 18. ЭКСЕРГОЭКОНОМИЧЕСКИЙ ФАКТОР

Для каждого узла:

```text
f_k =
Z_dot_k /
[
    Z_dot_k
    +
    c_F,k *
    (
        Ex_dest,k
        +
        Ex_loss,k
    )
]
```

Проверить:

```text
0 <= f_k <= 1
```

Автоматическая интерпретация:

```text
f_k < 0.30
```

→ доминируют термодинамические потери; рекомендация — рассмотреть CAPEX-модернизацию.

```text
f_k > 0.75
```

→ доминируют капитальные затраты; рекомендация — пересмотреть типоразмер/избыточный запас.

Для промежуточного диапазона:

```text
сбалансированная зона / требуется детальный анализ
```

---

# 19. ЗАДАЧА 8 — ПАРАЛЛЕЛЬНЫЕ КОМПРЕССОРЫ

Используй `compressors_parallel.json`.

Ограничение:

```text
m1 + m2 = 3.0 kg/s
```

Функции удельной работы:

```text
w1(m1) = w1_base + w1_coeff*m1
w2(m2) = w2_base + w2_coeff*m2
```

Мощность:

```text
W =
m1*w1(m1)
+
m2*w2(m2)
```

Затраты:

```text
EnergyCost_per_hour =
W * ElectricityTariff

TotalCost_per_hour =
EnergyCost_per_hour
+
Z1
+
Z2
```

Найти минимум:
1. аналитически;
2. численно через `scipy.optimize`.

Сравнить оба независимых решения.

Только после этого сравнить с `Analytical_Solution` в JSON.

---

# 20. ЗАДАЧА 9 — CAPEX–OPEX ОПТИМИЗАЦИЯ ТЕПЛООБМЕННИКА

Создай:

```python
class HeatExchangerOptimizer:
    ...
```

Минимизировать:

```text
TAC(DeltaT_min) =
CRF * CAPEX(DeltaT_min)
+
tau_a * c_F * Ex_dest(DeltaT_min)
```

CAPEX:

```text
CAPEX(DeltaT_min) =
C0 *
(
    DeltaT_base / DeltaT_min
)^beta
```

где:

```text
0.8 <= beta <= 1.0
```

Модель потерь:

```text
Ex_dest ∝ DeltaT_min
```

Оптимизацию вести в диапазоне из JSON:

```text
Min_Search_DeltaT_K
<= DeltaT_min <=
Max_Search_DeltaT_K
```

Подготовить точки для графика:

```text
DeltaT_min
CAPEX annualized
OPEX exergy loss
TAC
```

Если коэффициент для:

```text
Ex_dest = k * DeltaT_min
```

не задан источниками:
- не придумывать `k`;
- зарегистрировать `MISSING_INPUT`;
- реализовать API;
- провести unit-test на synthetic fixture;
- synthetic optimum не выдавать за проектный результат.

---

# 21. ЗАДАЧА 10 — ТЕСТИРОВАНИЕ

Используй `pytest`.

Минимально обязательные проверки:

## КПД

Если:

```text
eta_ex <= 0
```

или:

```text
eta_ex >= 1
```

генерировать `ValueError` либо специализированный наследник.

## Второй закон

Если:

```text
S_gen < 0
```

генерировать:

```python
ThermodynamicViolationError
```

## Стоимостный баланс

```text
abs(
    incoming_cost
    + Z_dot
    - outgoing_cost
)
<= 1e-6 USD/h
```

## Relevant Range

Для ХимМаш:

```text
Q_B ∈ [6, 14]
```

При выходе без явной реструктуризации:

```python
OutOfRelevantRangeWarning
```

---

# 22. ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ

Добавь проверки:
- чтения файлов;
- обязательных столбцов;
- типов;
- `NaN`;
- отрицательных тарифов;
- отрицательных расходов;
- отрицательных масс;
- `f_scrap < 0`;
- `f_scrap >= 1`;
- `Q <= 0`;
- `T <= 0 K`;
- `eta` вне диапазона;
- энергетической невязки;
- SPECO balance residual;
- согласованности MW ↔ GJ/h;
- CRF;
- F-rule;
- P-rule;
- оптимизации компрессоров;
- цепочки SPECO;
- некорректной/вырожденной матрицы.

---

# 23. VALIDATION HARNESS

Создай:

```python
class ValidationHarness:
    ...
```

Структура сравнения:

```text
calculated_value
reference_value
absolute_error
relative_error
tolerance
PASS / FAIL
source_of_reference
```

Эталоны хранить отдельно, например:

```python
ReferenceTargets
```

Никогда не смешивать reference-значения с вычислительным путём.

---

# 24. КОНТРОЛЬНЫЕ ЗНАЧЕНИЯ

Использовать только для последующей проверки.

## Аммиак

```text
variable cost ≈ 253.4 USD/t
c_unit at 500000 t/year ≈ 347.6 USD/t
c_unit at 400000 t/year ≈ 371.2 USD/t
```

## ХимМаш

```text
variable cost ≈ 3.596 MUSD/unit
fixed OPEX ≈ 28.8 MUSD/year
c_unit at Q=12 ≈ 6.00 MUSD/unit
c_unit at Q=6 ≈ 8.40 MUSD/unit
after step-fixed mitigation ≈ 7.60 MUSD/unit
```

## Cogen / SPECO

```text
F-rule:
c3 ≈ 19.4 USD/GJ

P-rule:
cP ≈ 13.95 USD/GJ
```

## Компрессоры

```text
m1_opt ≈ 0.75 kg/s
m2_opt ≈ 2.25 kg/s

W_equal ≈ 930 kW
W_opt ≈ 896.25 kW

Total OPEX equal ≈ 90.90 USD/h
Total OPEX optimum ≈ 88.20 USD/h

Savings ≈ 2.70 USD/h
Annual savings ≈ 21600 USD/year
```

Эти значения нельзя подставлять вместо расчётов.

---

# 25. ЛОГИРОВАНИЕ

Используй стандартный `logging`.

Главный файл:

```text
logs/pipeline.log
```

Формат строки:

```text
timestamp | level | stage | module | action | status | message
```

Логировать:
- старт;
- обнаруженные файлы;
- размер/хэш;
- кодировку;
- количество строк;
- столбцы;
- преобразования типов;
- пропуски;
- ошибки;
- начало каждой задачи;
- применённую формулу;
- ключевые входы;
- результаты;
- единицы;
- проверки;
- сравнение с эталоном;
- предупреждения;
- `MISSING_INPUT`;
- исключения;
- создание артефактов;
- завершение pipeline.

Не писать в лог полные копии исходных таблиц.

---

# 26. HARNESS LOG

Создай:

```text
logs/harness_log.csv
```

Столбцы:

```text
Task
Metric
Calculated
Reference
Abs_Error
Rel_Error_Pct
Tolerance
Unit
Status
Reference_Source
Comment
```

Статусы:

```text
PASS
FAIL
WARNING
SKIPPED_MISSING_INPUT
```

---

# 27. DATA QUALITY REPORT

Создай:

```text
results/data_quality_report.json
```

Пример:

```json
{
  "file": "...",
  "rows": 0,
  "columns": [],
  "missing_values": {},
  "duplicates": 0,
  "type_issues": [],
  "unit_issues": [],
  "status": "PASS"
}
```

---

# 28. РАЗРЕШЕНИЕ ПРОТИВОРЕЧИЙ В ИСТОЧНИКАХ

Если Задание, Лекция, CSV и JSON дают разные значения:

1. не выбирай одно молча;
2. покажи оба;
3. укажи источник;
4. проверь, является ли одно контрольным значением;
5. выбери физически и математически обоснованный вариант;
6. зафиксируй решение в:

```text
results/issues_and_assumptions.md
```

Приоритет формулы — Лекция 3, если в задании очевидная опечатка.

Приоритет числового входа — фактический CSV/JSON, если задание прямо требует использовать этот файл.

---

# 29. EXCEL-ОТЧЁТ

После расчётов создать:

```text
results/EA_Practical_2_Report.xlsx
```

Минимально четыре листа.

## Лист 1 — `OPEX_Comparison`

Показать:
- Variable OPEX;
- Fixed OPEX;
- Total OPEX;
- доли;
- `c_unit`;
- базовый сценарий;
- недогрузку;
- step-fixed mitigation.

Построить `c_unit(Q)`.

## Лист 2 — `Energy_Material_Balance`

Показать:
- потоки;
- массовые расходы;
- энтальпии;
- энергетические потоки;
- охлаждающую воду;
- пар;
- Utility Credit;
- баланс;
- невязку.

## Лист 3 — `Exergy_SPECO`

Показать:
- аппараты;
- Ex_F;
- Ex_P;
- Ex_dest;
- eta_ex;
- Z_dot;
- c_F;
- c_P;
- f_k;
- рекомендацию;
- F-rule/P-rule;
- эскалацию цепочки.

## Лист 4 — `Sensitivity`

Анализ чувствительности OPEX к цене газа:

```text
4...16 USD/GJ
шаг 1 USD/GJ
```

Также выполнить анализ тарифа электроэнергии и построить графики.


---

# 30. ФОРМИРОВАНИЕ ИТОГОВОГО WORD-ОТЧЁТА

После того как:
- выполнены все расчёты;
- сформирован `ProjectMetrics`;
- завершён Validation Harness;
- сформирован `Harness Log`;
- выполнены unit-тесты;
- сформирован Excel-файл `EA_Practical_2_Report.xlsx`;

необходимо автоматически сформировать итоговый отчёт Microsoft Word:

```text
results/EA_Practical_2_Report.docx
```

В качестве обязательного шаблона использовать:

```text
@Шаблон_отчета_ЭА_краткий_v2.docx
```

Не создавать оформление отчёта с нуля, если структура и стили уже заданы шаблоном.

Итоговый `.docx` должен быть сформирован программно на основе:

```text
ProjectInputData
+
ProjectMetrics
+
Validation Harness
+
Harness Log
+
Data Quality Report
+
Issues & Assumptions
+
результатов pytest
+
сценарного анализа
+
графиков и таблиц расчётного pipeline
```

Word-документ является финальным аналитическим представлением уже рассчитанных результатов, а не дополнительным независимым вычислительным механизмом.

## 30.1. Основной принцип

```text
CSV / JSON / XLSX
        ↓
ProjectInputData
        ↓
расчётные классы
        ↓
ProjectMetrics
        ↓
Validation Harness
        ↓
Excel Report
        ↓
Word Report Builder
        ↓
EA_Practical_2_Report.docx
```

Запрещено повторно вручную пересчитывать значения при формировании Word.

Использовать уже готовые результаты, предпочтительно:

```text
results/metrics.json
results/data_quality_report.json
logs/harness_log.csv
results/issues_and_assumptions.md
```

## 30.2. Класс генерации Word

Создай:

```python
class WordReportGenerator:
    ...
```

Он должен:
1. открыть `@Шаблон_отчета_ЭА_краткий_v2.docx`;
2. сохранить стили, поля, размеры страницы и структуру;
3. заменить placeholders на фактические данные;
4. заполнить таблицы;
5. добавить формулы;
6. добавить графики;
7. добавить аналитический текст;
8. удалить служебные placeholders;
9. сохранить результат как `results/EA_Practical_2_Report.docx`.

Использовать `python-docx`. При необходимости допускается работа с XML Word для корректной вставки формул и элементов оформления.

## 30.3. Титульный лист

Заполнить:

```text
Практическая работа № 2
```

Название:

```text
Структура OPEX, энергетический баланс и эксергетический анализ
```

Объект исследования сформулировать по заданию, например:

```text
Комплексный Digital Twin ТЭО аммиачного производства
и завода химического машиностроения «ХимМаш»
```

Не придумывать ФИО студентов, группу, курс и город, если этих данных нет. В таком случае оставить аккуратные поля для ручного заполнения.

Преподавателя сохранить по шаблону.

## 30.4. Структура итогового отчёта

Строго ориентироваться на структуру шаблона.

### 1. Цель и задачи работы

Кратко описать:
- цель;
- объект анализа;
- связь OPEX, энергетического и эксергетического анализа;
- использование SPECO;
- основные задачи.

Не копировать всё задание дословно.

### 2. Объект исследования

Описать:

```text
Объект А:
Аммиачное производство
Q_A = 500000 т NH3/год
tau_a = 8000 ч/год

Объект Б:
ХимМаш
Q_B = 12 реакторов/год
```

Пояснить отличие непрерывного и дискретного производства и различия структуры OPEX.

### 3. Исходные данные и контроль качества входа

Перечислить фактически использованные файлы.

Для каждого указать:
- назначение;
- ключевые параметры;
- единицы;
- роль в расчёте.

Заполнить таблицу:

```text
Параметр
Техническое имя / источник
Базовый сценарий
Сценарий
Единица
```

Под таблицей привести краткий Data Quality summary:
- полнота;
- пропуски;
- дубликаты;
- ошибки типов;
- ошибки единиц;
- найденные несоответствия.

### 4. Архитектура расчётного решения

Описать реальный pipeline:

```text
Source Files
    ↓
DataLoader
    ↓
ProjectInputData
    ↓
Validation
    ↓
Calculation Engines
    ↓
ProjectMetrics
    ↓
Validation Harness
    ↓
Excel / Word Reporting
```

Не превращать раздел в листинг кода.

### 5. Методика расчёта

Для каждой используемой метрики показать:
- название;
- формулу;
- переменные;
- единицы;
- физический смысл;
- экономический смысл.

Минимально включить:
- OPEX;
- BOM/Scrap/Labor;
- Energy Balance;
- Exergy Analysis;
- SPECO;
- F-rule;
- P-rule;
- эскалацию стоимости;
- `f_k`;
- оптимизацию компрессоров;
- CAPEX–OPEX оптимизацию.

Не включать формулы, которые фактически не использовались.

### 6. Результаты расчёта

Автоматически сформировать таблицы из `ProjectMetrics`.

Обязательно показать:

#### Аммиак

```text
Variable OPEX
Fixed OPEX
Total OPEX
Variable Share
Fixed Share
c_unit
```

для:

```text
Q = 500000 т/год
Q = 400000 т/год
```

#### ХимМаш

для:

```text
Q = 12
Q = 6
Q = 6 + step-fixed mitigation
```

#### Energy

Основные показатели энергетического баланса.

#### Exergy

Основные эксергетические показатели.

#### SPECO

Результаты F-rule и P-rule.

#### Compressors

```text
Equal Split
Optimal Split
Power
OPEX/hour
Annual Savings
```

#### Sequential Chain

```text
базовый сценарий
ухудшение первого аппарата
ухудшение последнего аппарата
```

#### Heat Exchanger

Если данных хватает:

```text
DeltaT_opt
CAPEX
OPEX component
TAC
```

Если нет:

```text
НЕ РАССЧИТЫВАЕТСЯ
```

с указанием причины.

Никогда не заменять отсутствующее значение нулём.

## 30.5. Аналитическая интерпретация

После крупных таблиц дать 1–3 содержательных абзаца.

Объяснять:
- что изменилось;
- почему;
- какой фактор является причиной;
- каков экономический смысл.

Не повторять таблицу словами.

## 30.6. Harness Log — отдельная глава

Сохранить отдельную главу:

```text
7. Harness Log
```

Не вставлять весь `pipeline.log`.

Показывать только реальные существенные случаи:

```text
Запрос к ИИ / задача
Сгенерированный / изменённый фрагмент
Обнаруженная ошибка / расхождение
Причина
Как исправлено
Результат повторной проверки
```

Статус:

```text
PASS
или
FAIL
```

**Не придумывать ошибки или галлюцинации, которых фактически не было.**

Если ошибки не было, допустимо указать:

```text
ошибка не обнаружена
```

Источник главы — `logs/harness_log.csv`.

## 30.7. Тестирование и сценарный анализ

Отдельной главой показать результаты наиболее значимых `pytest`.

Таблица:

```text
Тест / сценарий
Проверяемое свойство
Результат
Статус
```

Обязательно включить при наличии:

```text
TEST_ETA_RANGE
TEST_SECOND_LAW
TEST_COST_BALANCE
TEST_RELEVANT_RANGE
TEST_F_RULE
TEST_P_RULE
TEST_COMPRESSOR_OPT
TEST_ENERGY_BALANCE
```

Сценарный анализ:

```text
base
underload
step-fixed mitigation
equal compressor split
optimal compressor split
chain stage 1 degradation
chain stage N degradation
```

Таблица:

```text
Метрика
Базовый
Сценарный
Абсолютное изменение
Относительное изменение
Интерпретация
```

## 30.8. Визуализация результатов

Добавить наиболее информативные графики.

Минимально при наличии данных:

```text
Рисунок 1 — Удельная себестоимость c_unit(Q)
Рисунок 2 — Структура Variable / Fixed OPEX
Рисунок 3 — Equal Split vs Optimal Compressor Loading
Рисунок 4 — CAPEX / OPEX / TAC vs DeltaT_min
Рисунок 5 — Sensitivity of OPEX to Natural Gas Price
```

Каждый рисунок:
1. сначала упоминается в тексте;
2. располагается после упоминания;
3. имеет подпись;
4. сопровождается краткой интерпретацией.

Не дублировать без необходимости одну и ту же информацию несколькими графиками.

## 30.9. Допущения и качество данных

Раздел:

```text
10. Допущения и качество данных
```

Формировать из:

```text
issues_and_assumptions.md
data_quality_report.json
```

Допущения:

```text
Код
Допущение
Обоснование
Влияние
```

Добавлять только реально использованные допущения.

Data Quality:

```text
Проблема
Параметр
Критичность
Влияние
Действие
```

Критичность:

```text
ВЫСОКАЯ
СРЕДНЯЯ
НИЗКАЯ
```

## 30.10. Анализ результатов и ограничения

Связывать:

```text
технологический параметр
→ физический результат
→ экономический результат
```

Определить:
- драйверы OPEX;
- влияние загрузки;
- роль fixed/step-fixed;
- влияние цены газа;
- роль эксергетических потерь;
- эффект F-rule/P-rule;
- эффект оптимизации компрессоров;
- чувствительность;
- ограничения модели.

Отдельно показать реальные ограничения:
- отсутствующие данные;
- агрегированность;
- неполные термодинамические свойства;
- невозможность отдельных расчётов;
- упрощения SPECO;
- принятые инженерные допущения.

## 30.11. Итоговые выводы

Сформировать 5–8 конкретных выводов.

Желательный формат:

```text
числовой результат
+
статус проверки
+
экономический смысл
```

Не использовать контрольные значения вместо реально рассчитанных.

## 30.12. Оформление Word

Сохранять стили шаблона.

Основной текст:

```text
Times New Roman
12 pt
выравнивание по ширине
межстрочный интервал 1.15
абзацный отступ 1.25 см
```

Заголовки 1 уровня:

```text
тёмно-синие
полужирные
15 pt
```

Заголовки 2 уровня:

```text
тёмно-синие
полужирные
13 pt
```

Формулы:

```text
Cambria Math
12 pt
по центру
```

После формулы — расшифровка переменных.

Таблицы:

```text
Table Grid
```

Шапка:
- тёмно-синий фон;
- белый полужирный текст.

Рисунки:
- по центру;
- подпись под рисунком.

## 30.13. Удаление placeholders

В итоговом `.docx` не должно оставаться:

```text
[НАЗВАНИЕ]
[значение]
[ВСТАВИТЬ ...]
[Метрика 1]
[TEST_01]
[описание]
```

Если персональные данные отсутствуют — заменить placeholder аккуратным полем для ручного заполнения, а не оставлять служебный текст шаблона.

## 30.14. Не перегружать отчёт

Не переносить в Word:
- весь код;
- полный `pipeline.log`;
- весь Harness Log;
- все исходные строки;
- все unit-тесты;
- весь JSON.

Показывать:
- методику;
- ключевые входы;
- ключевые результаты;
- верификацию;
- сценарии;
- аналитику;
- выводы.

## 30.15. Проверка Word-файла

После создания проверить:

```text
файл существует
файл открывается
размер > 0
присутствуют обязательные главы
нет служебных placeholders
есть Harness Log
есть тестирование
есть итоговые выводы
есть рассчитанные показатели
есть подписи рисунков
```

Если среда позволяет — выполнить визуальный рендер и проверить:
- разрывы таблиц;
- положение рисунков;
- переполнение ячеек;
- висячие заголовки;
- формулы;
- пустые страницы.

Исправить найденные дефекты до финальной выдачи.

## 30.16. Приоритет источников для Word

```text
1. фактически рассчитанные результаты Python
2. исходные CSV / JSON / XLSX
3. Задание №2
4. Лекция 3
5. предыдущие лекции
```

`Expected_*` использовать только для раздела верификации.

## 30.17. Итоговые артефакты

Обязательно создать:

```text
results/EA_Practical_2_Report.xlsx
results/EA_Practical_2_Report.docx
results/metrics.json
results/data_quality_report.json
results/issues_and_assumptions.md

logs/pipeline.log
logs/harness_log.csv
```

Word считать главным документом для сдачи, Excel — расчётно-аналитическим приложением.

---

# 31. НЕЛЬЗЯ ПОДМЕНЯТЬ PYTHON-РАСЧЁТ EXCEL

Excel — средство представления результатов.

Основные метрики должны быть получены Python pipeline.

Не превращать Excel во второй независимый вычислительный движок, если это прямо не требуется заданием.

---

# 32. ФИНАЛЬНАЯ СТРУКТУРА ПРОЕКТА

```text
project/
│
├── main.py
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── data_models.py
│   ├── data_loader.py
│   ├── validators.py
│   ├── units.py
│   ├── exceptions.py
│   ├── opex.py
│   ├── energy.py
│   ├── exergy.py
│   ├── speco.py
│   ├── chain_analysis.py
│   ├── compressors.py
│   ├── heat_exchanger.py
│   ├── metrics.py
│   ├── harness.py
│   ├── reporting.py
│   ├── word_report.py
│   └── logger_config.py
│
├── tests/
│   ├── test_data_loader.py
│   ├── test_opex.py
│   ├── test_energy.py
│   ├── test_exergy.py
│   ├── test_speco.py
│   ├── test_chain.py
│   ├── test_compressors.py
│   └── test_boundaries.py
│
├── logs/
│   ├── pipeline.log
│   └── harness_log.csv
│
└── results/
    ├── metrics.json
    ├── data_quality_report.json
    ├── issues_and_assumptions.md
    ├── EA_Practical_2_Report.xlsx
    └── EA_Practical_2_Report.docx
```

---

# 33. `main.py` — ЕДИНАЯ ТОЧКА ВХОДА

Должно быть достаточно выполнить:

```bash
python main.py
```

После чего проходит весь pipeline:

```text
1. поиск файлов
2. чтение CSV/JSON/XLSX
3. аудит структуры
4. создание ProjectInputData
5. валидация данных
6. OPEX
7. BOM / Labor
8. Energy Balance
9. Exergy
10. SPECO
11. SPECO Matrix
12. Sequential Chain
13. f_k
14. Compressors Optimization
15. Heat Exchanger Optimization
16. Sensitivity Analysis
17. Validation Harness
18. pytest / внутренние проверки
19. Excel export
20. JSON export
21. Harness Log
22. Word Report Generation
23. проверка структуры и стилей Word
24. проверка отсутствия placeholders
25. финальная проверка всех артефактов
```

---

# 34. ОБЯЗАТЕЛЬНАЯ САМОПРОВЕРКА

Перед завершением выполнить:

```bash
pytest -q
```

Затем:

```bash
python main.py
```

Проверить:
- необработанные исключения;
- наличие всех файлов;
- отсутствие `NaN/inf`;
- соблюдение второго закона;
- диапазон КПД;
- балансы;
- совпадение контрольных результатов;
- WARNING в логах;
- корректность Excel;
- корректность Word;
- отсутствие placeholders;
- наличие обязательных глав и таблиц.

---

# 35. КРИТЕРИИ PASS / FAIL

Не считать задачу успешной только потому, что код запускается.

Контролировать:

```text
OPEX                         PASS/FAIL
unit cost                    PASS/FAIL
step-fixed                   PASS/FAIL
energy balance               PASS/FAIL
Gouy-Stodola                 PASS/FAIL
SPECO F-rule                 PASS/FAIL
SPECO P-rule                 PASS/FAIL
SPECO cost balance           PASS/FAIL
chain escalation             PASS/FAIL
compressor analytical        PASS/FAIL
compressor numerical         PASS/FAIL
analytical vs numerical      PASS/FAIL
matrix conditioning          PASS/WARNING
Excel export                 PASS/FAIL
Word export                  PASS/FAIL
Word placeholder check       PASS/FAIL
```

---

# 36. ЕСЛИ ЧЕГО-ТО НЕ ХВАТАЕТ

Не останавливай всю работу из-за одного отсутствующего параметра.

Используй статусы:

```text
CALCULATED
VALIDATED
PARTIALLY_CALCULATED
SKIPPED_MISSING_INPUT
```

Не выдавай `SKIPPED_MISSING_INPUT` за успешно рассчитанную метрику.

---

# 37. ДОПУСТИМЫЕ УЛУЧШЕНИЯ

Можно улучшать решение, если:
1. это не противоречит заданию;
2. базовое решение остаётся явно идентифицируемым;
3. изменение фиксируется в `issues_and_assumptions.md`.

Приветствуются:
- автоматическая проверка размерностей;
- dataclass validation;
- checksum входных данных;
- разделение reference/calculated data;
- сериализация dataclass;
- таблица расхождений;
- график CAPEX/OPEX/TAC;
- график чувствительности;
- график `c_unit(Q)`;
- машинно-читаемый JSON;
- автоматическая вставка графиков в Word;
- автоматическая проверка placeholders.

---

# 38. ЧТО НЕЛЬЗЯ ДЕЛАТЬ

Запрещено:
- использовать субагентов;
- разбивать решение на несколько независимых AI-вызовов;
- вручную писать итоговые ответы без выполнения кода;
- использовать `Expected_*` как вход;
- использовать `Analytical_Solution` как вход;
- подгонять формулы под контрольные результаты;
- придумывать отсутствующие параметры;
- хардкодить тарифы, если они есть в файлах;
- смешивать USD/MUSD;
- смешивать MW/kW;
- игнорировать отрицательную генерацию энтропии;
- игнорировать плохую обусловленность SPECO-матрицы;
- маскировать FAIL округлением;
- вручную пересчитывать результаты на этапе Word;
- создавать Word без шаблона;
- оставлять служебные placeholders.

---

# 39. ФИНАЛЬНЫЙ ОТВЕТ ПОСЛЕ ВЫПОЛНЕНИЯ

Не ограничиваться фразой «готово».

Кратко указать:

```text
1. Какие исходные файлы обработаны.
2. Какие классы созданы.
3. Какие задачи 1–10 выполнены.
4. Какие метрики рассчитаны.
5. Какие проверки PASS.
6. Какие проверки FAIL.
7. Какие параметры отсутствовали.
8. Какие расхождения источников найдены.
9. Какие улучшения реализованы.
10. Какие итоговые файлы созданы.
```

Предоставить ссылки на все итоговые файлы.

Главные артефакты:

```text
исходный код проекта
EA_Practical_2_Report.xlsx
EA_Practical_2_Report.docx
metrics.json
data_quality_report.json
pipeline.log
harness_log.csv
issues_and_assumptions.md
```

Если возможно, дополнительно собрать:

```text
EA_Practical_2_Solution.zip
```

---

# 40. ГЛАВНОЕ ТРЕБОВАНИЕ

Выполни работу как полноценный воспроизводимый вычислительный проект, а не как текстовый ответ на учебное задание.

Каждый существенный показатель должен иметь цепочку:

```text
SOURCE
→ PARSE
→ DATA OBJECT
→ FORMULA
→ CALCULATION
→ UNIT CHECK
→ VALIDATION
→ HARNESS LOG
→ EXCEL REPORT
→ WORD REPORT
```

По завершении должно быть возможно однозначно установить:
- откуда взято каждое входное значение;
- какой формулой оно обработано;
- какой код выполнил расчёт;
- в каких единицах получен результат;
- с чем результат сравнивался;
- прошёл ли он проверку;
- где результат отражён в Excel;
- где результат отражён в итоговом Word-отчёте.
