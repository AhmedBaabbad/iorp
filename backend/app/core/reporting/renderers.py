from io import BytesIO
from typing import Protocol

import httpx
from pypdf import PdfReader

from app.core.config import settings


class RenderError(RuntimeError):
    pass


class PdfRenderer(Protocol):
    def render(self, html: str, header: str, footer: str, landscape: bool = False, margins: tuple[float, float] | None = None) -> tuple[bytes, int]: ...


class GotenbergRenderer:
    def render(self, html, header, footer, landscape=False, margins=None):
        top, bottom = margins or (1.25, 0.9)
        try:
            response = httpx.post(
                settings.report_renderer_url.rstrip('/') + '/forms/chromium/convert/html',
                files=[('files', ('index.html', html.encode(), 'text/html')),
                       ('files', ('header.html', header.encode(), 'text/html')),
                       ('files', ('footer.html', footer.encode(), 'text/html'))],
                data={'paperWidth': '8.27', 'paperHeight': '11.7', 'marginTop': str(top),
                      'marginBottom': str(bottom), 'marginLeft': '0.4', 'marginRight': '0.4',
                      'landscape': str(landscape).lower(), 'printBackground': 'true'},
                timeout=60, follow_redirects=False, trust_env=False,
            )
            response.raise_for_status()
            if not response.content.startswith(b'%PDF-'):
                raise RenderError('INVALID_PDF')
            return response.content, len(PdfReader(BytesIO(response.content)).pages)
        except (httpx.HTTPError, ValueError) as exc:
            raise RenderError('PDF_RENDER_FAILED') from exc
