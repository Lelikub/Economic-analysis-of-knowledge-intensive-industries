# Практическое занятие № 1

## Базовая операционная модель и ресурсоёмкость High-Tech производства

## 1. Цель работы

Преобразовать физические параметры пилотного производства EUV-фоторезиста в воспроизводимую экономическую модель с независимыми расчётами Python и Microsoft Excel.

## 2. Исходные данные

Использованы `euv_photoresist_pilot_2026.csv`, `euv_photoresist_stress_2026.csv` и `euv_photoresist_comparison_input_2026.csv`. Расчётный период pilot CSV — 720 календарных часов, то есть 30 суток.

### CSV → model fields → formulas

| Parameter | CSV source | Meaning | Unit | Used in metric | Expected range | Validation rule | Notes |
|---|---|---|---|---|---|---|---|
| Calendar_Hours | pilot + stress | Календарный фонд времени в месяц (30 дней * 24 часа) | hours | Utilization, TEEP | > 0 | > 0 | ProductionData.calendar_hours |
| Planned_Hours | pilot + stress | Плановое время работы (2 смены по 8 часов, 30 дней) | hours | Availability, Performance, Utilization | 0..Calendar_Hours | 0..Calendar_Hours | ProductionData.planned_hours |
| Actual_Hours | pilot + stress | Фактическое время реакции (вычет остановок на глубокую промывку и регенерацию) | hours | Availability, Performance | 0..Planned_Hours | 0..Planned_Hours | ProductionData.actual_hours |
| Target_Output | pilot + stress | Плановый объем выпуска ультрачистого EUV-фоторезиста за плановое время | L | Normative Cycle Time, Performance | >= 0 | >= 0 | ProductionData.target_output |
| Actual_Output | pilot + stress | Фактически запущенный в синтез объем партии | L | FPY, Final Yield, Performance | >= 0 | >= 0 | ProductionData.actual_output |
| First_Pass_Good_Units | pilot + stress | Годная продукция с первого прохода без повторной фильтрации (G_fr), FPY = 75% | L | FPY, Quality, OEE | 0..Actual_Output | 0..Actual_Output | ProductionData.first_pass_good_units |
| Final_Good_Units | pilot + stress | Итоговая годная продукция после ректификации и переделки (G_final), Final Yield = 85% | L | Final Yield, intensities, CPU | 0..Actual_Output | 0..Actual_Output | ProductionData.final_good_units |
| Raw_Material_Cost | pilot + stress | Прямые материалы (DM): прекурсоры олова (SnOx), фотоактивные генераторы, фторированные растворители ($2500/л) | USD | Total Manufacturing Cost, proxy | >= 0 (кроме intentional stress) | >= 0 (кроме intentional stress) | ProductionData.raw_material_cost |
| Energy_kWh | pilot + stress | Потребление электроэнергии (криогенный синтез, ISO Class 3 чистые комнаты, глубокий вакуум) | kWh | Energy Cost, Energy Intensity | >= 0 | >= 0 | ProductionData.energy_kwh |
| Energy_Cost_Rate | pilot + stress | Тариф на электроэнергию с учетом резервирования мощности | USD/kWh | Energy Cost | >= 0 | >= 0 | ProductionData.energy_cost_rate |
| Equipment_CAPEX | pilot + stress | Капитальные затраты: Cleanroom ISO 3, ректорный скид, масс-спектрометры ICP-MS, NMR-спектрометр | USD | Monthly Depreciation | >= 0 | >= 0 | ProductionData.equipment_capex |
| Amortization_Years_Economic | pilot + stress | Управленческий срок морального износа оборудования (быстрая смена узлов литографии) | years | Monthly Depreciation | > 0 | > 0 | ProductionData.amortization_years_economic |
| OPEX_Overhead | pilot + stress | Косвенные расходы: HVAC (вентиляция чистых комнат), азот 99.9999%, утилизация опасных отходов, метрология | USD/month | Total Manufacturing Cost | >= 0 | >= 0 | ProductionData.opex_overhead |
| Delay_Years | pilot + stress | Задержка квалификации фоторезиста у заказчика (Delta t = 6 месяцев) | years | TTM Penalty | >= 0 | >= 0 | ProductionData.delay_years |
| Discount_Rate | pilot + stress | Ставка дисконтирования проекта (r = 12% годовых) | ratio | TTM Penalty (CSV scenario) | > -1 | > -1 | ProductionData.discount_rate |
| Price_Erosion_Rate | pilot + stress | Темп ежегодного падения цены из-за действий конкурентов (alpha = 18% в год) | ratio | TTM Penalty (CSV scenario) | обычно >= 0 | обычно >= 0 | ProductionData.price_erosion_rate |
| Market_Horizon | pilot + stress | Полный жизненный цикл одного состава фоторезиста на рынке (T = 3 года) | years | TTM Penalty | > 0 | > 0 | ProductionData.market_horizon |
| Market_Window_Open | pilot + stress | Статус рыночного окна (1 - окно открыто, 0 - заказчик перешел на продукт конкурента) | binary | TTM Penalty | {0, 1} | {0, 1} | ProductionData.market_window_open |

