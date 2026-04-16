#!/usr/bin/env python3
"""
Download catalog images from migration draft JSON into static/ and docs/static/.

Usage:
  python3 scripts/download_catalog_images_from_draft.py \
    --draft migration/catalog_migration_draft.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.migrate_gazony_product import download_file


def safe_filename(slug: str, image_url: str) -> str:
    ru_to_lat = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    slug = "".join(ru_to_lat.get(ch, ch) for ch in (slug or "").lower())
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-") or "item"
    ext = Path(urllib.parse.urlparse(image_url).path).suffix.lower() or ".jpg"
    return f"{slug}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download migrated catalog images from draft JSON.")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    items = json.loads(args.draft.read_text(encoding="utf-8"))
    ok = 0
    errors = 0

    for idx, item in enumerate(items, start=1):
        slug = item.get("slug") or f"item-{idx}"
        image_url = item.get("image_url") or ""
        if not image_url:
            continue
        filename = safe_filename(slug, image_url)
        rel = Path("media/images/catalog/migrated") / filename
        dst_static = ROOT / "static" / rel
        dst_docs = ROOT / "docs" / "static" / rel
        try:
            dst_static.parent.mkdir(parents=True, exist_ok=True)
            dst_docs.parent.mkdir(parents=True, exist_ok=True)
            download_file(image_url, dst_static, timeout=args.timeout)
            dst_docs.write_bytes(dst_static.read_bytes())
            item["image"] = rel.as_posix()
            ok += 1
        except Exception:  # noqa: BLE001
            errors += 1
        if idx % 50 == 0:
            print(f"Processed images: {idx}/{len(items)} | ok={ok} | errors={errors}", flush=True)

    args.draft.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated draft: {args.draft}")
    print(f"Images downloaded: {ok}, errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
