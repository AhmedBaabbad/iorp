"""Run after docker compose up -d report-renderer; writes reviewable PDF/HTML artifacts."""
from pathlib import Path
from io import BytesIO
import base64
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from pypdf import PdfReader
import pymupdf
from app.core.reporting.contracts import ReportData, TableSection
from app.core.reporting.layout import render_layout
from app.core.reporting.renderers import GotenbergRenderer

root = Path(__file__).resolve().parents[1]
placeholder = root / 'app/core/reporting/assets/defaults/logo-placeholder.png'
placeholder.parent.mkdir(parents=True, exist_ok=True)
im = Image.new('RGBA', (160, 100), (0, 0, 0, 0))
draw = ImageDraw.Draw(im)
for x, h in [(25, 30), (62, 50), (99, 70)]:
    draw.rounded_rectangle((x, 85-h, x+27, 85), radius=4, fill='#24556b')
im.save(placeholder)
logo = 'data:image/png;base64,' + base64.b64encode(placeholder.read_bytes()).decode()
data = ReportData(sections=[TableSection(key='sample', title='اختبار الإنتاج العربي', columns=['رقم', 'البند', 'الكمية'], rows=[[str(i), 'منتج عربي Mixed English', '125.500 kg'] for i in range(1, 121)])])
branding = dict(name='اختبار الشركة', legal_name_en='Arabic PDF test', logo_data_uri=logo, primary_color='#24556b')
context = dict(branding=branding, lang='ar', title='تقرير الإنتاج', reference='RPT-TEST-2026-000001', generated_at='2026-10-01', generated_by='اختبار', filters='', data=data, body_template='production_body.html')
html, header, footer = render_layout(context, [root / 'app/production/reporting/templates'])
pdf, pages = GotenbergRenderer().render(html, header, footer)
import os, tempfile
out = Path(os.environ.get('REPORT_SAMPLES_DIR') or Path(tempfile.gettempdir()) / 'iorp-report-samples') / 'report-spike'; out.mkdir(parents=True, exist_ok=True)
(out / 'arabic.pdf').write_bytes(pdf)
(out / 'arabic.html').write_text(html, encoding='utf-8')
reader = PdfReader(BytesIO(pdf))
texts = [page.get_text() for page in pymupdf.open(stream=pdf, filetype='pdf')]
assert pages >= 3
assert all('RPT-TEST' in text for text in texts)
assert all('صفحة' in text or 'ةحفص' in text for text in texts)
assert 'الإنتاج' in ''.join(texts) or 'جاتنإلا' in ''.join(texts)
print(f'PASS Arabic PDF: {pages} pages, repeating footer/reference, Arabic extraction; {out}')
