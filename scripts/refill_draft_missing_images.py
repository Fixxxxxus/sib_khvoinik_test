#!/usr/bin/env python3
"""
Дозагрузка фото для позиций в migration draft, у которых пустые image / image_url.

Берёт первый legacy_path, тянет страницу с old.gazony.ru, парсит (в т.ч. og:image),
скачивает файл в static/ и docs/static/, прописывает image в JSON.

Usage:
  python3 scripts/refill_draft_missing_images.py \\
    --draft migration/catalog_migration_draft.json \\
    --old-base http://old.gazony.ru
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def legacy_to_url(old_base: str, legacy_path: str) -> str:
    base = old_base.rstrip("/") + "/"
    path = (legacy_path or "").strip()
    if not path.startswith("/"):
        path = "/" + path
    return urllib.parse.urljoin(base, path)


def rel_image_path(item: dict, image_url: str) -> str:
    ext = Path(urllib.parse.urlparse(image_url).path).suffix.lower() or ".jpg"
    base = ascii_slug(str(item.get("slug") or item.get("name") or "item"))
    h = hashlib.md5(image_url.encode("utf-8")).hexdigest()[:8]
    return f"media/images/catalog/migrated/{base}-{h}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refill missing catalog images in draft JSON.")
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--old-base", default="http://old.gazony.ru")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-fetch and overwrite image for every item that has legacy_paths (default: only empty image).",
    )
    args = parser.parse_args()

    items: list[dict] = json.loads(args.draft.read_text(encoding="utf-8"))
    ok = 0
    skipped = 0
    errors: list[tuple[str, str]] = []

    work_indices: list[int] = []
    for i, item in enumerate(items):
        has_image = bool((item.get("image") or "").strip())
        if has_image and not args.all:
            skipped += 1
            continue
        if not (item.get("legacy_paths") or []):
            skipped += 1
            continue
        work_indices.append(i)

    total_work = len(work_indices)
    print(f"К обработке (сеть): {total_work} поз., пропуск без изменений: {skipped}", flush=True)

    for n, idx in enumerate(work_indices, start=1):
        item = items[idx]

        url = legacy_to_url(args.old_base, item["legacy_paths"][0])
        label = item.get("name") or item.get("slug") or url
        try:
            html = fetch(url, timeout=args.timeout)
            parsed = parse_product_page(html, url)
        except Exception as exc:  # noqa: BLE001
            errors.append((label, f"fetch/parse: {exc}"))
            continue

        image_url = (parsed.get("image_url") or "").strip()
        if not image_url:
            errors.append((label, "no image_url in parsed page"))
            continue

        rel = rel_image_path(item, image_url)
        dst_static = ROOT / "static" / rel
        dst_docs = ROOT / "docs" / "static" / rel
        try:
            dst_static.parent.mkdir(parents=True, exist_ok=True)
            download_file(image_url, dst_static, timeout=args.timeout)
            dst_docs.parent.mkdir(parents=True, exist_ok=True)
            dst_docs.write_bytes(dst_static.read_bytes())
        except Exception as exc:  # noqa: BLE001
            errors.append((label, f"download: {exc}"))
            continue

        item["image_url"] = image_url
        item["image"] = rel
        # Часто при первой миграции описание = название; если на странице есть текст — подменим.
        desc = (parsed.get("description") or "").strip()
        cur = (item.get("description") or "").strip()
        if desc and (len(desc) > len(cur) + 40 or cur == item.get("name")):
            item["description"] = desc
        ok += 1
        if n % 5 == 0 or n == total_work:
            print(f"… {n}/{total_work} ok={ok} err={len(errors)}", flush=True)

    args.draft.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Draft updated: {args.draft}")
    print(f"Images filled: {ok}, skipped: {skipped}, errors: {len(errors)}")
    for name, err in errors[:25]:
        print(f"  - {name[:60]}… :: {err}")
    if len(errors) > 25:
        print(f"  … and {len(errors) - 25} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
