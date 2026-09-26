"""Проверки физических и экономических контрактов на известных примерах."""
import math

import numpy as np
import pytest

from src.calculations import (
    ChemicalOpexModel, MachineryOpexModel, ExergyAnalysisEngine,
    SpecoCostingEngine, SpecoMatrixSolver, SequentialChainAnalyzer,
    ParallelCompressorsOptimizer, HeatExchangerOptimizer,
)
from src.models import ThermodynamicViolationError, OutOfRelevantRangeWarning


def test_opex_and_step_fixed():
    assert ChemicalOpexModel([(2, 3)], [10]).scenario(5)["unit_cost"] == 8
    model = MachineryOpexModel([3], [10], [4])
    assert model.scenario(6, mitigate=True)["unit_cost"] == pytest.approx(4)
    with pytest.warns(OutOfRelevantRangeWarning):
        model.scenario(15)


def test_material_and_labor_input_validation():
    assert MachineryOpexModel.gross_material(90, 0.1) == pytest.approx(100)
    assert MachineryOpexModel.material_cost(2, [(90, 5, 0.1)], 20) == pytest.approx(1040)
    assert MachineryOpexModel.labor_cost(2, [(10, 30)]) == 600
    with pytest.raises(ValueError):
        MachineryOpexModel.gross_material(100, 1)


def test_second_law_and_exergy():
    assert ExergyAnalysisEngine.physical(600, 100, 2, 1, 300) == 200
    assert ExergyAnalysisEngine.gouy_stodola(300, 2) == 600
    with pytest.raises(ThermodynamicViolationError):
        ExergyAnalysisEngine.gouy_stodola(300, -0.01)


def test_speco_rules_and_matrix():
    f = SpecoCostingEngine.f_rule(144, 12, 100.8, 36, 180)
    p = SpecoCostingEngine.p_rule(144, 12, [100.8, 36], 180)
    assert f == pytest.approx(19.4)
    assert p == pytest.approx(13.947368421052632)
    assert SpecoMatrixSolver.solve(np.array([[1., 1.], [1., -1.]]), np.array([2., 0.]))[0].tolist() == pytest.approx([1, 1])
    with pytest.raises(ValueError):
        SpecoMatrixSolver.solve(np.array([[1., 1.], [2., 2.]]), np.array([2., 4.]))


def test_cogen_exergoeconomic_factor():
    assert SpecoCostingEngine.exergoeconomic_factor(180, 12, 2) == pytest.approx(180 / 266.4)


def test_chain_and_compressors():
    assert SequentialChainAnalyzer.escalation_factor([.8] * 5) == pytest.approx(1 / .8**5)
    inp = {"Total_Mass_Flow_kg_s": 3, "Electricity_Tariff_USD_per_kWh": .08,
           "Annual_Operating_Hours": 8000,
           "Compressor_1_Piston": {"w_base_kJ_kg": 280, "w_coeff_kJ_s_kg2": 40, "Hourly_Opex_Fix_Z1_USD_per_h": 4.5},
           "Compressor_2_Screw_VFD": {"w_base_kJ_kg": 250, "w_coeff_kJ_s_kg2": 20, "Hourly_Opex_Fix_Z2_USD_per_h": 12}}
    result = ParallelCompressorsOptimizer(inp).calculate()
    assert result["optimal_m1"] == pytest.approx(.75)
    assert result["numeric_m1"] == pytest.approx(.75, abs=1e-4)
    assert result["annual_savings"] == pytest.approx(21600)


def test_heat_exchanger_synthetic_optimum_and_missing_k():
    inp = {"Base_Temperature_Difference_DeltaT_base_K": 20,
           "Base_CAPEX_C0_USD": 1000, "Cost_Scaling_Exponent_Beta": 1,
           "Fuel_Exergy_Cost_cF_USD_per_GJ": 10,
           "Min_Search_DeltaT_K": 1, "Max_Search_DeltaT_K": 100}
    model = HeatExchangerOptimizer(inp, crf=.1, annual_hours=100)
    assert model.calculate()["status"] == "SKIPPED_MISSING_INPUT"
    result = model.calculate(k_gj_per_h_k=.02)
    assert result["optimum_delta_t_k"] == pytest.approx(10, abs=.01)
