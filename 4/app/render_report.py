"""Необязательный нативный рендер Word → PDF; не изменяет исходный DOCX."""
import json
from pathlib import Path
import sys

APP=Path(__file__).resolve().parent
sys.path[:0]=[str(APP/'vendor'),str(APP)]
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')

def render(directory):
    import win32com.client
    from pypdf import PdfReader
    from src.reporting import REPORT_NAME
    from src.serialization import write_json
    directory=Path(directory).resolve()
    if not directory.is_relative_to(APP): raise ValueError('Рендер только внутри 4/app')
    application=None;document=None
    try:
        application=win32com.client.DispatchEx('Word.Application')
        application.Visible=False;application.DisplayAlerts=0
        application.AutomationSecurity=3
        document=application.Documents.Open(str(directory/REPORT_NAME),ReadOnly=True,AddToRecentFiles=False,Visible=False)
        document.Repaginate()
        pdf=directory/(Path(REPORT_NAME).stem+'.pdf')
        document.ExportAsFixedFormat(str(pdf),17)
        captions=[];shapes=[]
        for para in document.Paragraphs:
            text=para.Range.Text.strip()
            if text.startswith('Рисунок '):captions.append(dict(text=text,page=int(para.Range.Information(3))))
        for shape in document.InlineShapes:
            shapes.append(dict(page=int(shape.Range.Information(3)),width_points=float(shape.Width),height_points=float(shape.Height)))
        from src.audit import sha256
        result=dict(status='PASS',engine='Microsoft Word '+str(application.Version),page_count=int(document.ComputeStatistics(2)),captions=captions,images=shapes,pdf=str(pdf),docx_read_only=True,docx_sha256=sha256(directory/REPORT_NAME))
    finally:
        if document is not None:document.Close(False)
        if application is not None:application.Quit()
    reader=PdfReader(pdf)
    texts=[p.extract_text() or '' for p in reader.pages]
    result['pdf_page_count']=len(reader.pages)
    result['pdf_caption_pages']=[i+1 for i,t in enumerate(texts) if 'Рисунок ' in t]
    result['pdf_image_pages']=[i+1 for i,p in enumerate(reader.pages) if len(list(p.images))>0]
    result['pdf_image_count']=sum(len(list(p.images)) for p in reader.pages)
    result['pdf_text_nonempty']=all(t.strip() for t in texts)
    result['caption_image_same_page']=len(captions)==len(shapes)==12 and all(c['page']==s['page'] for c,s in zip(captions,shapes))
    if not result['caption_image_same_page'] or result['pdf_image_count']!=12 or not result['pdf_text_nonempty']:
        result['status']='FAIL'
    write_json(directory/'word_render_validation.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    import traceback
    try:
        result=render(sys.argv[1] if len(sys.argv)>1 else APP/'output')
    except Exception:
        traceback.print_exc()
        result=2
    raise SystemExit(result)
