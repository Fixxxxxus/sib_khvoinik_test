#!/usr/bin/env python3
"""
Собирает статические HTML календаря ухода в docs/sluzhba-zaboty/calendar/
для GitHub Pages (как на localhost с Django, с префиксом SITE_PREFIX).

Запуск из корня проекта:
  python3 scripts/export_calendar_to_docs.py

Переменная окружения: SITE_PREFIX=/sib_khvoinik_test (по умолчанию).
После изменений в templates/pages/calendar*.html — перезапустите скрипт и закоммитьте docs/.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""
DOCS_CALENDAR = ROOT / "docs" / "sluzhba-zaboty" / "calendar"


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
            return f"{attr}={q}{prefix}{path}{q}"
        return m.group(0)

    html = re.sub(r'(href|src)=(["\'])(/[^"\']*)\2', fix_attr, html)
    html = html.replace(
        '<meta name="base-path" content="" />',
        f'<meta name="base-path" content="{prefix}" />',
    )
    return html


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages.data import CALENDAR_PAGE

    n = 0

    # 1. Main calendar page
    html = render_to_string("pages/calendar.html", CALENDAR_PAGE)
    write_html(DOCS_CALENDAR / "index.html", apply_site_prefix(html, PREFIX))
    n += 1
    print("OK docs/sluzhba-zaboty/calendar/index.html")

    categories = CALENDAR_PAGE.get("categories") or []
    plants_all = CALENDAR_PAGE.get("plants") or []

    # 2. Category pages
    for cat in categories:
        slug = cat["slug"]
        ctx = dict(CALENDAR_PAGE)
        ctx["active_category"] = cat
        ctx["category_plants"] = [
            p for p in plants_all if p["category_slug"] == slug
        ]
        html = render_to_string("pages/calendar-category.html", ctx)
        write_html(
            DOCS_CALENDAR / slug / "index.html",
            apply_site_prefix(html, PREFIX),
        )
        n += 1
        print(f"OK docs/sluzhba-zaboty/calendar/{slug}/index.html")

    # 3. Plant pages
    for plant in plants_all:
        plant_slug = plant.get("slug")
        if not plant_slug:
            continue
        cat_slug = plant.get("category_slug", "")
        ctx = dict(CALENDAR_PAGE)
        ctx["active_plant"] = plant
        ctx["active_category"] = next(
            (c for c in categories if c["slug"] == cat_slug),
            {"slug": cat_slug, "label": cat_slug},
        )
        html = render_to_string("pages/calendar-plant.html", ctx)
        write_html(
            DOCS_CALENDAR / cat_slug / plant_slug / "index.html",
            apply_site_prefix(html, PREFIX),
        )
        n += 1
        print(
            f"OK docs/sluzhba-zaboty/calendar/{cat_slug}/{plant_slug}/index.html"
        )

    print(f"Готово: {n} страниц календаря ухода.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
