from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def data_dir(project_root: Path) -> Path:
    return project_root / "1" / "data"


@pytest.fixture
def valid_data(data_dir: Path):
    from euv_analysis.loader import CsvProductionLoader

    return CsvProductionLoader().load(data_dir / "euv_photoresist_pilot_2026.csv")
