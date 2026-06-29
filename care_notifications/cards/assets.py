"""Офлайн-ассеты для рендера карточек: Lucide и Manrope (base64 woff2)."""
from __future__ import annotations

import base64
import functools
import pathlib

from django.conf import settings

_STATIC = pathlib.Path(settings.BASE_DIR) / "static"
_FONTS = _STATIC / "fonts"
_WEIGHTS = {"500": "manrope-500.woff2", "700": "manrope-700.woff2",
            "800": "manrope-800.woff2"}


@functools.lru_cache(maxsize=1)
def lucide_src() -> str:
    return (_STATIC / "js" / "lucide.min.js").read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def font_face_css() -> str:
    rules = []
    for weight, fname in _WEIGHTS.items():
        b64 = base64.b64encode((_FONTS / fname).read_bytes()).decode()
        rules.append(
            "@font-face{font-family:'Manrope';font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
    return "".join(rules)
