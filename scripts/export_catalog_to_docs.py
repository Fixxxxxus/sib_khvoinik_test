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
    from pages.catalog_merge import find_merged_plant, get_merged_catalog_plants, resolve_catalog_plant_slug
    from pages.catalog_nav import enrich_catalog_context
    from pages.catalog_products import plant_belongs_to_category, similar_plants_for_detail
    from pages.catalog_subcategories import all_subcategory_slugs, category_heading_for_slug
    from pages.catalog_context import get_catalog_page_for_template

    n = 0

    merged_plants, _ = get_merged_catalog_plants()
    catalog_page = get_catalog_page_for_template()

    html = render_to_string("pages/catalog.html", enrich_catalog_context(dict(catalog_page)))
    write_html(DOCS_CATALOG / "index.html", apply_site_prefix(html, PREFIX))
    n += 1
    print(f"OK docs/catalog/index.html")

    categories = catalog_page.get("categories") or []

    for cat in categories:
        slug = cat["slug"]
        ctx = dict(catalog_page)
        ctx["active_category_slug"] = slug
        ctx["category_label"] = cat.get("label") or slug
        ctx["category_hub_links"] = cat.get("category_hub_links")
        ctx["plants"] = [p for p in merged_plants if plant_belongs_to_category(p, slug)]
        html = render_to_string("pages/catalog-category.html", enrich_catalog_context(ctx))
        write_html(DOCS_CATALOG / slug / "index.html", apply_site_prefix(html, PREFIX))
        n += 1
        print(f"OK docs/catalog/{slug}/index.html")

    for sub_slug in sorted(all_subcategory_slugs()):
        ctx = dict(catalog_page)
        ctx["active_category_slug"] = sub_slug
        ctx["category_label"] = category_heading_for_slug(sub_slug, categories)
        ctx["category_hub_links"] = None
        ctx["plants"] = [p for p in merged_plants if plant_belongs_to_category(p, sub_slug)]
        html = render_to_string("pages/catalog-category.html", enrich_catalog_context(ctx))
        write_html(DOCS_CATALOG / sub_slug / "index.html", apply_site_prefix(html, PREFIX))
        n += 1
        print(f"OK docs/catalog/{sub_slug}/index.html")

    written_plant_paths: set[str] = set()
    for plant in merged_plants:
        slug = plant.get("slug")
        if not slug:
            continue
        alias_slugs = [slug] + list(plant.get("merged_member_slugs") or [])
        for sp in alias_slugs:
            if sp in written_plant_paths:
                continue
            written_plant_paths.add(sp)
            ctx = dict(catalog_page)
            ctx["plants"] = merged_plants
            ctx["active_plant_slug"] = resolve_catalog_plant_slug(sp)
            ctx["active_plant"] = find_merged_plant(merged_plants, sp)
            if not ctx["active_plant"]:
                continue
            ctx["similar_plants"] = similar_plants_for_detail(ctx["active_plant"], merged_plants)
            html = render_to_string("pages/plant-card.html", enrich_catalog_context(ctx))
            write_html(DOCS_CATALOG / sp / "index.html", apply_site_prefix(html, PREFIX))
            n += 1
            print(f"OK docs/catalog/{sp}/index.html")

    print(f"Готово: {n} страниц каталога.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
