"""Чистые расчётные модели без чтения файлов и записи отчётов."""
from __future__ import annotations

import math
import warnings
from typing import Sequence

import numpy as np

from .models import OutOfRelevantRangeWarning, ThermodynamicViolationError


class Units:
    """Явные преобразования базовых единиц проекта."""
    @staticmethod
    def mw_to_kw(value: float) -> float:
        return value * 1000

    @staticmethod
    def mw_to_gj_h(value: float) -> float:
        return value * 3.6

    @staticmethod
    def musd_to_usd(value: float) -> float:
        return value * 1_000_000

    @staticmethod
    def kwh_to_kj(value: float) -> float:
        return value * 3600


class OperationalExpenditureModel:
    """OPEX = Q·v + F в согласованных денежных единицах."""
    def __init__(self, variable_unit_cost: float, annual_fixed_cost: float):
        if variable_unit_cost < 0 or annual_fixed_cost < 0:
            raise ValueError("Затраты не могут быть отрицательными")
        self.variable_unit_cost = variable_unit_cost
        self.annual_fixed_cost = annual_fixed_cost

    def scenario(self, quantity: float, fixed_saving: float = 0) -> dict:
        if quantity <= 0 or fixed_saving < 0 or fixed_saving > self.annual_fixed_cost:
            raise ValueError("Некорректный выпуск или сокращение постоянных затрат")
        variable = quantity * self.variable_unit_cost
        fixed = self.annual_fixed_cost - fixed_saving
        total = variable + fixed
        return {"quantity": quantity, "variable": variable, "fixed": fixed,
                "total": total, "unit_cost": total / quantity,
                "variable_share_pct": variable / total * 100,
                "fixed_share_pct": fixed / total * 100}


class ChemicalOpexModel(OperationalExpenditureModel):
    """Потребление · тариф по каждой статье, USD/т и USD/год."""
    def __init__(self, variable_items: Sequence[tuple[float, float]], fixed_items: Sequence[float]):
        if any(s < 0 or p < 0 for s, p in variable_items):
            raise ValueError("Отрицательный расход или тариф")
        super().__init__(sum(s * p for s, p in variable_items), sum(fixed_items))


class MachineryOpexModel(OperationalExpenditureModel):
    """Дискретный OPEX в MUSD/шт и MUSD/год."""
    def __init__(self, variable_items: Sequence[float], fixed_items: Sequence[float], savings: Sequence[float]):
        if any(x < 0 for x in [*variable_items, *fixed_items, *savings]):
            raise ValueError("Отрицательные затраты")
        self.savings = sum(savings)
        if self.savings > sum(fixed_items):
            raise ValueError("Экономия больше постоянных затрат")
        super().__init__(sum(variable_items), sum(fixed_items))

    def scenario(self, quantity: float, mitigate: bool = False) -> dict:
        if not 6 <= quantity <= 14:
            warnings.warn("Выпуск вне релевантного диапазона 6–14", OutOfRelevantRangeWarning, stacklevel=2)
        return super().scenario(quantity, self.savings if mitigate else 0)

    @staticmethod
    def gross_material(net_mass: float, scrap_fraction: float) -> float:
        if net_mass < 0 or not 0 <= scrap_fraction < 1:
            raise ValueError("Масса или доля отходов вне диапазона")
        return net_mass / (1 - scrap_fraction)

    @classmethod
    def material_cost(cls, quantity: float, materials: Sequence[tuple[float, float, float]], bought_out: float) -> float:
        if quantity <= 0 or bought_out < 0 or any(p < 0 for _, p, _ in materials):
            raise ValueError("Некорректный выпуск или цена")
        return quantity * (sum(cls.gross_material(m, f) * p for m, p, f in materials) + bought_out)

    @staticmethod
    def labor_cost(quantity: float, operations: Sequence[tuple[float, float]]) -> float:
        if quantity <= 0 or any(t < 0 or r < 0 for t, r in operations):
            raise ValueError("Некорректные нормы труда")
        return quantity * sum(t * r for t, r in operations)

    @staticmethod
    def classify_wip(value: float) -> dict:
        if value < 0:
            raise ValueError("WIP не может быть отрицательным")
        return {"opex": 0.0, "working_capital": value}


