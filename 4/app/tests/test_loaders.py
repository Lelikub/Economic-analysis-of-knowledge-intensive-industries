import json
import shutil
from dataclasses import replace
import pytest
from src.loaders import InputLoader
from src.validators import DataValidator
from src.calculators.telemetry import TelemetryCalculator

def copy_inputs(data,tmp_path):
    for name in InputLoader.FILENAMES: shutil.copyfile(data.telemetry.source.parent/name,tmp_path/name)
    return tmp_path

def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError): InputLoader().load(tmp_path)

def test_duplicate_json_keys(data,tmp_path):
    directory=copy_inputs(data,tmp_path)
    (directory/InputLoader.FILENAMES[0]).write_text('{"cargo_profile":{},"cargo_profile":{}}',encoding='utf-8')
    with pytest.raises(ValueError,match='Повтор'): InputLoader().load(directory)

def test_string_number_json(data,tmp_path):
    directory=copy_inputs(data,tmp_path);p=directory/InputLoader.FILENAMES[0]
    raw=json.loads(p.read_text(encoding='utf-8'));raw['cargo_profile']['volume_tons']='20'
    p.write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises(ValueError):DataValidator().validate(InputLoader().load(directory))

def test_wrong_csv_header(data,tmp_path):
    directory=copy_inputs(data,tmp_path)
    (directory/InputLoader.FILENAMES[1]).write_text('customer_id,demand\n1,20\n',encoding='utf-8')
    with pytest.raises(ValueError,match='столбцы'):InputLoader().load(directory)

def test_duplicate_tariff_hub(data,tmp_path):
    directory=copy_inputs(data,tmp_path);p=directory/InputLoader.FILENAMES[3]
    text=p.read_text(encoding='utf-8');p.write_text(text+text.splitlines()[1]+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Повтор'):InputLoader().load(directory)

def test_time_duplicate(data):
    s=data.telemetry.samples
    d=replace(data,telemetry=replace(data.telemetry,samples=(s[0],replace(s[1],timestamp=s[0].timestamp))+s[2:]))
    with pytest.raises(ValueError,match='Временные'):DataValidator().validate(d)

def test_gap_quality_warning(data):
    d=replace(data,telemetry=replace(data.telemetry,samples=data.telemetry.samples[:5]+data.telemetry.samples[6:]))
    rows=DataValidator().validate(d,expected_dataset=False)
    assert any(r['kind']=='WARNING' and r['value']==10 for r in rows)

def test_gps_jump_excluded(data):
    s=data.telemetry.samples[:3]
    d=replace(data.telemetry,samples=(s[0],replace(s[1],latitude=-50,longitude=-100),s[2]))
    x=TelemetryCalculator().calculate(d)
    assert x['excluded_gps_segments']==2
    assert x['distance_km']==0

def test_rate_and_risk_reject_nonfinite(data):
    from src.calculators.tco import MultimodalTCOSimulator
    s=MultimodalTCOSimulator(data.cargo,data.cbam,data.routes)
    with pytest.raises(ValueError):s.set_failure_probability('Rail_Express',float('inf'))
    with pytest.raises(ValueError):s.calculate('Sea_Road_Multimodal',total_days=2)

def test_no_silent_input_rewrite(data):
    import hashlib
    path=data.telemetry.source
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    DataValidator().validate(data)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
