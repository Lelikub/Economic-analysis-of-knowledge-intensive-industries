"""Последовательный расчёт показателей проекта из типизированных входов."""
from __future__ import annotations

from .calculations import (
    ChemicalOpexModel, EnergyBalanceSolver, HeatExchangerOptimizer,
    MachineryOpexModel, ParallelCompressorsOptimizer, SequentialChainAnalyzer,
    SpecoCostingEngine, SpecoMatrixSolver, Units,
)
from .models import ProjectInputData, ProjectMetrics


class ProjectMetricsCalculator:
    """Создаёт один объект результатов; контрольные значения не используются."""
    def __init__(self, data: ProjectInputData):
        self.data = data

    def calculate(self) -> ProjectMetrics:
        d = self.data
        result = ProjectMetrics()
        ammonia = ChemicalOpexModel(
            [(x.consumption, x.price) for x in d.ammonia_variable_opex],
            [Units.musd_to_usd(x.annual_musd) for x in d.ammonia_fixed_opex])
        machinery = MachineryOpexModel(
            [x.per_unit_musd for x in d.machinery_variable_opex],
            [x.annual_musd for x in d.machinery_fixed_opex],
            [x.saving_musd if x.is_step_fixed else 0 for x in d.machinery_fixed_opex])
        a0, a1 = ammonia.scenario(500_000), ammonia.scenario(400_000)
        m0, m1, m2 = machinery.scenario(12), machinery.scenario(6), machinery.scenario(6, mitigate=True)
        result.opex = {"ammonia_base": a0, "ammonia_underload": a1,
                       "machinery_base": m0, "machinery_underload": m1,
                       "machinery_mitigated": m2,
                       "ammonia_unit_change_pct": (a1["unit_cost"] / a0["unit_cost"] - 1) * 100,
                       "machinery_unit_change_pct": (m1["unit_cost"] / m0["unit_cost"] - 1) * 100}
        bom_material = next(x.per_unit_musd for x in d.machinery_variable_opex if "Материалы" in x.name)
        bought_out = next(x.per_unit_musd for x in d.machinery_variable_opex if "Покупные" in x.name)
        labor = next(x.per_unit_musd for x in d.machinery_variable_opex if "труд" in x.name)
        result.materials = {"aggregate_bom_per_unit_musd": bom_material,
                            "aggregate_bought_out_per_unit_musd": bought_out,
                            "aggregate_labor_per_unit_musd": labor,
                            "aggregate_materials_annual_musd": 12 * (bom_material + bought_out),
                            "aggregate_labor_annual_musd": 12 * labor,
                            "detailed_scrap_status": "SKIPPED_MISSING_INPUT",
                            "detailed_scrap_missing": "m_net,i; f_scrap,i; p_i по материалам",
                            "wip_treatment": "Working Capital; не входит в OPEX"}

        s = {x.stream_id: x for x in d.energy_streams}
        gas_hot, gas_cold = s["STR-04"], s["STR-05"]
        steam, bfw = s["STR-06"], s["STR-07"]
        cw_in, cw_out = s["STR-08"], s["STR-09"]
        whrb = EnergyBalanceSolver.balance(
            [(gas_hot.mass_kg_s, gas_hot.enthalpy_kj_kg), (bfw.mass_kg_s, bfw.enthalpy_kj_kg)],
            [(gas_cold.mass_kg_s, gas_cold.enthalpy_kj_kg), (steam.mass_kg_s, steam.enthalpy_kj_kg)])
        gas_heat = gas_hot.mass_kg_s * (gas_hot.enthalpy_kj_kg - gas_cold.enthalpy_kj_kg)
        steam_heat = steam.mass_kg_s * (steam.enthalpy_kj_kg - bfw.enthalpy_kj_kg)
        cw_heat = cw_in.mass_kg_s * (cw_out.enthalpy_kj_kg - cw_in.enthalpy_kj_kg)
        cw_calc = EnergyBalanceSolver.cooling_water(cw_heat, cw_out.temperature_c - cw_in.temperature_c)
        steam_calc = EnergyBalanceSolver.steam(steam_heat, steam.enthalpy_kj_kg, bfw.enthalpy_kj_kg)
        tariff = d.economic_constants.values["Tariffs_and_Market_Prices"]
        annual_hours = d.economic_constants.values["Annual_Work_Hours_tau_a"]
        potential_credit = steam.mass_kg_s * 3.6 * tariff["High_Pressure_Steam_Export_Credit_USD_per_ton"]
        result.energy = {"streams": [{"id": x.stream_id, "name": x.name, "mass_kg_s": x.mass_kg_s,
                                        "h_kj_kg": x.enthalpy_kj_kg, "energy_kw": x.mass_kg_s * x.enthalpy_kj_kg}
                                       for x in d.energy_streams],
                         "whrb": whrb, "gas_heat_release_kw": gas_heat,
                         "steam_duty_kw": steam_heat, "unallocated_heat_kw": gas_heat - steam_heat,
                         "cooling_water_heat_kw": cw_heat, "cooling_water_kg_s_calculated": cw_calc,
                         "cooling_water_kg_s_source": cw_in.mass_kg_s,
                         "steam_kg_s_calculated": steam_calc, "steam_kg_s_source": steam.mass_kg_s,
                         "potential_steam_credit_usd_h": potential_credit,
                         "potential_steam_credit_usd_year": potential_credit * annual_hours,
                         "utility_opex_status": "SKIPPED_MISSING_INPUT",
                         "utility_opex_missing": "W_el аммиачного завода; расход покупного пара; подтверждённый экспорт выработанного пара",
                         "status": "PARTIALLY_CALCULATED"}

        c = d.cogeneration.values
        fuel = c["High_Pressure_Steam_Inlet"]
        lp = c["Low_Pressure_Steam_Outlet"]
        el = c["Electrical_Shaft_Power_Outlet"]
        destruction = c["Exergy_Destruction_MW"]
        fuel_mw = fuel["Exergy_Power_MW"]
        balance_residual = fuel_mw - lp["Exergy_Power_MW"] - el["Exergy_Power_MW"] - destruction
        result.exergy = {"cogen_fuel_mw": fuel_mw, "cogen_products_mw": lp["Exergy_Power_MW"] + el["Exergy_Power_MW"],
                         "cogen_destruction_mw": destruction, "cogen_efficiency": (lp["Exergy_Power_MW"] + el["Exergy_Power_MW"]) / fuel_mw,
                         "cogen_balance_residual_mw": balance_residual,
                         "stream_physical_status": "SKIPPED_MISSING_INPUT",
                         "stream_physical_missing": "h0, s0 для каждого состава потока при T0, P0",
                         "chemical_status": "SKIPPED_MISSING_INPUT",
                         "chemical_missing": "x_i, a_i, стандартные химические эксергии",
                         "gouy_stodola_status": "SKIPPED_MISSING_INPUT",
                         "gouy_stodola_missing": "полный энтропийный баланс и температуры обмена теплом"}

        fuel_flow, fuel_cost = fuel["Exergy_Flow_GJ_per_h"], fuel["Specific_Cost_USD_per_GJ"]
        steam_flow, electricity_flow = lp["Exergy_Flow_GJ_per_h"], el["Exergy_Flow_GJ_per_h"]
        z = c["Capital_and_Opex_Fix_Rate_Z_USD_per_h"]
        cogen_factor = SpecoCostingEngine.exergoeconomic_factor(z, fuel_cost, destruction)
        if not 0 <= cogen_factor <= 1:
            raise ValueError("Эксергоэкономический фактор вне [0, 1]")
        result.exergy["cogen_factor"] = cogen_factor
        result.exergy["cogen_factor_recommendation"] = (
            "рассмотреть CAPEX-модернизацию" if cogen_factor < .30 else
            "пересмотреть типоразмер и запас" if cogen_factor > .75 else
            "сбалансированная зона; требуется детальный анализ")
        f_value = SpecoCostingEngine.f_rule(fuel_flow, fuel_cost, steam_flow, electricity_flow, z)
        p_value = SpecoCostingEngine.p_rule(fuel_flow, fuel_cost, [steam_flow, electricity_flow], z)
        f_matrix, f_diag = SpecoMatrixSolver.cogeneration(fuel_flow, fuel_cost, steam_flow, electricity_flow, z, "F")
        p_matrix, p_diag = SpecoMatrixSolver.cogeneration(fuel_flow, fuel_cost, steam_flow, electricity_flow, z, "P")
        result.speco = {"f_rule": {"steam_cost_usd_gj": fuel_cost, "electricity_cost_usd_gj": f_value,
                                    "cost_balance_residual_usd_h": fuel_flow * fuel_cost + z - steam_flow * fuel_cost - electricity_flow * f_value},
                        "p_rule": {"product_cost_usd_gj": p_value,
                                    "cost_balance_residual_usd_h": fuel_flow * fuel_cost + z - (steam_flow + electricity_flow) * p_value},
                        "f_matrix": f_matrix, "p_matrix": p_matrix,
                        "f_matrix_diagnostics": f_diag, "p_matrix_diagnostics": p_diag,
                        "z_usd_h": z}

        stages = d.speco_chain
        base = SequentialChainAnalyzer.analyze(stages)
        first = SequentialChainAnalyzer.analyze(stages, 0)
        last = SequentialChainAnalyzer.analyze(stages, len(stages) - 1)
        result.chain = {"base": base, "first_degraded": first, "last_degraded": last,
                        "scenario_rule": "eta_new = eta * 0.95; Ex_F,1 и Z_k фиксированы; потоки следующих аппаратов пересчитываются",
                        "initial_fuel_cost_status": "SKIPPED_MISSING_INPUT",
                        "initial_fuel_cost_missing": "c_F,1 для sequential_chain_speco.csv",
                        "factors_status": "SKIPPED_MISSING_INPUT",
                        "factors_missing": "c_F,k для каждого узла цепочки",
                        "csv_balance_residuals_mw": [x.fuel_mw - x.product_mw - x.destruction_mw for x in stages],
                        "csv_eta_residuals": [x.product_mw / x.fuel_mw - x.efficiency for x in stages]}

        result.compressors = ParallelCompressorsOptimizer(d.compressors.values).calculate()
        result.heat_exchanger = HeatExchangerOptimizer(
            d.economic_constants.values["Heat_Exchanger_Optimization_Params"],
            d.economic_constants.values["Capital_Recovery_Factor_CRF"], annual_hours).calculate()

        gas = next(x for x in d.ammonia_variable_opex if "газ" in x.name)
        electricity = next(x for x in d.ammonia_variable_opex if "Электроэнергия" in x.name)
        gas_points = []
        for price in range(4, 17):
            unit = ammonia.variable_unit_cost + gas.consumption * (price - gas.price) + ammonia.annual_fixed_cost / 500_000
            gas_points.append({"gas_price_usd_gj": price, "ammonia_unit_cost_usd_t": unit,
                               "annual_opex_usd": unit * 500_000})
        el_points = []
        for multiplier in (.5, .75, 1, 1.25, 1.5):
            price = electricity.price * multiplier
            unit = ammonia.variable_unit_cost + electricity.consumption * (price - electricity.price) + ammonia.annual_fixed_cost / 500_000
            el_points.append({"electricity_price_usd_kwh": price, "ammonia_unit_cost_usd_t": unit,
                              "annual_opex_usd": unit * 500_000})
        result.sensitivity = {"gas": gas_points, "electricity": el_points,
                              "electricity_range_rule": "50–150% базового тарифа, шаг 25%"}
        return result
