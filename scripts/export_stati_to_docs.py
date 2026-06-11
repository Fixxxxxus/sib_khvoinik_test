#!/usr/bin/env python3
"""
Экспорт раздела «Статьи» в docs/ для статического зеркала (GitHub Pages):
docs/stati/index.html (список) + docs/stati/<slug>/index.html (каждая статья).

Запуск из корня проекта:
  python3 scripts/export_stati_to_docs.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""


def apply_site_prefix(html: str) -> str:
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

    return re.sub(r'(href|src)=(["\'])(/[^"\']*)\2', fix_attr, html)


def main() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.template.loader import render_to_string
    from pages import seo
    from pages.data import STATI_PAGE

    from export_common import postprocess_docs_html

    # Список статей.
    html = apply_site_prefix(render_to_string("pages/stati.html", dict(STATI_PAGE)))
    html = postprocess_docs_html(html, PREFIX)
    out = ROOT / "docs/stati/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out.relative_to(ROOT)} ({len(html)} символов)")

    # Детальные страницы (контекст повторяет pages.views.stati_detail).
    for article in STATI_PAGE["articles"]:
        slug = article["slug"]
        canonical_path = f"/stati/{slug}/"
        ctx = dict(STATI_PAGE)
        ctx.update(
            active_article_slug=slug,
            article=article,
            seo_title=article["title"],
            og_title=article["title"],
            meta_description=article["excerpt"],
            canonical_path=canonical_path,
            jsonld_blocks=[
                seo.article_jsonld(article, canonical_path),
                seo.breadcrumbs_jsonld([
                    ("Главная", "/"),
                    ("Статьи", "/stati/"),
                    (article["title"], canonical_path),
                ]),
            ]
            + ([seo.faq_jsonld(article["faq"])] if article.get("faq") else []),
        )
        html = apply_site_prefix(render_to_string("pages/stati-detail.html", ctx))
        html = postprocess_docs_html(html, PREFIX)
        out = ROOT / f"docs/stati/{slug}/index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"OK: {out.relative_to(ROOT)} ({len(html)} символов)")


if __name__ == "__main__":
    main()