class EnergyBalanceSolver:
    """Баланс стационарного аппарата и расход утилит."""
    @staticmethod
    def balance(inlet: Sequence[tuple[float, float]], outlet: Sequence[tuple[float]],
                work_kw: float = 0, heat_in_kw: float = 0, heat_loss_kw: float = 0) -> dict:
        energy_in = sum(m * h for m, h in inlet) + work_kw + heat_in_kw
        energy_out = sum(m * h for m, h in outlet) + heat_loss_kw
        residual = energy_in - energy_out
        return {"energy_in_kw": energy_in, "energy_out_kw": energy_out,
                "residual_kw": residual, "relative_error": abs(residual) / max(abs(energy_in), abs(energy_out), 1)}

    @staticmethod
    def reaction_heat(rate_kmol_s: float, enthalpy_kj_kmol: float = -46110) -> float:
        if rate_kmol_s < 0:
            raise ValueError("Отрицательная скорость реакции")
        return rate_kmol_s * -enthalpy_kj_kmol

    @staticmethod
    def cooling_water(heat_reject_kw: float, delta_t_k: float, cp_kj_kg_k: float = 4.18) -> float:
        if heat_reject_kw < 0 or delta_t_k <= 0 or cp_kj_kg_k <= 0:
            raise ValueError("Некорректные параметры охлаждения")
        return heat_reject_kw / (cp_kj_kg_k * delta_t_k)

    @staticmethod
    def steam(heat_recovery_kw: float, h_steam: float, h_bfw: float) -> float:
        if heat_recovery_kw < 0 or h_steam <= h_bfw:
            raise ValueError("Некорректная энтальпия пара")
        return heat_recovery_kw / (h_steam - h_bfw)


class ExergyAnalysisEngine:
    """Эксергия и контроль второго закона."""
    @staticmethod
    def physical(h: float, h0: float, s: float, s0: float, t0: float) -> float:
        if t0 <= 0:
            raise ValueError("Температура должна быть > 0 K")
        return (h - h0) - t0 * (s - s0)

    @staticmethod
    def chemical(fractions: Sequence[float], standard_exergies: Sequence[float], activities: Sequence[float],
                 gas_constant: float, t0: float) -> float:
        if len(fractions) != len(standard_exergies) or len(fractions) != len(activities):
            raise ValueError("Несогласованные компоненты")
        if any(a <= 0 for a in activities) or not math.isclose(sum(fractions), 1, abs_tol=1e-8) or t0 <= 0:
            raise ValueError("Некорректный состав, активность или температура")
        return sum(x * e for x, e in zip(fractions, standard_exergies)) + gas_constant * t0 * sum(x * math.log(a) for x, a in zip(fractions, activities))

    @staticmethod
    def total(physical: float, chemical: float, velocity_m_s: float = 0, elevation_m: float = 0,
              neglect_kinetic: bool = False, neglect_potential: bool = False) -> float:
        return physical + chemical + (0 if neglect_kinetic else velocity_m_s**2 / 2000) + (0 if neglect_potential else 9.81 * elevation_m / 1000)

    @staticmethod
    def heat(heat_kw: float, source_t_k: float, t0: float) -> float:
        if source_t_k <= 0 or t0 <= 0:
            raise ValueError("Температура должна быть > 0 K")
        return heat_kw * (1 - t0 / source_t_k)

    @staticmethod
    def cold(heat_kw: float, source_t_k: float, t0: float) -> float:
        return -ExergyAnalysisEngine.heat(heat_kw, source_t_k, t0)

    @staticmethod
    def gouy_stodola(t0: float, entropy_generation_kw_k: float) -> float:
        if t0 <= 0:
            raise ValueError("Температура должна быть > 0 K")
        if entropy_generation_kw_k < -1e-12:
            raise ThermodynamicViolationError("Отрицательная генерация энтропии")
        return t0 * max(0, entropy_generation_kw_k)