## 3. Архитектура решения

`CSV → typed ProductionData → validation → Python calculators` и параллельно `CSV → Excel formulas → Excel recalculation`. Затем `MetricsHarness` сравнивает два результата; stress, visualization и reporting используют только рассчитанные объекты.

## 4. Проверка исходных данных

Comparison CSV: **PASS**.

| Check | Status |
|---|---|
| ENERGY_RATE_TRIPLED | PASS |
| FPY_75_TO_40 | PASS |
| DELAY_0_TO_0_5 | PASS |

## 5. Математические модели и размерности

| Metric | Formula | Dimension |
|---|---|---|
| FPY | First_Pass_Good_Units / Actual_Output | L/L → dimensionless |
| Final Yield | Final_Good_Units / Actual_Output | L/L → dimensionless |
| Availability | Actual_Hours / Planned_Hours | h/h → dimensionless |
| Performance | (Planned_Hours / Target_Output) × Actual_Output / Actual_Hours | (h/L)×L/h → dimensionless |
| OEE | Availability × Performance × FPY | dimensionless |
| TEEP | OEE × Planned_Hours / Calendar_Hours | dimensionless |
| Energy Intensity | Energy_kWh / Final_Good_Units | kWh/L |
| CPU | Total Manufacturing Cost / Final_Good_Units | USD/L |
| TTM penalty | 1 − discount × erosion × horizon × window | dimensionless |

## 6. Результаты Python

| Metric | Value | Unit | Status |
|---|---:|---|---|
| FPY | 0.75 | dimensionless | OK |
| Final Yield | 0.85 | dimensionless | OK |
| Availability | 0.8125 | dimensionless | OK |
| Performance | 0.974358974359 | dimensionless | OK |
| Quality | 0.75 | dimensionless | OK |
| OEE | 0.59375 | dimensionless | OK |
| Utilization | 0.666666666667 | dimensionless | OK |
| TEEP | 0.395833333333 | dimensionless | OK |
| Energy Cost | 25300 | USD/month | OK |
| Monthly Depreciation | 777777.777778 | USD/month | OK |
| Total Manufacturing Cost | 1188077.77778 | USD/month | OK |
| Mass Intensity | NOT_COMPUTABLE | kg/L | NOT_COMPUTABLE |
| Energy Intensity | 1424.14860681 | kWh/L | OK |
| Economic Intensity | 14713.0374957 | USD/L | OK |
| Raw Material Cost Proxy | 2972.13622291 | USD/L | OK |
| CPU | 14713.0374957 | USD/L | OK |

Ограничивающий фактор OEE — Quality/FPY (75%); Availability равна 81.25%, а Performance около 97.44%. TEEP ниже OEE из-за календарной загрузки 66.67%, поэтому значительная часть CAPEX не используется круглосуточно.

## 7. Excel Ground Truth

Реальный пересчёт Microsoft Excel: **COMPLETED**. Книга содержит формулы, а значения прочитаны из кэша после пересчёта.

