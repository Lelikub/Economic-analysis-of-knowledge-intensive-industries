# Аудит источников и трассировка

Приоритет: PDF задания → первичные данные → лекция 7 → совместимые решения работ 1–3.
Все 10 страниц задания и 28 страниц лекции просмотрены через pypdf. Изучены архитектура/README работ 1 и 3, Harness работы 2, структура тестов и результатов. Численные модели других работ не переносились.

| Источник / страницы | Формула или требование, переменные и размерность | Реализация | Независимая проверка | Артефакт / раздел Word |
|---|---|---|---|---|
| `4/data/Задание_к_практическому_занятию_4_ЭА.pdf`, с.2–5; лекция 7 с.7–9 | Freight=ΣD·T·V; D км, T USD/(т·км), V т; результат USD | calculators/tco.py, MultimodalTCOSimulator | test_tco_independent, Harness Decimal | tco_baseline.csv, route_legs.csv / §3 |
| Задание с.4; лекция с.8–9 | C_inv=V·P·WACC·Σt/365; P USD/т, t сутки, WACC доля/год | calculators/tco.py | Decimal; test_zero_wacc, test_sensitivity | wacc/cargo_value/lead_time.csv / §3.1–3.3 |
| Задание с.3–4; лекция с.7–8 | C_ins=V·P·r; C_risk=p·L; упаковка фиксирована, USD | calculators/tco.py | p=0 и 1, сумма компонент | metrics.json / §2.1,3 |
| Задание с.4; лекция с.10–11 | E=ΣD·E_m·10⁻⁶, т CO2/т; CBAM=max(0,SEE+E−benchmark)·V·(ETS−origin), EUR; курс USD/EUR | CBAMCalculator | test_cbam_below_benchmark; отрицательный спред; независимый Decimal и курс | tco_baseline.csv / §2.1,3 |
| Задание с.5,10 | Линейные зависимости: WACC 5–30%, P 20–500 тыс., t_sea_total 10–120; ETS при P150–300 тыс. | calculators/sensitivity.py | Подстановка корней + смена знака; NO_CROSSING_IN_RANGE | break_even.csv, ets_thresholds.csv / §3,6.1–6.2 |
| Задание с.6; лекция с.19 | min ΣF y+Σc x, руб./год; спрос/мощность т/год, тариф руб./т | CFLPCalculator.solve | балансы; 16 открытий + scipy.optimize.linprog (HiGHS) | flows_multi.csv, residuals_multi.csv / §4.1 |
| Задание с.6–7; лекция с.23 | z бинарны; x=d·z; Σz=1; z≤y | CFLPCalculator(single=True) | полный перебор 4⁵=1024 назначений; binary/link остатки | flows_single.csv, residuals_single.csv / §4.2 |
| Задание с.7; лекция с.23 | K заменяется M=10⁹; y ослабляется в [0,1]; gap=abs(Zmilp−Zlp)/abs(Zmilp)·100% | CFLPService и калькулятор | LP lower bound, независимая физическая перегрузка, 3 времени | cflp_comparison.csv, solver_timings.csv / §4.4 |
| Задание с.2–3,8 | T∈[−22,−18] °C; непрерывный эпизод >30 мин; 540–548 | TelemetryCalculator | регрессия 45 мин; ровно 30 против 35; пропуск; границы | temperature_incidents.csv / §5.1 |
| Задание с.3,8 | norm=sqrt(ax²+ay²+az²); shock при abs(любой оси)>2.5g | TelemetryCalculator | индекс920; норма не заменяет ось; ±2.5/2.5001 | shock_incidents.csv / §5.2 |
| Задание с.8–9 | Тот же Rail_Express: p=.005→1; риск 1.2млн USD | TelemetryService + исходный simulator | test_integration_trigger; Δ=(1−p0)L | dynamic_tco.csv, DPP / §5.4 |
| Задание с.9 | Haversine; R=6371.0088 км; Scope3=D·Erail·10⁻⁶·V, тCO2 | telemetry.py; TelemetryService | независимая сферическая формула косинусов; тест1° | gps_segments.csv / §5.3 |
| Задание с.9–10; лекция с.28 | SHA-256 исходных байт; обязательные ключи DPP | PassportService | hashlib.file_digest и schema/type tests | dpp_passport.json / §5.4 |
| Задание с.10, раздел3 | Harness; проверка ошибок, фактические запуски | harness.py, orchestrator.py | pytest/JUnit, append-only CSV/MD | logs/, test_results.json / §7 |
| Задание с.10, вопросы1–3 | Капитал, ETS, сенсоры и ERP | sensitivity.py, analysis.py, reporting.py | количественные пороги и анализ граничных случаев | analysis.json, Word / §6 |
| Промт разделы9–10 | Таблица → рисунок → анализ; 200dpi, русский Word | plotting.py, reporting.py | тесты артефактов, bbox, CRC/XML, рендер при доступности | 12 PNG, plot_validation.json, Word |

Библиотека SciPy используется для независимого решателя HiGHS, а не вместо обязательного CBC. Pillow проверяет PNG, lxml — XML, pypdf — источники и PDF-рендер. Общий шаблон DOCX используется как источник стилей, секций и оформления; его исходный файл не меняется. Служебные тексты заменены содержательными результатами.

RAR: содержимое пяти первичных файлов прочитано через `7z x -so`, SHA-256 сравнен с `4/data` без создания дубликатов. Результат — `output/archive_comparison.json`. Полные хэши всех исходных файлов — `output/run_manifest.json`.