class SpecoCostingEngine:
    """Стоимостные балансы SPECO в USD/h и USD/GJ."""
    @staticmethod
    def validate_efficiency(eta: float) -> None:
        if not 0 < eta < 1:
            raise ValueError("Эксергетический КПД должен быть в (0, 1)")

    @staticmethod
    def product_cost(fuel_gj_h: float, fuel_cost_usd_gj: float, product_gj_h: float,
                     z_usd_h: float, loss_cost_usd_h: float = 0) -> float:
        if product_gj_h <= 0 or min(fuel_gj_h, fuel_cost_usd_gj, z_usd_h, loss_cost_usd_h) < 0:
            raise ValueError("Некорректный стоимостный баланс")
        return (fuel_gj_h * fuel_cost_usd_gj + z_usd_h - loss_cost_usd_h) / product_gj_h

    @staticmethod
    def f_rule(fuel_gj_h: float, fuel_cost_usd_gj: float, residual_gj_h: float,
               main_product_gj_h: float, z_usd_h: float) -> float:
        return SpecoCostingEngine.product_cost(fuel_gj_h, fuel_cost_usd_gj, main_product_gj_h,
                                               z_usd_h, residual_gj_h * fuel_cost_usd_gj)

    @staticmethod
    def p_rule(fuel_gj_h: float, fuel_cost_usd_gj: float, products_gj_h: Sequence[float], z_usd_h: float) -> float:
        return SpecoCostingEngine.product_cost(fuel_gj_h, fuel_cost_usd_gj, sum(products_gj_h), z_usd_h)

    @staticmethod
    def cost_balance(incoming_cost: float, z: float, outgoing_cost: float, tolerance: float = 1e-6) -> bool:
        return abs(incoming_cost + z - outgoing_cost) <= tolerance

    @staticmethod
    def exergoeconomic_factor(z_usd_h: float, fuel_cost_usd_gj: float, destruction_mw: float, loss_mw: float = 0) -> float:
        denominator = z_usd_h + fuel_cost_usd_gj * Units.mw_to_gj_h(destruction_mw + loss_mw)
        if denominator <= 0:
            raise ValueError("Нулевой знаменатель фактора")
        return z_usd_h / denominator


class SpecoMatrixSolver:
    """Решение Ax=b с диагностикой ранга и обусловленности."""
    @staticmethod
    def solve(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, dict]:
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        if a.ndim != 2 or a.shape[0] != a.shape[1] or b.shape != (a.shape[0],):
            raise ValueError("Размеры матрицы SPECO не согласованы")
        rank = int(np.linalg.matrix_rank(a))
        condition = float(np.linalg.cond(a))
        if rank != a.shape[0] or not math.isfinite(condition):
            raise ValueError("Вырожденная матрица SPECO")
        return np.linalg.solve(a, b), {"rank": rank, "condition_number": condition,
                                        "determinant": float(np.linalg.det(a)),
                                        "status": "WARNING" if condition > 1e10 else "PASS"}

    @staticmethod
    def cogeneration(fuel_gj_h: float, fuel_cost: float, steam_gj_h: float,
                     electricity_gj_h: float, z_usd_h: float, rule: str) -> tuple[dict, dict]:
        total = fuel_gj_h * fuel_cost + z_usd_h
        if rule == "F":
            a = np.array([[steam_gj_h, electricity_gj_h], [1, 0]], float)
            b = np.array([total, fuel_cost], float)
        elif rule == "P":
            a = np.array([[steam_gj_h, electricity_gj_h], [1, -1]], float)
            b = np.array([total, 0], float)
        else:
            raise ValueError("Неизвестное правило SPECO")
        values, diagnostics = SpecoMatrixSolver.solve(a, b)
        return {"steam_cost_usd_gj": float(values[0]), "electricity_cost_usd_gj": float(values[1])}, diagnostics


class SequentialChainAnalyzer:
    """Линейные коэффициенты cP=A·cF1+B для последовательной цепочки."""
    @staticmethod
    def escalation_factor(efficiencies: Sequence[float]) -> float:
        for eta in efficiencies:
            SpecoCostingEngine.validate_efficiency(eta)
        return math.prod(1 / eta for eta in efficiencies)

    @staticmethod
    def analyze(stages: Sequence, degradation_index: int | None = None) -> dict:
        if not stages:
            raise ValueError("Пустая цепочка")
        efficiencies = [float(s.efficiency) for s in stages]
        if degradation_index is not None:
            efficiencies[degradation_index] *= .95
        fuel = float(stages[0].fuel_mw)
        a, b = 1.0, 0.0
        rows = []
        for stage, eta in zip(stages, efficiencies):
            SpecoCostingEngine.validate_efficiency(eta)
            product = fuel * eta
            destruction = fuel - product
            a = a / eta
            b = b / eta + stage.z_usd_h / Units.mw_to_gj_h(product)
            rows.append({"number": stage.number, "name": stage.name, "fuel_mw": fuel,
                         "product_mw": product, "destruction_mw": destruction,
                         "efficiency": eta, "z_usd_h": stage.z_usd_h,
                         "cost_coefficient_a": a, "cost_increment_usd_gj": b})
            fuel = product
        return {"rows": rows, "amplification": a, "capital_increment_usd_gj": b,
                "outlet_mw": fuel, "status": "PARTIALLY_CALCULATED"}


