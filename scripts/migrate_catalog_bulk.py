#!/usr/bin/env python3
"""
Bulk migration helper for old catalog pages.

Pipeline:
1) Read old detail URLs from a txt file (one URL per line)
2) Fetch and parse product cards
3) Group duplicates into one item with variants
4) Save draft JSON for further import into pages/data.py

Usage:
  python3 scripts/migrate_catalog_bulk.py \
    --urls migration/old_catalog_urls.txt \
    --out migration/catalog_migration_draft.json \
    --errors migration/catalog_migration_errors.csv
"""

from __future__ import annotations

import argparse
from typing import Optional
import csv
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.migrate_gazony_product import download_file, fetch, parse_product_page


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def slugify(value: str) -> str:
    s = value.lower()
    s = re.sub(r"[^a-z0-9а-яё]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "item"


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


def extract_variant_from_name(name: str) -> tuple[str, str]:
    n = normalize_spaces(name)

    height_match = re.search(r"\bh\s*\d+\s*[-–]\s*\d+\b", n, flags=re.IGNORECASE)
    height = height_match.group(0).replace("h", "h ").replace("  ", " ").strip() if height_match else ""

    cont_match = re.search(r"\(([^)]*?(?:ком|сетка|mesh|c\d[^)]*))\)", n, flags=re.IGNORECASE)
    if cont_match:
        container = normalize_spaces(cont_match.group(1))
    else:
        # fallback: S2/3, C2/3 etc.
        short_match = re.search(r"\b[SC]\s*\d+(?:[\/,]\d+)?\b", n, flags=re.IGNORECASE)
        container = normalize_spaces(short_match.group(0)) if short_match else ""

    return height, container


def base_name_for_grouping(name: str) -> str:
    n = normalize_spaces(name)
    # remove trailing variant chunks (height, brackets, container codes)
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n)
    n = re.sub(r"\s+\bh\s*\d+\s*[-–]\s*\d+.*$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s+\b[SC]\s*\d+(?:[\/,]\d+)?\b.*$", "", n, flags=re.IGNORECASE)
    return normalize_spaces(n)


def parse_category_slug(legacy_path: str) -> str:
    parts = [p for p in legacy_path.strip("/").split("/") if p]
    # /product/{category}/{subcategory}/{item}/
    if len(parts) >= 3 and parts[0] == "product":
        mapping = {
            "derevya": "derevya",
            "khvoynye": "hvoynye-derevya",
            "kustarniki": "listvennye-kustarniki",
            "klubnika": "klubnika",
            "odnoletnie_tsvety": "odnoletniaia-rassada",
            "ovoshchnaya_rassada": "ovoshchnaya-rassada",
            "mnogoletnie_tsvety": "mnogoletnie-tsvety",
            "plodovye": "plodovye",
            "rozy": "rozy",
            "semena_gazonnykh_trav": "semena-gazonnyh-trav",
        }
        return mapping.get(parts[1], "listvennye-kustarniki")
    return "listvennye-kustarniki"


def to_old_domain(url: str, old_base: str) -> str:
    """
    Replace host in sitemap URL with old domain host.
    """
    old = urllib.parse.urlparse(old_base)
    src = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((old.scheme, old.netloc, src.path, "", "", ""))