## 8. Harness

| Metric | Excel | Python | Abs Delta | Rel Delta | Tolerance | Status | Cause |
|---|---:|---:|---:|---:|---:|---|---|
| Availability | 0.8125 | 0.8125 | 0 | 0 | 1.0e-09 | PASS |  |
| CPU | 14713.0374957 | 14713.0374957 | 0 | 0 | 1.0e-09 | PASS |  |
| Economic Intensity | 14713.0374957 | 14713.0374957 | 0 | 0 | 1.0e-09 | PASS |  |
| Energy Cost | 25300 | 25300 | 0 | 0 | 1.0e-09 | PASS |  |
| Energy Intensity | 1424.14860681 | 1424.14860681 | 0 | 0 | 1.0e-09 | PASS |  |
| FPY | 0.75 | 0.75 | 0 | 0 | 1.0e-09 | PASS |  |
| Final Yield | 0.85 | 0.85 | 0 | 0 | 1.0e-09 | PASS |  |
| Mass Intensity | NOT_COMPUTABLE | NOT_COMPUTABLE | NOT_COMPUTABLE | NOT_COMPUTABLE | 1.0e-09 | NOT_COMPUTABLE | Excel value is unavailable |
| Monthly Depreciation | 777777.777778 | 777777.777778 | 0 | 0 | 1.0e-09 | PASS |  |
| OEE | 0.59375 | 0.59375 | 0 | 0 | 1.0e-09 | PASS |  |
| Performance | 0.974358974359 | 0.974358974359 | 0 | 0 | 1.0e-09 | PASS |  |
| Quality | 0.75 | 0.75 | 0 | 0 | 1.0e-09 | PASS |  |
| Raw Material Cost Proxy | 2972.13622291 | 2972.13622291 | 0 | 0 | 1.0e-09 | PASS |  |
| TEEP | 0.395833333333 | 0.395833333333 | 0 | 0 | 1.0e-09 | PASS |  |
| TTM Penalty Assignment | 0.262859411141 | 0.262859411141 | 0 | 0 | 1.0e-09 | PASS |  |
| TTM Penalty CSV | 0.280346835817 | 0.280346835817 | 0 | 0 | 1.0e-09 | PASS |  |
| Total Manufacturing Cost | 1188077.77778 | 1188077.77778 | 0 | 0 | 1.0e-09 | PASS |  |
| Utilization | 0.666666666667 | 0.666666666667 | 0 | 0 | 1.0e-09 | PASS |  |

## 9. Граничные тесты

| Test | Status |
|---|---|
| A_FULL_SCRAP | PASS |
| B_IDEAL_FACTORY | PASS |
| C_RAW_MATERIAL_SUBSIDY | PASS |
| ZERO_TIME_DENOMINATOR | PASS |
| TTM_DELAY_ZERO | PASS |
| TTM_DELAY_AT_HORIZON | PASS |
| TTM_DELAY_AFTER_HORIZON | PASS |

## 10. Stress Test

| Metric | Baseline | Stress | Absolute Change | Relative Change | Interpretation |
|---|---:|---:|---:|---:|---|
| FPY | 0.75 | 0.4 | -0.35 | -0.466666666667 | Падение FPY отражает рост переделок и потерь первого прохода. |
| OEE | 0.59375 | 0.316666666667 | -0.277083333333 | -0.466666666667 | Снижение Quality напрямую уменьшает OEE. |
| TEEP | 0.395833333333 | 0.211111111111 | -0.184722222222 | -0.466666666667 | TEEP снижается вместе с OEE при неизменной календарной загрузке. |
| Energy Cost | 25300 | 75900 | 50600 | 2 | Трёхкратный тариф увеличивает затраты на электроэнергию. |
| Economic Intensity | 14713.0374957 | 15339.6628827 | 626.625386997 | 0.042589804259 | Рост затрат увеличивает стоимость ресурсов на литр годной продукции. |
| CPU | 14713.0374957 | 15339.6628827 | 626.625386997 | 0.042589804259 | Рост полной стоимости повышает себестоимость итогового годного литра. |
| TTM Penalty | 0 | 0.262859411141 | 0.262859411141 | NOT_COMPUTABLE | Задержка одновременно дисконтирует деньги, снижает цену и сокращает рынок. |

