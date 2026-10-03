"""Real Chromium integration, opt in with RUN_RENDERER_TESTS=1."""
import os
import subprocess
from uuid import uuid4
from io import BytesIO
from pathlib import Path
import pytest
import httpx
from pypdf import PdfReader
from app.core.config import settings
from app.core.reporting.renderers import GotenbergRenderer
from app.core.reporting.layout import render_layout
from app.core.reporting.contracts import ReportData,TableSection

pytestmark=pytest.mark.skipif(os.environ.get('RUN_RENDERER_TESTS')!='1',reason='Real renderer opt-in')

def test_arabic_pdf_headers_fonts_pages_and_landscape():
    import pymupdf
    data=ReportData(sections=[TableSection(key='test',title='تقرير الإنتاج',columns=['البند','الكمية'],rows=[['منتج عربي','100 kg']]*100)])
    context=dict(data=data,branding={'name':'الشركة','logo_data_uri':'','primary_color':'#24556b'},lang='ar',title='الإنتاج',generated_at='2026',generated_by='مدير',filters='',body_template='production_body.html')
    html,header,footer=render_layout(context,[Path(__file__).parents[1]/'app/production/reporting/templates'])
    pdf,pages=GotenbergRenderer().render(html,header,footer,True)
    assert pdf.startswith(b'%PDF-') and pages>2
    reader=PdfReader(BytesIO(pdf));assert reader.pages[0].mediabox.width>reader.pages[0].mediabox.height
    doc=pymupdf.open(stream=pdf,filetype='pdf')
    assert all('صفحة' in p.get_text() for p in doc)
    assert 'الإنتاج' in ''.join(p.get_text() for p in doc)
    assert any(font[1] != 'n/a' for font in doc[0].get_fonts())

def test_renderer_rejects_external_network_and_javascript():
    url=settings.report_renderer_url+'/forms/chromium/convert/html'
    marker=uuid4().hex
    html=f'<html><body>SAFE<script>document.body.innerText="JAVASCRIPT_EXECUTED"</script><img src="https://example.com/{marker}.png"></body></html>'
    response=httpx.post(url,files={'files':('index.html',html,'text/html')},timeout=60,trust_env=False)
    assert response.status_code==200  # Chromium omits a blocked image; it can still produce the document.
    logs=subprocess.run(['docker','compose','logs','--since','30s','report-renderer'],capture_output=True,text=True,check=True).stdout
    assert any(marker in line and 'value filtered' in line for line in logs.splitlines())
    pdf,_=GotenbergRenderer().render('<html><body>SAFE<script>document.body.innerText="JAVASCRIPT_EXECUTED"</script></body></html>','<html></html>','<html></html>')
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'SAFE' in text and 'JAVASCRIPT_EXECUTED' not in text
