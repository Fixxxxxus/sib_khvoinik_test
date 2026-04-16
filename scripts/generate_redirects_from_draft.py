#!/usr/bin/env python3
"""
Generate static redirect pages for legacy product paths from migration draft JSON.

Usage:
  python3 scripts/generate_redirects_from_draft.py \
    --draft migration/catalog_migration_draft.json
"""

from __future__ import annotations

import argparse
import json
import os
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").rstrip("/") or ""


def redirect_html(target_path: str) -> str:
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
    parser = argparse.ArgumentParser(description="Generate redirects from migration draft JSON.")
    parser.add_argument("--draft", type=Path, required=True)
    args = parser.parse_args()

    items = json.loads(args.draft.read_text(encoding="utf-8"))
    written = 0
    for item in items:
        slug = item.get("slug")
        if not slug:
            continue
        target = f"{PREFIX}/catalog/{slug}/"
        for legacy in item.get("legacy_paths") or []:
            legacy = (legacy or "").strip("/")
            if not legacy.startswith("product/"):
                continue
            out_dir = ROOT / "docs" / legacy
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(redirect_html(target), encoding="utf-8")
            written += 1
    print(f"Redirect pages generated: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