class ParallelCompressorsOptimizer:
    """Аналитический и независимый численный минимум мощности."""
    def __init__(self, values: dict):
        self.values = values

    def calculate(self) -> dict:
        d = self.values
        total = float(d["Total_Mass_Flow_kg_s"])
        tariff = float(d["Electricity_Tariff_USD_per_kWh"])
        hours = float(d["Annual_Operating_Hours"])
        one, two = d["Compressor_1_Piston"], d["Compressor_2_Screw_VFD"]
        b1, c1 = float(one["w_base_kJ_kg"]), float(one["w_coeff_kJ_s_kg2"])
        b2, c2 = float(two["w_base_kJ_kg"]), float(two["w_coeff_kJ_s_kg2"])
        fixed = float(one["Hourly_Opex_Fix_Z1_USD_per_h"]) + float(two["Hourly_Opex_Fix_Z2_USD_per_h"])
        if total <= 0 or tariff < 0 or hours <= 0 or c1 + c2 <= 0:
            raise ValueError("Некорректные параметры компрессоров")

        def power(m1: float) -> float:
            m2 = total - m1
            return m1 * (b1 + c1 * m1) + m2 * (b2 + c2 * m2)

        analytical = min(total, max(0, (b2 + 2 * c2 * total - b1) / (2 * (c1 + c2))))
        try:
            from scipy.optimize import minimize_scalar
            numerical = float(minimize_scalar(power, bounds=(0, total), method="bounded", options={"xatol": 1e-12}).x)
            method = "scipy.optimize.minimize_scalar"
        except ImportError:
            # Независимый численный метод при отсутствии необязательной зависимости.
            left, right = 0., total
            ratio = (math.sqrt(5) - 1) / 2
            for _ in range(100):
                x, y = right - ratio * (right - left), left + ratio * (right - left)
                if power(x) < power(y):
                    right = y
                else:
                    left = x
            numerical = (left + right) / 2
            method = "golden-section"
        equal = total / 2
        eq_power, opt_power = power(equal), power(analytical)
        eq_cost, opt_cost = eq_power * tariff + fixed, opt_power * tariff + fixed
        return {"equal_m1": equal, "equal_m2": equal, "equal_power_kw": eq_power,
                "equal_cost_usd_h": eq_cost, "optimal_m1": analytical, "optimal_m2": total - analytical,
                "optimal_power_kw": opt_power, "optimal_cost_usd_h": opt_cost,
                "numeric_m1": numerical, "numeric_power_kw": power(numerical),
                "numeric_method": method, "hourly_savings": eq_cost - opt_cost,
                "annual_savings": (eq_cost - opt_cost) * hours}


class HeatExchangerOptimizer:
    """TAC для заданного k; без k проектный минимум не вычисляется."""
    def __init__(self, values: dict, crf: float, annual_hours: float):
        self.values, self.crf, self.annual_hours = values, crf, annual_hours

    def calculate(self, k_gj_per_h_k: float | None = None) -> dict:
        if k_gj_per_h_k is None:
            return {"status": "SKIPPED_MISSING_INPUT", "missing": "k_gj_per_h_k для Ex_dest = k·DeltaT"}
        d = self.values
        base = float(d["Base_Temperature_Difference_DeltaT_base_K"])
        capex = float(d["Base_CAPEX_C0_USD"])
        beta = float(d["Cost_Scaling_Exponent_Beta"])
        fuel_cost = float(d["Fuel_Exergy_Cost_cF_USD_per_GJ"])
        low, high = float(d["Min_Search_DeltaT_K"]), float(d["Max_Search_DeltaT_K"])
        if k_gj_per_h_k < 0 or low <= 0 or high <= low or not .8 <= beta <= 1 or self.crf <= 0 or self.annual_hours <= 0:
            raise ValueError("Некорректные параметры теплообменника")

        def components(delta: float) -> tuple[float, float, float]:
            annual_capex = self.crf * capex * (base / delta) ** beta
            annual_loss = self.annual_hours * fuel_cost * k_gj_per_h_k * delta
            return annual_capex, annual_loss, annual_capex + annual_loss

        if k_gj_per_h_k == 0:
            optimum = high
        else:
            optimum = (beta * self.crf * capex * base**beta / (self.annual_hours * fuel_cost * k_gj_per_h_k)) ** (1 / (beta + 1))
            optimum = min(high, max(low, optimum))
        points = [{"delta_t_k": float(x), "annual_capex_usd": components(float(x))[0],
                   "annual_loss_usd": components(float(x))[1], "tac_usd": components(float(x))[2]}
                  for x in np.linspace(low, high, 40)]
        c, o, t = components(optimum)
        return {"status": "CALCULATED", "optimum_delta_t_k": optimum,
                "annual_capex_usd": c, "annual_loss_usd": o, "tac_usd": t, "points": points}