Падение FPY с 75% до 40% снижает OEE и TEEP. Тариф электроэнергии ×3 увеличивает Energy Cost на 50 600 USD и CPU на величину этого прироста, распределённую на 80.75 л итоговой годной продукции.
В предоставленном stress CSV `Final_Good_Units` остаётся 80.75 л, а стоимость переделки отдельным полем не задана. Поэтому само снижение FPY не увеличивает CPU в этой модели напрямую: его эффект виден в OEE/TEEP, тогда как наблюдаемый рост CPU вызван тарифом. Для монетизации переделок требуется отдельный параметр rework cost.

## 11. OPEX

Диаграмма `opex_structure.png` показывает: сырьё 25%, утилиты 20%, персонал 30%, ТОиР 15%, compliance/качество/метрология 10%. Сумма программно проверена и равна 100%.

## 12. TTM

- TTM: сценарий задания (`r=10%`, `α=15%`, `T=3`, `Δt=0.5`): **26.285941%**.
- TTM: сценарий CSV (`r=12%`, `α=18%`, `T=3`, `Δt=0.5`): **28.034684%**.
- Stress относительно baseline comparison CSV (`Δt: 0→0.5`): **26.285941%** против **0%**.

Штраф мультипликативный: задержка одновременно удешевляет будущие деньги, ускоряет ценовую эрозию, сокращает горизонт продаж и учитывает закрытие рыночного окна.

## 13. Data Quality Report

| Issue | Parameter | Severity | Effect | Action |
|---|---|---|---|---|
| Масса сырья отсутствует | Raw_Material_Mass_kg | HIGH | Mass Intensity = NOT_COMPUTABLE | Добавить массу потреблённого сырья, kg |
| Параметры TTM расходятся | Discount_Rate; Price_Erosion_Rate | MEDIUM | Разные штрафы | Показывать два сценария отдельно |
| Pilot delay не равен comparison baseline | Delay_Years | MEDIUM | Pilot нельзя считать no-delay baseline для TTM stress | Для стресс-сравнения использовать comparison CSV |

## 14. Допущения

| ID | Assumption | Reason | Impact | Source | Status |
|---|---|---|---|---|---|
| A01 | Расчётный период — месяц | 720 h = 30×24 | Monthly depreciation | CSV | Принято |
| A02 | Normative Cycle Time = Planned_Hours / Target_Output | Отдельного поля нет | Performance и OEE | Лекция + CSV | Принято |
| A03 | CPU использует Final_Good_Units | Это объём после итогового контроля | CPU и Economic Intensity | Лекция + задание | Принято |
| A04 | Actual_Output — обработанный/запущенный объём | Описание CSV и формула FPY | FPY и Final Yield | CSV + задание | Принято |

## 15. Выводы

Модель связывает физическую эффективность производства с полной стоимостью и риском задержки. Низкий FPY является главным ограничителем OEE, календарная загрузка дополнительно снижает TEEP, а высокая доля амортизации делает стоимость единицы чувствительной к объёму годной продукции. Массовая ресурсоёмкость требует дополнительного физического параметра и не заменяется стоимостной оценкой.

## 16. Итоговый checklist

- [x] CSV прочитаны и преобразованы в dataclass
- [x] Validation выполнен
- [x] FPY, OEE, TEEP, CPU и TTM рассчитаны
- [x] Mass Intensity рассмотрена как Data Gap
- [x] Excel formulas созданы
- [x] Excel пересчитан и прочитан
- [x] Harness выполнен без необъяснённых FAIL
- [x] Boundary checks выполнены
- [x] Stress CSV и comparison CSV обработаны
- [x] OPEX chart создан
- [x] Execution log и выходные CSV сформированы
- [x] Результаты не захардкожены в расчётных слоях