def image_rel_from_url(image_url: str, slug: str) -> str:
    ext = Path(urllib.parse.urlparse(image_url).path).suffix.lower() or ".jpg"
    safe_slug = ascii_slug(slug)
    return f"media/images/catalog/migrated/{safe_slug}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build draft migrated catalog JSON from old URLs.")
    parser.add_argument("--urls", type=Path, required=True, help="Text file with URLs, one per line.")
    parser.add_argument("--out", type=Path, default=Path("migration/catalog_migration_draft.json"))
    parser.add_argument("--errors", type=Path, default=Path("migration/catalog_migration_errors.csv"))
    parser.add_argument("--old-base", default="http://old.gazony.ru", help="Old site base URL.")
    parser.add_argument("--download-images", action="store_true", help="Download product images.")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout per URL (seconds).")
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Повторов запроса страницы при сетевой ошибке (включая первый заход).",
    )
    args = parser.parse_args()

    url_list = [u.strip() for u in args.urls.read_text(encoding="utf-8").splitlines() if u.strip()]
    grouped: dict[str, dict] = {}
    errors: list[tuple[str, str]] = []
    ok_count = 0

    for idx, url in enumerate(url_list, start=1):
        old_url = to_old_domain(url, args.old_base)
        raw = None
        last_exc: Optional[Exception] = None
        for attempt in range(max(1, args.retries)):
            try:
                html_text = fetch(old_url, timeout=args.timeout)
                raw = parse_product_page(html_text, old_url)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt + 1 < max(1, args.retries):
                    time.sleep(2.0 * (attempt + 1))
        if raw is None:
            errors.append((old_url, str(last_exc) if last_exc else "fetch-failed"))
            if idx % 20 == 0:
                print(f"Processed: {idx}/{len(url_list)} | ok={ok_count} | errors={len(errors)}", flush=True)
            continue

        ok_count += 1

        base_name = base_name_for_grouping(raw.get("name", ""))
        if not base_name:
            errors.append((old_url, "empty-name"))
            continue

        group_key = slugify(base_name)
        height, container = extract_variant_from_name(raw.get("name", ""))
        variant = {
            "height": height or "уточняйте",
            "container": container or "формат уточняйте",
            "price": raw.get("price_display") or "уточняйте",
            "in_stock": True,
        }

        if group_key not in grouped:
            image_rel = ""
            if args.download_images and raw.get("image_url"):
                try:
                    rel = image_rel_from_url(raw["image_url"], group_key)
                    dst_static = ROOT / "static" / rel
                    dst_docs = ROOT / "docs" / "static" / rel
                    dst_static.parent.mkdir(parents=True, exist_ok=True)
                    dst_docs.parent.mkdir(parents=True, exist_ok=True)
                    download_file(raw["image_url"], dst_static)
                    dst_docs.write_bytes(dst_static.read_bytes())
                    image_rel = rel
                except Exception as exc:  # noqa: BLE001
                    errors.append((old_url, f"image-download: {exc}"))
            grouped[group_key] = {
                "slug": group_key,
                "name": base_name,
                "category_slug": parse_category_slug(raw.get("legacy_path", "")),
                "image": image_rel,
                "image_url": raw.get("image_url", ""),
                "description": raw.get("description", ""),
                "legacy_paths": [raw.get("legacy_path", "")],
                "variants": [variant],
            }
        else:
            item = grouped[group_key]
            if raw.get("legacy_path"):
                item["legacy_paths"].append(raw["legacy_path"])
            if variant not in item["variants"]:
                item["variants"].append(variant)
            if not item.get("image") and args.download_images and raw.get("image_url"):
                try:
                    rel = image_rel_from_url(raw["image_url"], group_key)
                    dst_static = ROOT / "static" / rel
                    dst_docs = ROOT / "docs" / "static" / rel
                    dst_static.parent.mkdir(parents=True, exist_ok=True)
                    dst_docs.parent.mkdir(parents=True, exist_ok=True)
                    download_file(raw["image_url"], dst_static)
                    dst_docs.write_bytes(dst_static.read_bytes())
                    item["image"] = rel
                except Exception as exc:  # noqa: BLE001
                    errors.append((old_url, f"image-download: {exc}"))

        if idx % 20 == 0:
            print(f"Processed: {idx}/{len(url_list)} | ok={ok_count} | errors={len(errors)}", flush=True)

    # final cleanup
    result = []
    for item in grouped.values():
        item["legacy_paths"] = sorted({p for p in item["legacy_paths"] if p})
        item["catalog_teaser"] = (
            f"от {item['variants'][0]['price']} · {len(item['variants'])} варианта(ов) (высота и формат)"
            if item["variants"]
            else "цена по запросу"
        )
        result.append(item)
    result.sort(key=lambda x: x["name"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    args.errors.parent.mkdir(parents=True, exist_ok=True)
    with args.errors.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "error"])
        writer.writerows(errors)

    print(f"Draft saved: {args.out} (items: {len(result)})")
    print(f"Errors saved: {args.errors} (errors: {len(errors)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
