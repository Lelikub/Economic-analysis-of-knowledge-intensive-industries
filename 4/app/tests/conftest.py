import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'vendor'))
sys.path.insert(0, str(APP))

import pytest
from src.loaders import InputLoader

def pytest_configure(config):
    # Не смешиваем каталоги Windows Temp разных токенов пользователя/песочницы.
    if not config.option.basetemp:
        import uuid
        parent=APP/'logs'/'.pytest_tmp'
        parent.mkdir(parents=True,exist_ok=True)
        config.option.basetemp=str(parent/uuid.uuid4().hex)

@pytest.fixture
def data():
    return InputLoader().load(APP.parent / 'data')
