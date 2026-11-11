from pathlib import Path
import json
import hashlib
import pytest
import pandas as pd
from PIL import Image
from src.reporting import validate_docx,REPORT_NAME

OUTPUT=Path(__file__).resolve().parents[1]/'output'

@pytest.fixture
def artifacts():
    import os
    directory=Path(os.environ.get('LOGISTICS_ARTIFACT_DIR',OUTPUT))
    if not (directory/'metrics.json').exists(): pytest.skip('Артефакты ещё не созданы; сначала main.py')
    return directory

def test_docx_structure(artifacts):
    assert validate_docx(artifacts/REPORT_NAME)['status']=='PASS'

def test_only_title_has_forced_page_break(artifacts):
    import zipfile
    from lxml import etree
    with zipfile.ZipFile(artifacts/REPORT_NAME) as z:
        root=etree.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    assert len(root.xpath('//w:br[@w:type="page"]',namespaces=ns))==1
    assert not root.xpath('//w:pPr/w:pageBreakBefore[not(@w:val="0")]',namespaces=ns)

def test_dpp_schema(artifacts,data):
    x=json.loads((artifacts/'dpp_passport.json').read_text(encoding='utf-8'))
    fields={'batch_id':str,'cargo_type':str,'transport_mode':str,'sha256_telemetry_digest':str,'cold_chain_status':str,
            'vibration_status':str,'final_disposition':str,'adjusted_tco_usd':float,'scope3_transport_emissions_tco2':float}
    assert all(k in x and isinstance(x[k],v) for k,v in fields.items())
    assert len(x['sha256_telemetry_digest'])==64
    assert x['sha256_telemetry_digest']==hashlib.sha256(data.telemetry.source.read_bytes()).hexdigest()
    assert x['cold_chain_status']=='VIOLATED'
    assert x['final_disposition']=='SCRAP_WRITE_OFF'
    assert x['adjusted_tco_usd']>1200000

def test_images_present(artifacts):
    meta=json.loads((artifacts/'plot_validation.json').read_text(encoding='utf-8'))
    assert len(meta)==12
    for m in meta:
        assert m['status']=='PASS'
        assert all(e['inside'] for e in m['labels'])
        with Image.open(artifacts/'figures'/(m['key']+'.png')) as im:
            assert im.width>=1600 and im.height>=800
            im.verify()

@pytest.mark.parametrize('name',['wacc','cargo_value','lead_time','ets'])
def test_curve_tables_match_metrics(artifacts,name):
    x=json.loads((artifacts/'metrics.json').read_text(encoding='utf-8'))['tco']['sensitivity'][name]
    df=pd.read_csv(artifacts/'tables'/(name+'.csv'))
    expected=pd.DataFrame(x)
    pd.testing.assert_frame_equal(df,expected,check_dtype=False,rtol=1e-10,atol=1e-6)

def test_dynamic_tco_consistency(artifacts):
    m=json.loads((artifacts/'metrics.json').read_text(encoding='utf-8'))
    d=json.loads((artifacts/'dpp_passport.json').read_text(encoding='utf-8'))
    assert m['iot']['delta_usd']==pytest.approx(1194000)
    assert d['adjusted_tco_usd']==round(m['iot']['after']['tco_log_usd'],2)
    assert m['iot']['after']['risk_usd']==1200000
    assert m['tco']['baseline']['Air_Express']['p_fail']==.005

def test_report_contains_results(artifacts):
    from docx import Document
    d=Document(artifacts/REPORT_NAME)
    text='\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells])
    for x in ['SCRAP_WRITE_OFF','123 624 000','6.1.','6.2.','6.3.']:
        assert x in text
    incident_tables=[t for t in d.tables if [c.text for c in t.rows[0].cells]==['Начальный индекс','Последний индекс','Начало','Отсчётов','Минут','Пик']]
    assert float(incident_tables[0].rows[1].cells[4].text.replace(',','.'))==45
