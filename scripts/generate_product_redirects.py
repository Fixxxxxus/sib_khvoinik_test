#!/usr/bin/env python3
"""
Генерирует статические HTML-редиректы для старых URL каталога Bitrix.

GitHub Pages не отдаёт настоящий HTTP 301 из _redirects; для поисковиков и
пользователей используем canonical + meta refresh + location.replace (как в migration.md).

Запуск из корня:
  python3 scripts/generate_product_redirects.py

Префикс сайта (как в export_*): SITE_PREFIX=/sib_khvoinik_test
"""

from __future__ import annotations

import os
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""


def redirect_html(target_path: str) -> str:
    """target_path: абсолютный путь на сайте, напр. /sib_khvoinik_test/catalog/foo/"""
    safe = escape(target_path, quote=True)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Перенаправление в каталог</title>
  <link rel="canonical" href="{safe}">
  <meta http-equiv="refresh" content="0;url={safe}">
  <script>location.replace("{safe}");</script>
</head>
<body>
  <p>Страница перенесена. Если не произошло автоматическое перенаправление, откройте
  <a href="{safe}">новый адрес в каталоге</a>.</p>
</body>
</html>
"""


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from pages.data import CATALOG_PAGE

    def write_legacy_redirects(slug: str, legacy_paths: list) -> int:
        n = 0
        for legacy in legacy_paths or []:
            legacy = legacy.strip("/")
            if not legacy.startswith("product/"):
                print(f"skip (unexpected path): /{legacy}/", file=sys.stderr)
                continue
            rel = legacy
            out_dir = ROOT / "docs" / rel
            out_dir.mkdir(parents=True, exist_ok=True)
            target = f"{PREFIX}/catalog/{slug}/"
            (out_dir / "index.html").write_text(redirect_html(target), encoding="utf-8")
            n += 1
            print(f"OK docs/{rel}/index.html -> {target}")
        return n

    written = 0
    for plant in CATALOG_PAGE.get("plants") or []:
        s = plant.get("slug")
        if s:
            written += write_legacy_redirects(s, plant.get("legacy_paths"))

    for cat in CATALOG_PAGE.get("categories") or []:
        s = cat.get("slug")
        if s:
            written += write_legacy_redirects(s, cat.get("legacy_paths"))

    print(f"Готово: {written} редирект(ов).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
