import base64
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
# A quantity, amount or percentage, optionally with a unit ("1,250.500 kg", "93.33", "12 %"): aligned as a number.
NUMERIC = re.compile(r'^[-+]?\d[\d,]*(\.\d+)?(\s?%|\s[A-Za-z]{1,6})?$')


def is_numeric(value):
    return bool(NUMERIC.match(str(value).strip())) if value is not None else False


def render_layout(context, template_roots, templates=('base.html', 'header.html', 'footer.html')):
    environment = Environment(loader=FileSystemLoader([ROOT / 'templates', *template_roots]), autoescape=select_autoescape(['html']))
    environment.tests['numeric'] = is_numeric
    fonts = ''.join("@font-face{font-family:'%s';src:url(data:font/ttf;base64,%s) format('truetype');font-weight:100 900;}" %
                    (family, base64.b64encode((ROOT / 'assets/fonts' / filename).read_bytes()).decode())
                    for family, filename in [('Noto Naskh Arabic', 'NotoNaskhArabic.ttf'), ('Noto Sans', 'NotoSans.ttf')])
    css = (ROOT / 'assets/print.css').read_text(encoding='utf-8')
    # CSS is exclusively trusted packaged content; no user CSS is inserted here.
    from markupsafe import Markup
    context = dict(context, css=Markup(fonts + css), chrome_css=Markup(css + 'body{width:100%;padding:0 36px}'))
    return tuple(environment.get_template(name).render(**context) for name in templates)
