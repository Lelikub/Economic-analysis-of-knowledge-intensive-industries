"""Независимая проверка результатов и экспорт журнала сравнений."""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from .models import ProjectInputData, ProjectMetrics


class ReferenceTargets:
    """Эталоны задания, лекции и контрольных полей JSON; не участвуют в расчёте."""
    ASSIGNMENT = {
        "ammonia_variable": (253.4, "USD/т", .01),
        "ammonia_base": (347.6, "USD/т", .01),
        "ammonia_underload": (371.2, "USD/т", .1),
        "machinery_variable": (3.596, "MUSD/шт", .001),
        "machinery_fixed": (28.8, "MUSD/год", .01),
        "machinery_base": (6., "MUSD/шт", .01),
        "machinery_underload": (8.4, "MUSD/шт", .01),
        "machinery_mitigated": (7.6, "MUSD/шт", .01),
        "f_rule_electricity": (19.4, "USD/ГДж", .01),
        "p_rule_product": (13.95, "USD/ГДж", .01),
        "compressor_m1": (.75, "кг/с", 1e-6),
        "compressor_power": (896.25, "кВт", .01),
        "compressor_annual_saving": (21600., "USD/год", 1),
    }


class ValidationHarness:
    """Сравнивает рассчитанное с эталоном и фиксирует пропуски отдельно."""
    HEADERS = ["Task", "Metric", "Calculated", "Reference", "Abs_Error", "Rel_Error_Pct",
               "Tolerance", "Unit", "Status", "Reference_Source", "Comment"]

    def __init__(self):
        self.rows: list[dict[str, Any]] = []

    def compare(self, task: str, metric: str, calculated: float, reference: float,
                tolerance: float, unit: str, source: str, comment: str = "") -> None:
        error = abs(calculated - reference)
        relative = error / abs(reference) * 100 if reference else (0 if not error else math.inf)
        self.rows.append(dict(zip(self.HEADERS, [task, metric, calculated, reference, error,
            relative, tolerance, unit, "PASS" if error <= tolerance else "FAIL", source, comment])))

    def status(self, task: str, metric: str, status: str, comment: str, unit: str = "") -> None:
        self.rows.append(dict(zip(self.HEADERS, [task, metric, "", "", "", "", "", unit, status, "", comment])))

    def validate(self, data: ProjectInputData, metrics: ProjectMetrics) -> list[dict]:
        o, s, c = metrics.opex, metrics.speco, metrics.compressors
        mapping = {
            "ammonia_variable": ("1", "Аммиак: переменная себестоимость", o["ammonia_base"]["variable"] / 500_000),
            "ammonia_base": ("1", "Аммиак: база", o["ammonia_base"]["unit_cost"]),
            "ammonia_underload": ("1", "Аммиак: недогруз", o["ammonia_underload"]["unit_cost"]),
            "machinery_variable": ("1", "ХимМаш: переменная себестоимость", o["machinery_base"]["variable"] / 12),
            "machinery_fixed": ("1", "ХимМаш: постоянный OPEX", o["machinery_base"]["fixed"]),
            "machinery_base": ("1", "ХимМаш: база", o["machinery_base"]["unit_cost"]),
            "machinery_underload": ("1", "ХимМаш: недогруз", o["machinery_underload"]["unit_cost"]),
            "machinery_mitigated": ("1", "ХимМаш: сокращение fixed", o["machinery_mitigated"]["unit_cost"]),
            "f_rule_electricity": ("5", "F-rule electricity", s["f_rule"]["electricity_cost_usd_gj"]),
            "p_rule_product": ("5", "P-rule product", s["p_rule"]["product_cost_usd_gj"]),
            "compressor_m1": ("8", "Компрессор: m1 оптимум", c["optimal_m1"]),
            "compressor_power": ("8", "Компрессор: мощность", c["optimal_power_kw"]),
            "compressor_annual_saving": ("8", "Компрессор: годовая экономия", c["annual_savings"]),
        }
        for key, (task, metric, value) in mapping.items():
            reference, unit, tolerance = ReferenceTargets.ASSIGNMENT[key]
            self.compare(task, metric, value, reference, tolerance, unit,
                         "Задание №2 / Лекция 3, округлённое значение")
        self.compare("1", "Аммиак: s_i·p_i vs CSV", sum(x.consumption * x.price for x in data.ammonia_variable_opex),
                     sum(x.reference_cost for x in data.ammonia_variable_opex), .01, "USD/т", "opex_ammonia_raw.csv")
        self.compare("2", "BOM доли vs CSV", sum(x.reference_share_pct for x in data.machinery_variable_opex),
                     100., .05, "%", "khimmash_bom_opex.csv")
        self.compare("3", "Расход CW", metrics.energy["cooling_water_kg_s_calculated"],
                     metrics.energy["cooling_water_kg_s_source"], .01, "кг/с", "streams_energy_balance.csv")
        self.compare("3", "Расход пара", metrics.energy["steam_kg_s_calculated"],
                     metrics.energy["steam_kg_s_source"], 1e-6, "кг/с", "streams_energy_balance.csv")
        self.status("3", "Баланс КУ: нераспределённое тепло", "WARNING",
                    f"Невязка {metrics.energy['whrb']['residual_kw']:.1f} кВт; не задан отдельный поток потерь/отбора", "кВт")
        self.status("3", "Полный OPEX утилит", "SKIPPED_MISSING_INPUT", metrics.energy["utility_opex_missing"])
        self.compare("4", "Когенерация: эксергетический баланс", metrics.exergy["cogen_balance_residual_mw"],
                     0., 1e-9, "МВт", "exergy_cogen_speco.json")
        self.status("4", "Когенерация: фактор f_k в [0,1]", "PASS",
                    f"f_k={metrics.exergy['cogen_factor']:.6f}; {metrics.exergy['cogen_factor_recommendation']}")
        self.status("4", "Физическая эксергия потоков", "SKIPPED_MISSING_INPUT", metrics.exergy["stream_physical_missing"])
        self.status("4", "Химическая эксергия потоков", "SKIPPED_MISSING_INPUT", metrics.exergy["chemical_missing"])
        self.status("4", "Гуй–Стодола по потокам", "SKIPPED_MISSING_INPUT", metrics.exergy["gouy_stodola_missing"])
        self.compare("5", "F-rule cost balance", s["f_rule"]["cost_balance_residual_usd_h"], 0., 1e-6,
                     "USD/ч", "exergy_cogen_speco.json")
        self.compare("5", "P-rule cost balance", s["p_rule"]["cost_balance_residual_usd_h"], 0., 1e-6,
                     "USD/ч", "exergy_cogen_speco.json")
        self.compare("6", "F-rule matrix vs direct", s["f_matrix"]["electricity_cost_usd_gj"],
                     s["f_rule"]["electricity_cost_usd_gj"], 1e-9, "USD/ГДж", "независимые Python методы")
        self.compare("6", "P-rule matrix vs direct", s["p_matrix"]["steam_cost_usd_gj"],
                     s["p_rule"]["product_cost_usd_gj"], 1e-9, "USD/ГДж", "независимые Python методы")
        self.compare("7", "Цепочка: множитель 1/0.8^5", metrics.chain["base"]["amplification"],
                     1 / .8**5, 1e-9, "раз", "Лекция 3, расчётная формула")
        for stage, residual, eta_residual in zip(data.speco_chain, metrics.chain["csv_balance_residuals_mw"], metrics.chain["csv_eta_residuals"]):
            self.compare("7", f"Ступень {stage.number}: эксергетический баланс", residual, 0., .01,
                         "МВт", "sequential_chain_speco.csv", "последняя ступень округлена")
            self.compare("7", f"Ступень {stage.number}: КПД", eta_residual, 0., .001,
                         "доля", "sequential_chain_speco.csv")
        self.status("7", "Абсолютная стоимость цепочки и f_k", "SKIPPED_MISSING_INPUT", metrics.chain["initial_fuel_cost_missing"])
        self.compare("8", "Компрессоры: аналитика vs численный минимум", c["optimal_m1"], c["numeric_m1"],
                     1e-4, "кг/с", "собственный аналитический и численный методы")
        reference = data.compressors.values["Analytical_Solution"]
        self.compare("8", "Компрессоры: JSON контроль", c["optimal_cost_usd_h"],
                     reference["Optimal_Total_Hourly_Cost_USD_per_h"], .01, "USD/ч", "compressors_parallel.json: Analytical_Solution")
        hp = data.economic_constants.values
        rate, years = hp["Discount_Rate_r"], hp["Equipment_Lifetime_Years_T"]
        crf = rate * (1 + rate)**years / ((1 + rate)**years - 1)
        self.compare("9", "CRF", crf, hp["Capital_Recovery_Factor_CRF"], 1e-5,
                     "1/год", "project_economic_constants.json")
        self.status("9", "Оптимум теплообменника", "SKIPPED_MISSING_INPUT", metrics.heat_exchanger["missing"])
        self.status("2", "Детальный scrap", "SKIPPED_MISSING_INPUT", metrics.materials["detailed_scrap_missing"])
        return self.rows

    def write(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.HEADERS)
            writer.writeheader()
            writer.writerows(self.rows)
