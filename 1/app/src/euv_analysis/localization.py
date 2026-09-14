"""Russian presentation labels for exported reports and workbooks."""

from __future__ import annotations


SHEET_NAMES: dict[str, str] = {
    "source": "Исходные данные",
    "metrics": "Метрики",
    "costs": "Затраты",
    "ttm": "TTM",
    "stress": "Стресс-тест",
    "harness": "Журнал сверки",
    "opex": "Структура OPEX",
    "assumptions": "Допущения",
    "issues": "Проблемы данных",
}

PARAMETER_LABELS: dict[str, str] = {
    "Calendar_Hours": "Календарное время",
    "Planned_Hours": "Плановое время работы",
    "Actual_Hours": "Фактическое время работы",
    "Target_Output": "Плановый выпуск",
    "Actual_Output": "Фактический выпуск",
    "First_Pass_Good_Units": "Годный объём первого прохода",
    "Final_Good_Units": "Итоговый годный объём",
    "Raw_Material_Cost": "Затраты на сырьё",
    "Energy_kWh": "Потребление электроэнергии",
    "Energy_Cost_Rate": "Тариф на электроэнергию",
    "Equipment_CAPEX": "Капитальная стоимость оборудования",
    "Amortization_Years_Economic": "Экономический срок амортизации",
    "OPEX_Overhead": "Накладные операционные расходы",
    "Delay_Years": "Задержка вывода на рынок",
    "Discount_Rate": "Ставка дисконтирования",
    "Price_Erosion_Rate": "Темп ценовой эрозии",
    "Market_Horizon": "Рыночный горизонт",
    "Market_Window_Open": "Открытость рыночного окна",
}

PARAMETER_DESCRIPTIONS: dict[str, str] = {
    "Calendar_Hours": "Общее календарное время расчётного периода",
    "Planned_Hours": "Запланированное время работы оборудования",
    "Actual_Hours": "Фактическое время работы оборудования",
    "Target_Output": "Плановый объём выпуска",
    "Actual_Output": "Фактически обработанный объём",
    "First_Pass_Good_Units": "Объём, прошедший контроль с первого раза",
    "Final_Good_Units": "Итоговый годный объём после переделки",
    "Raw_Material_Cost": "Стоимость использованных сырья и материалов",
    "Energy_kWh": "Потребление электроэнергии за период",
    "Energy_Cost_Rate": "Стоимость одного киловатт-часа",
    "Equipment_CAPEX": "Первоначальная стоимость оборудования",
    "Amortization_Years_Economic": "Экономический срок службы оборудования",
    "OPEX_Overhead": "Накладные операционные расходы за период",
    "Delay_Years": "Задержка выхода продукта на рынок",
    "Discount_Rate": "Годовая ставка дисконтирования",
    "Price_Erosion_Rate": "Годовой темп снижения рыночной цены",
    "Market_Horizon": "Доступный горизонт продаж",
    "Market_Window_Open": "Признак открытого рыночного окна",
}

METRIC_LABELS: dict[str, str] = {
    "FPY": "Выход годных с первого прохода (FPY)",
    "Final Yield": "Итоговый выход годных",
    "Availability": "Доступность оборудования",
    "Performance": "Производительность оборудования",
    "Quality": "Коэффициент качества",
    "OEE": "Общая эффективность оборудования (OEE)",
    "Utilization": "Использование календарного времени",
    "TEEP": "Полная эффективная производительность оборудования (TEEP)",
    "Energy Cost": "Затраты на электроэнергию",
    "Monthly Depreciation": "Ежемесячная амортизация",
    "Total Manufacturing Cost": "Общие производственные затраты",
    "Mass Intensity": "Массовая ресурсоёмкость",
    "Energy Intensity": "Энергетическая ресурсоёмкость",
    "Economic Intensity": "Экономическая ресурсоёмкость",
    "Raw Material Cost Proxy": "Стоимостной показатель сырья",
    "CPU": "Себестоимость единицы продукции (CPU)",
    "TTM Penalty Assignment": "Штраф TTM по параметрам задания",
    "TTM Penalty CSV": "Штраф TTM по параметрам CSV",
    "TTM Penalty": "Штраф за задержку вывода на рынок (TTM)",
}

UNIT_LABELS: dict[str, str] = {
    "hours": "ч",
    "h": "ч",
    "L": "л",
    "USD": "долл. США",
    "kWh": "кВт·ч",
    "USD/kWh": "долл. США/кВт·ч",
    "USD/month": "долл. США/месяц",
    "years": "лет",
    "ratio": "доля",
    "binary": "0 или 1",
    "dimensionless": "безразмерная величина",
    "kWh/L": "кВт·ч/л",
    "USD/L": "долл. США/л",
    "kg/L": "кг/л",
}

STATUS_LABELS: dict[str, str] = {
    "PASS": "СОВПАДАЕТ",
    "FAIL": "РАСХОЖДЕНИЕ",
    "NOT_COMPUTABLE": "НЕ РАССЧИТЫВАЕТСЯ",
    "OK": "РАССЧИТАНО",
    "COMPLETED": "ВЫПОЛНЕН",
    "UNAVAILABLE": "НЕДОСТУПЕН",
}

SCENARIO_LABELS: dict[str, str] = {
    "Baseline": "Базовый",
    "Stress": "Стрессовый",
    "Assignment": "Параметры задания",
    "CSV": "Параметры CSV",
    "Stress Baseline": "Базовый для стресс-теста",
}

CAUSE_LABELS: dict[str, str] = {
    "Excel value is unavailable": "Значение Excel недоступно",
    "Python value is unavailable": "Значение Python недоступно",
    "Formula, input, or cached Excel value differs": (
        "Различаются формула, исходные данные или кэшированное значение Excel"
    ),
}


def localize_unit(value: str) -> str:
    """Return a Russian unit label while preserving unknown technical units."""
    return UNIT_LABELS.get(value, value)


def localize_metric(value: str) -> str:
    """Return a Russian metric label while preserving unknown metric keys."""
    return METRIC_LABELS.get(value, value)


def localize_status(value: str) -> str:
    """Return a Russian display status while keeping internal status stable."""
    return STATUS_LABELS.get(value, value)


def localize_cause(value: str) -> str:
    """Translate a known harness cause without obscuring unexpected diagnostics."""
    return CAUSE_LABELS.get(value, value)

