"""Контроль реальных входных файлов и отказ на повреждённых данных."""
from pathlib import Path

import pytest

from src.loader import DataLoader
from src.models import InputDataError


DATA = Path(__file__).resolve().parents[2] / "data"


def test_load_all_sources():
    loader = DataLoader(DATA)
    data = loader.load()
    assert len(data.ammonia_variable_opex) == 6
    assert len(data.machinery_fixed_opex) == 7
    assert len(data.energy_streams) == 10
    assert len(data.speco_chain) == 5
    assert loader.audit()["files"]["streams_energy_balance.csv"]["rows"] == 10
    assert all(c["numeric_discrepancies"] == [] for c in loader.audit()["cross_checks"])


def test_missing_required_column_is_rejected(tmp_path):
    (tmp_path / "opex_ammonia_raw.csv").write_text("Resource_Name,Price_pi_USD\nГаз,8\n", encoding="utf-8")
    with pytest.raises(InputDataError, match="столбц"):
        DataLoader(tmp_path).read_csv("opex_ammonia_raw.csv")


def test_negative_json_tariff_is_rejected(tmp_path):
    (tmp_path / "project_economic_constants.json").write_text(
        '{"Tariffs_and_Market_Prices":{"Natural_Gas_USD_per_GJ":-1}}', encoding="utf-8")
    with pytest.raises(InputDataError, match="тариф"):
        DataLoader(tmp_path).read_json("project_economic_constants.json")
