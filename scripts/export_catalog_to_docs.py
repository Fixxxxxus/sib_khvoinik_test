#!/usr/bin/env python3
"""
Собирает статические HTML каталога в docs/catalog/ для GitHub Pages
(как на localhost с Django, с префиксом SITE_PREFIX).

Запуск из корня проекта:
  python3 scripts/export_catalog_to_docs.py

Переменная окружения: SITE_PREFIX=/sib_khvoinik_test (по умолчанию).
После изменений в templates/pages/catalog*.html или plant-card — перезапустите скрипт и закоммитьте docs/.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""
DOCS_CATALOG = ROOT / "docs" / "catalog"


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
    from pages.data import CATALOG_PAGE

    n = 0

    html = render_to_string("pages/catalog.html", CATALOG_PAGE)
    write_html(DOCS_CATALOG / "index.html", apply_site_prefix(html, PREFIX))
    n += 1
    print(f"OK docs/catalog/index.html")

    categories = CATALOG_PAGE.get("categories") or []
    plants_all = CATALOG_PAGE.get("plants") or []

    for cat in categories:
        slug = cat["slug"]
        ctx = dict(CATALOG_PAGE)
        ctx["active_category_slug"] = slug
        ctx["category_label"] = cat.get("label") or slug
        ctx["plants"] = [p for p in plants_all if p.get("category_slug") == slug]
        html = render_to_string("pages/catalog-category.html", ctx)
        write_html(DOCS_CATALOG / slug / "index.html", apply_site_prefix(html, PREFIX))
        n += 1
        print(f"OK docs/catalog/{slug}/index.html")

    for plant in plants_all:
        slug = plant.get("slug")
        if not slug:
            continue
        ctx = dict(CATALOG_PAGE)
        ctx["active_plant_slug"] = slug
        ctx["active_plant"] = plant
        html = render_to_string("pages/plant-card.html", ctx)
        write_html(DOCS_CATALOG / slug / "index.html", apply_site_prefix(html, PREFIX))
        n += 1
        print(f"OK docs/catalog/{slug}/index.html")

    print(f"Готово: {n} страниц каталога.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
