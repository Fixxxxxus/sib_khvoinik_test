#!/usr/bin/env python3
"""
Перекачать фото для позиций, куда попал og:image-логотип Aspro (247×59 и т.п.).

Читает migration/catalog_migration_draft.json, для записей с legacy_paths
заново тянет HTML, парсит (migrate_gazony_product.parse_product_page),
скачивает корректный image_url в static/ и docs/static/, обновляет draft.

После этого нужно:
  python3 scripts/apply_catalog_draft_to_data.py --draft migration/catalog_migration_draft.json
  python3 scripts/export_catalog_to_docs.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.migrate_gazony_product import download_file, fetch, parse_product_page

RU_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def ascii_slug(value: str) -> str:
    value = (value or "").lower()
    value = "".join(RU_TO_LAT.get(ch, ch) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "item"


def is_logo_png(path: Path) -> bool:
    if path.suffix.lower() != ".png" or not path.is_file():
        return False
    try:
        head = path.read_bytes()[:32]
    except OSError:
        return False
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    w, h = struct.unpack(">II", head[16:24])
    return w == 247 and h == 59


def is_branding_url(url: str) -> bool:
    u = (url or "").lower()
    return "callcorp3" in u or ("aspro" in u and "iblock" not in u)


def legacy_to_url(old_base: str, legacy_path: str) -> str:
    base = old_base.rstrip("/") + "/"
    path = (legacy_path or "").strip()
    if not path.startswith("/"):
        path = "/" + path
    return urllib.parse.urljoin(base, path)


def rel_for_download(slug: str, image_url: str) -> str:
    ext = Path(urllib.parse.urlparse(image_url).path).suffix.lower() or ".jpg"
    base = ascii_slug(slug)
    h = hashlib.md5(image_url.encode("utf-8")).hexdigest()[:8]
    return f"media/images/catalog/migrated/{base}-{h}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair catalog images that saved Aspro og:logo.")
    parser.add_argument("--draft", type=Path, default=Path("migration/catalog_migration_draft.json"))
    parser.add_argument("--old-base", default="http://old.gazony.ru")
    parser.add_argument("--timeout", type=int, default=35)
    args = parser.parse_args()

    items: list[dict] = json.loads(args.draft.read_text(encoding="utf-8"))
    fixed = 0
    skipped = 0
    errors: list[str] = []

    for item in items:
        rel = (item.get("image") or "").strip()
        if not rel:
            skipped += 1
            continue
        p = ROOT / "static" / rel
        need = is_branding_url(item.get("image_url") or "") or is_logo_png(p)
        if not need:
            skipped += 1
            continue
        paths = item.get("legacy_paths") or []
        if not paths:
            errors.append(f"{item.get('slug')}: no legacy_paths")
            continue
        url = legacy_to_url(args.old_base, paths[0])
        try:
            html = fetch(url, timeout=args.timeout)
            parsed = parse_product_page(html, url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.get('slug')}: fetch {exc}")
            continue
        image_url = (parsed.get("image_url") or "").strip()
        if not image_url or is_branding_url(image_url):
            errors.append(f"{item.get('slug')}: still no valid image_url")
            continue
        slug = str(item.get("slug") or item.get("name") or "item")
        new_rel = rel_for_download(slug, image_url)
        dst_static = ROOT / "static" / new_rel
        dst_docs = ROOT / "docs" / "static" / new_rel
        try:
            dst_static.parent.mkdir(parents=True, exist_ok=True)
            download_file(image_url, dst_static, timeout=args.timeout)
            dst_docs.parent.mkdir(parents=True, exist_ok=True)
            dst_docs.write_bytes(dst_static.read_bytes())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.get('slug')}: download {exc}")
            continue
        item["image_url"] = image_url
        item["image"] = new_rel
        fixed += 1

    args.draft.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fixed images: {fixed}, skipped: {skipped}, errors: {len(errors)}")
    for e in errors[:20]:
        print(" ", e)
    if len(errors) > 20:
        print(f"  … {len(errors) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
