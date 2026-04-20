#!/usr/bin/env python3
"""
Рендерит pages/sluzhba-zaboty.html и сохраняет в docs/sluzhba-zaboty/index.html
для GitHub Pages / деплоя на gazony.ru (префикс SITE_PREFIX).

Запуск из корня проекта:
  python3 scripts/export_sluzhba_zaboty_to_docs.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""


def main() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages.data import SLUZHBA_ZABOTY_PAGE

    html = render_to_string("pages/sluzhba-zaboty.html", SLUZHBA_ZABOTY_PAGE)
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

    out = ROOT / "docs/sluzhba-zaboty/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out.relative_to(ROOT)} ({len(html)} символов)")


if __name__ == "__main__":
    main()
