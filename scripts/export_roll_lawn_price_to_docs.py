#!/usr/bin/env python3
"""
Рендерит pages/roll-lawn-price.html и сохраняет docs/prais-rulonnyy-gazon/index.html.

Запуск из корня проекта:
  python3 scripts/export_roll_lawn_price_to_docs.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test")


def main() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages.catalog_nav import enrich_catalog_context
    from pages.data import ROLL_LAWN_PRICE_PAGE

    ctx = dict(ROLL_LAWN_PRICE_PAGE)
    ctx["active_catalog_nav_route"] = "roll_lawn_price"
    html = render_to_string("pages/roll-lawn-price.html", enrich_catalog_context(ctx))
    html = html.replace("/static/", f"{PREFIX}/static/")

    def fix_attr(m: re.Match[str]) -> str:
        attr, q, path = m.group(1), m.group(2), m.group(3)
        if (
            path.startswith(PREFIX)
            or path.startswith("http")
            or path.startswith("//")
            or path.startswith("#")
            or path.startswith("mailto")
            or path.startswith("tel:")
        ):
            return m.group(0)
        if path.startswith("/"):
            return f'{attr}={q}{PREFIX}{path}{q}'
        return m.group(0)

    html = re.sub(r'(href|src)=(["\'])(/[^"\']*)\2', fix_attr, html)

    out = ROOT / "docs/prais-rulonnyy-gazon/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out.relative_to(ROOT)} ({len(html)} символов)")


if __name__ == "__main__":
    main()
