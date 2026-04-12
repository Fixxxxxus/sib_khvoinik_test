#!/usr/bin/env python3
"""
Парсер карточки товара со старого сайта (Bitrix / Aspro).

Пример:
  python3 scripts/migrate_gazony_product.py \\
    --url http://old.gazony.ru/product/khvoynye/tuya/tuya_zapadnaya_thuja_occidentalis_brabant_s15_h_100_120/

Зависимости: beautifulsoup4 (см. requirements.txt).
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; SibKhvoinikMigration/1.0; +https://gazony.ru/)"
)


def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def absolutize(base: str, path: str) -> str:
    return urllib.parse.urljoin(base, path)


def slug_from_legacy_path(path: str) -> str:
    """/product/khvoynye/tuya/foo_bar/ -> foo-bar (последний сегмент)."""
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "item"
    last = parts[-1]
    return last.replace("_", "-")


def parse_price(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    m = re.search(r"([\d\s]+)\s*₽", t)
    if m:
        num = re.sub(r"\s+", " ", m.group(1).strip())
        return f"{num} ₽"
    return None


def extract_detail_html(soup: BeautifulSoup) -> str:
    block = soup.select_one("div.catalog-detail__detailtext")
    if not block:
        return ""
    # Текст без вложенной вёрстки табов
    return block.get_text("\n", strip=True)


def parse_product_page(html_text: str, page_url: str) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    base = page_url.rsplit("/", 1)[0] + "/" if "/" in page_url else page_url + "/"

    name_meta = soup.select_one('meta[itemprop="name"]')
    raw_name = html.unescape(name_meta["content"].strip()) if name_meta and name_meta.get("content") else ""

    url_link = soup.select_one('link[itemprop="url"]')
    rel_path = ""
    if url_link and url_link.get("href"):
        href = url_link["href"]
        rel_path = "/" + href.strip("/") + "/" if not href.startswith("http") else urllib.parse.urlparse(href).path

    sku_meta = soup.select_one('meta[itemprop="sku"]')
    sku = sku_meta["content"].strip() if sku_meta and sku_meta.get("content") else ""

    img_link = soup.select_one('link[itemprop="image"]')
    image_rel = img_link["href"].strip() if img_link and img_link.get("href") else ""
    image_abs = absolutize(page_url, image_rel) if image_rel else ""

    price_el = soup.select_one("span.price__new-val")
    price_raw = price_el.get_text() if price_el else ""
    price = parse_price(price_raw) or "уточняйте"

    detail_text = extract_detail_html(soup)
    description = detail_text or raw_name

    slug = slug_from_legacy_path(rel_path or urllib.parse.urlparse(page_url).path)

    return {
        "slug": slug,
        "name": raw_name,
        "sku": sku,
        "price_display": price,
        "description": description,
        "image_url": image_abs,
        "legacy_path": rel_path or urllib.parse.urlparse(page_url).path,
    }


def download_file(url: str, dest: Path, timeout: int = 120) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser(description="Спарсить одну карточку old.gazony.ru")
    parser.add_argument("--url", required=True, help="Полный URL детальной страницы товара")
    parser.add_argument(
        "--download-image",
        action="store_true",
        help="Скачать главное фото в static/media/images/catalog/migrated/",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Корень репозитория",
    )
    args = parser.parse_args()

    try:
        body = fetch(args.url)
    except urllib.error.URLError as e:
        print(f"Ошибка загрузки: {e}", file=sys.stderr)
        return 1

    data = parse_product_page(body, args.url)

    rel_image_static = ""
    if args.download_image and data["image_url"]:
        parsed = urllib.parse.urlparse(data["image_url"])
        ext = Path(parsed.path).suffix.lower() or ".jpg"
        safe_slug = re.sub(r"[^a-z0-9-]+", "-", data["slug"].lower()).strip("-")
        filename = f"{safe_slug}{ext}"
        dest = args.project_root / "static" / "media" / "images" / "catalog" / "migrated" / filename
        try:
            download_file(data["image_url"], dest)
            rel_image_static = f"/static/media/images/catalog/migrated/{filename}"
            print(f"Фото: {dest}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"Не удалось скачать фото: {e}", file=sys.stderr)

    # Печать для копирования в data.py (ручной шаг или следующий --apply)
    print("--- parsed ---")
    for k, v in data.items():
        print(f"{k}: {v!r}")
    if rel_image_static:
        print(f"image (static): {rel_image_static!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
