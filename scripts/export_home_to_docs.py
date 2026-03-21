#!/usr/bin/env python3
"""
Вставляет в docs/index.html содержимое <main> из отрендеренного Django-шаблона
templates/pages/home.html (как на localhost).

Запуск из корня проекта (нужен venv с Django):
  python3 scripts/export_home_to_docs.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_INDEX = ROOT / "docs/index.html"
PREFIX = "/sib_khvoinik_test"


def main() -> None:
    os.chdir(ROOT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages.data import HOME_PAGE

    html = render_to_string("pages/home.html", HOME_PAGE)
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
    m = re.search(r"<main[^>]*>(.*)</main>", html, re.DOTALL)
    if not m:
        print("ERROR: <main> not found in rendered HTML", file=sys.stderr)
        sys.exit(1)
    inner = m.group(1)
    lines = []
    for ln in inner.strip().split("\n"):
        lines.append("      " + ln if ln.strip() else "")
    new_inner = "\n".join(lines) + "\n"

    data = DOCS_INDEX.read_text(encoding="utf-8")
    i0 = data.find("<main>") + len("<main>")
    i1 = data.find("</main>", i0)
    if i0 < len("<main>") or i1 < 0:
        print("ERROR: <main> in docs/index.html", file=sys.stderr)
        sys.exit(1)
    data = data[:i0] + "\n" + new_inner + "\n    " + data[i1:]
    DOCS_INDEX.write_text(data, encoding="utf-8")
    print(f"OK: обновлён {DOCS_INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
