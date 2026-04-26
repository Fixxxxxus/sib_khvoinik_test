#!/usr/bin/env python3
"""
Рендерит pages/pitomnik.html и сохраняет docs/pitomnik/index.html (модалки и base в актуальном виде).

Запуск из корня проекта:
  python3 scripts/export_pitomnik_to_docs.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/pitomnik/index.html"
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test")


def apply_site_prefix(html: str, prefix: str) -> str:
    html = html.replace("/static/", f"{prefix}/static/")

    def fix_attr(m: re.Match[str]) -> str:
        attr, q, path = m.group(1), m.group(2), m.group(3)
        if (
            path.startswith(prefix)
            or path.startswith("http")
            or path.startswith("//")
            or path.startswith("#")
            or path.startswith("mailto")
            or path.startswith("tel:")
        ):
            return m.group(0)
        if path.startswith("/"):
            return f'{attr}={q}{prefix}{path}{q}'
        return m.group(0)

    html = re.sub(r'(href|src)=(["\'])(/[^"\']*)\2', fix_attr, html)
    html = html.replace(
        '<meta name="base-path" content="" />',
        f'<meta name="base-path" content="{prefix}" />',
        1,
    )
    return html


def main() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages.data import PITOMNIK_PAGE

    html = render_to_string("pages/pitomnik.html", PITOMNIK_PAGE)
    html = apply_site_prefix(html, PREFIX)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"OK: {OUT.relative_to(ROOT)} ({len(html)} символов)")


if __name__ == "__main__":
    main()
