"""Platform report assets: bundled fonts (also mounted into the renderer as system fallbacks) and the default logo.

Modules reach them through these names, never by building file paths themselves.
"""
from pathlib import Path

ROOT = Path(__file__).parent
FONTS = ROOT / "fonts"
PLACEHOLDER_LOGO = ROOT / "defaults" / "logo-placeholder.png"
