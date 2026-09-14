# EUV Photoresist Production Analysis

Воспроизводимый Python-pipeline для практического занятия № 1 по экономическому анализу наукоёмких производств.

## Требования

- Windows с установленным Microsoft Excel;
- Python 3.14 и проектное окружение `.venv` в корне репозитория;
- входные CSV в `1/data`.

## Установка

Из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\1\app\requirements.txt
```

## Единая команда запуска

Из каталога `1/app`:

```powershell
..\..\.venv\Scripts\python.exe .\main.py
```

Все стадии выполняются программно через этот Python-интерпретатор. Excel запускается скрыто из Python как независимый движок пересчёта формул; ручная подстановка результатов не используется.

## Тесты

Из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m pytest .\1\app\tests -v -p no:cacheprovider
```

Тесты с маркером `excel` запускают установленный Microsoft Excel. Чтобы проверить только чистую Python-логику:

```powershell
.\.venv\Scripts\python.exe -m pytest .\1\app\tests -m "not excel" -v -p no:cacheprovider
```

## Результаты

- `output/ground_truth.xlsx` — Excel Ground Truth с формулами и кэшированными значениями после реального пересчёта;
- `output/harness_log.csv` — сравнение Excel и Python;
- `output/stress_comparison.csv` — baseline/stress;
- `output/opex_structure.png` — структура OPEX;
- `output/report.md` — итоговый аналитический отчёт;
- `logs/execution.log` — хронология pipeline.

## Политика данных

- FPY и Final Yield не смешиваются.
- TTM-параметры задания и CSV рассчитываются как отдельные сценарии.
- Массовая ресурсоёмкость имеет статус `NOT_COMPUTABLE`, поскольку в CSV нет массы потреблённого сырья. `Raw Material Cost Proxy` — отдельный стоимостной показатель, а не замена физической массы.
- При недоступности Excel книга с формулами сохраняется, но harness не получает фиктивный PASS.

Архитектура и допущения описаны в [`../data/ARCH.md`](../data/ARCH.md).
