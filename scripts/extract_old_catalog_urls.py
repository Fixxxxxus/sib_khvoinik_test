#!/usr/bin/env python3
"""
Extract old Bitrix catalog item URLs from a sitemap XML.

Usage:
  python3 scripts/extract_old_catalog_urls.py \
    --sitemap "/Users/.../public_html/sitemap-iblock-51.xml" \
    --out "migration/old_catalog_urls.txt"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_urls(xml_text: str) -> list[str]:
    return re.findall(r"<loc>(.*?)</loc>", xml_text)


def is_product_detail(url: str) -> bool:
    """
    Keep only detail URLs like /product/category/subcategory/item/.
    Skip root/category hubs.
    """
    path = re.sub(r"^https?://[^/]+", "", url).strip("/")
    if not path.startswith("product/"):
        return False
    parts = [p for p in path.split("/") if p]
    return len(parts) >= 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract old product URLs from sitemap.")
    parser.add_argument("--sitemap", type=Path, required=True, help="Path to sitemap XML.")
    parser.add_argument("--out", type=Path, default=Path("migration/old_catalog_urls.txt"))
    args = parser.parse_args()

    xml_text = args.sitemap.read_text(encoding="utf-8", errors="ignore")
    urls = parse_urls(xml_text)
    product_urls = sorted({u for u in urls if is_product_detail(u)})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(product_urls) + ("\n" if product_urls else ""), encoding="utf-8")

    print(f"Saved: {args.out}")
    print(f"Total URLs: {len(product_urls)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
