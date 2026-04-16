#!/usr/bin/env python3
"""
Собрать все URL карточек товара со старого каталога old.gazony.ru, обходя разделы вручную.

Почему не sitemap: в sitemap-iblock-51 нет веток klubnika / odnoletnie_tsvety / ovoshchnaya_rassada.
Здесь: индекс /product/ → хабы → подхабы → страницы с data-item (DETAIL_PAGE_URL) + пагинация PAGEN_1.

Результат — список URL в том же формате, что migration/old_catalog_urls.txt (https://gazony.ru/product/...).

Usage:
  python3 scripts/discover_old_catalog_product_urls.py \\
    --out migration/old_catalog_urls_discovered.txt

  python3 scripts/discover_old_catalog_product_urls.py \\
    --merge migration/old_catalog_urls.txt \\
    --out migration/old_catalog_urls_merged.txt

  # Только «пустые» на новом сайте ветки (быстро):
  python3 scripts/discover_old_catalog_product_urls.py \\
    --hubs klubnika,odnoletnie_tsvety,ovoshchnaya_rassada \\
    --merge migration/old_catalog_urls.txt \\
    --out migration/old_catalog_urls_merged.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.migrate_gazony_product import DEFAULT_UA


def fetch(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_path(href: str) -> str:
    href = href.strip()
    if href.startswith("http://old.gazony.ru"):
        href = href[len("http://old.gazony.ru") :]
    elif href.startswith("https://old.gazony.ru"):
        href = href[len("https://old.gazony.ru") :]
    elif href.startswith("http://gazony.ru"):
        href = href[len("http://gazony.ru") :]
    elif href.startswith("https://gazony.ru"):
        href = href[len("https://gazony.ru") :]
    href = href.split("?")[0].split("#")[0]
    if not href.startswith("/"):
        href = "/" + href
    if not href.endswith("/"):
        href += "/"
    return href


def path_parts(path: str) -> list[str]:
    return [p for p in path.strip("/").split("/") if p]


def to_canonical_product_url(path: str) -> str:
    p = normalize_path(path)
    return "https://gazony.ru" + p.rstrip("/") + "/"


def extract_detail_urls_from_html(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for tag in soup.select("[data-item]"):
        raw = tag.get("data-item")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        u = (data.get("DETAIL_PAGE_URL") or "").strip()
        if not u.startswith("/product/"):
            continue
        out.append(normalize_path(u))
    return out


def likely_product_leaf_segment(seg: str) -> bool:
    """Отличить URL карточки от подраздела при обходе на один уровень глубже."""
    if seg.count("_") >= 3:
        return True
    if len(seg) > 36:
        return True
    return False


def extract_child_hub_paths(html: str, hub_path: str) -> set[str]:
    from bs4 import BeautifulSoup

    hub_path = normalize_path(hub_path)
    hub_n = len(path_parts(hub_path))
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()
    prefix = hub_path.rstrip("/")
    for a in soup.find_all("a", href=True):
        p = normalize_path(a["href"])
        if not p.startswith("/product/"):
            continue
        if not (p.startswith(prefix + "/") or p == hub_path):
            continue
        parts = path_parts(p)
        if len(parts) != hub_n + 1:
            continue
        last = parts[-1]
        if likely_product_leaf_segment(last):
            continue
        found.add(p)
    return found


def discover(
    old_base: str,
    timeout: int,
    delay: float,
    max_pages_per_hub: int,
    seed_hubs: list[str] | None,
) -> tuple[set[str], set[str]]:
    """
    Возвращает (product_paths, hub_visited).
    product_paths — нормализованные пути /product/.../ с завершающим /.

    seed_hubs: только верхние сегменты без «product», например ``["klubnika", "odnoletnie_tsvety"]``.
    Если None — берём все хабы со страницы ``/product/``.
    """
    from bs4 import BeautifulSoup

    base = old_base.rstrip("/")
    hub_queue: deque[str] = deque()
    seen_hubs: set[str] = set()
    products: set[str] = set()

    if seed_hubs:
        for seg in seed_hubs:
            seg = seg.strip().strip("/")
            if not seg or seg.lower().startswith("sezon"):
                continue
            hub_queue.append(normalize_path(f"/product/{seg}/"))
    else:
        index_url = f"{base}/product/"
        html = fetch(index_url, timeout=timeout)
        time.sleep(delay)
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            p = normalize_path(a["href"])
            if not p.startswith("/product/"):
                continue
            parts = path_parts(p)
            if len(parts) != 2 or parts[0] != "product":
                continue
            if parts[1].lower().startswith("sezon"):
                continue
            hub_queue.append(p)

    while hub_queue:
        hub = hub_queue.popleft()
        hub = normalize_path(hub)
        if hub in seen_hubs:
            continue
        seen_hubs.add(hub)

        last_batch_set: set[str] | None = None
        for page in range(1, max_pages_per_hub + 1):
            if page == 1:
                page_url = base + hub.rstrip("/") + "/"
            else:
                page_url = base + hub.rstrip("/") + "/" + f"?PAGEN_1={page}"
            try:
                body = fetch(page_url, timeout=timeout)
            except urllib.error.HTTPError:
                break
            except Exception:
                break
            time.sleep(delay)

            batch = extract_detail_urls_from_html(body)
            if page > 1 and not batch:
                break
            if last_batch_set is not None and set(batch) == last_batch_set:
                break
            last_batch_set = set(batch)
            for u in batch:
                products.add(normalize_path(u))

            # Подразделы могут быть не только на 1-й странице пагинации.
            for child in extract_child_hub_paths(body, hub):
                if child not in seen_hubs:
                    hub_queue.append(child)

        time.sleep(delay)

    return products, seen_hubs


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover old product URLs by crawling catalog hubs.")
    parser.add_argument("--old-base", default="http://old.gazony.ru", help="Base URL of legacy site.")
    parser.add_argument("--out", type=Path, required=True, help="Output text file (one URL per line).")
    parser.add_argument("--merge", type=Path, help="Optional existing URL list to merge with discovered.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.15, help="Pause between HTTP requests (seconds).")
    parser.add_argument("--max-pages", type=int, default=60, help="Max pagination pages per hub.")
    parser.add_argument(
        "--hubs",
        type=str,
        default="",
        help="Только эти верхние разделы (через запятую), без обхода всего индекса. "
        "Пример: klubnika,odnoletnie_tsvety,ovoshchnaya_rassada",
    )
    args = parser.parse_args()

    seed: list[str] | None = None
    if args.hubs.strip():
        seed = [s.strip() for s in args.hubs.split(",") if s.strip()]

    products, hubs = discover(
        old_base=args.old_base,
        timeout=args.timeout,
        delay=args.delay,
        max_pages_per_hub=args.max_pages,
        seed_hubs=seed,
    )
    merged: set[str] = {to_canonical_product_url(p) for p in products}
    if args.merge and args.merge.exists():
        for line in args.merge.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            merged.add(line.split("?")[0].rstrip("/") + "/")

    out_lines = sorted(merged)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Hubs visited: {len(hubs)}")
    print(f"Product URLs (unique): {len(merged)}")
    print(f"Written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
