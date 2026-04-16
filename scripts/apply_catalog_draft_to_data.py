#!/usr/bin/env python3
"""
Apply migration draft plants into pages/data.py CATALOG_PAGE["plants"].

Usage:
  python3 scripts/apply_catalog_draft_to_data.py \
    --draft migration/catalog_migration_draft.json
"""

from __future__ import annotations

import argparse
import json
import pprint
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PY = ROOT / "pages" / "data.py"

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


def teaser_from_variants(variants: list[dict]) -> str:
    prices = [v.get("price", "") for v in variants if v.get("price")]
    if prices:
        return f"от {prices[0]} · {len(variants)} варианта (высота и формат)"
    return "цена по запросу"


def map_item(item: dict, used_slugs: set[str]) -> dict:
    base_slug = ascii_slug(item.get("slug") or item.get("name") or "")
    slug = base_slug
    i = 2
    while slug in used_slugs:
        slug = f"{base_slug}-{i}"
        i += 1
    used_slugs.add(slug)

    variants = item.get("variants") or []
    cat = item.get("category_slug") or "listvennye-kustarniki"
    # Recompute category from legacy path if draft has fallback category.
    legacy_paths = item.get("legacy_paths") or []
    if legacy_paths:
        parts = [p for p in legacy_paths[0].strip("/").split("/") if p]
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
            cat = mapping.get(parts[1], cat)

    return {
        "slug": slug,
        "name": item.get("name"),
        "category_slug": cat,
        "image": item.get("image") or "",
        "image_alt": item.get("name") or "Растение",
        "description": (item.get("description") or "").strip() or "Описание будет добавлено после проверки.",
        "height": "выберите формат ниже",
        "frost": "-35°C",
        "light": "солнце / полутень",
        "catalog_teaser": item.get("catalog_teaser") or teaser_from_variants(variants),
        "variants": variants,
        "legacy_paths": item.get("legacy_paths") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply migrated catalog draft to pages/data.py")
    parser.add_argument("--draft", type=Path, required=True)
    args = parser.parse_args()

    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    used_slugs: set[str] = set()
    plants = [map_item(item, used_slugs) for item in draft if item.get("slug") and item.get("name")]
    plants.sort(key=lambda x: (x["category_slug"], x["name"]))

    data_text = DATA_PY.read_text(encoding="utf-8")

    plants_literal = pprint.pformat(plants, width=120, sort_dicts=False)
    replacement = f'"plants": {plants_literal},\n    "selectionChips":'
    updated, n = re.subn(
        r'"plants": \[.*?\],\n    "selectionChips":',
        lambda _m: replacement,
        data_text,
        flags=re.S,
    )
    if n != 1:
        raise RuntimeError("Could not find unique CATALOG_PAGE plants block in pages/data.py")

    DATA_PY.write_text(updated, encoding="utf-8")
    print(f"Applied plants: {len(plants)}")
    print(f"Updated: {DATA_PY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
