#!/usr/bin/env python3
"""
В уже собранных HTML в docs/ раскомментирует пункт «Статьи» в шапке и футере
(старый маркер <!-- TODO: вернуть когда будет контент ... -->).

Поддерживает и однострочную разметку ссылки, и формат Django (тег <a> и
«Статьи» на разных строках) — иначе патч не срабатывал на страницах каталога.

Запуск из корня проекта:
  python3 scripts/patch_docs_navbar_stati.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_raw = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").strip()
PREFIX = (_raw if _raw.startswith("/") else f"/{_raw}").rstrip("/") or "/sib_khvoinik_test"


def patch_html(text: str, href_stati: str) -> tuple[str, int]:
    """Возвращает (новый_текст, число_замен)."""
    esc = re.escape(href_stati)
    repls = 0

    # Любой <a href="…/stati/" …> … Статьи … </a> внутри старого HTML-комментария TODO
    pat = re.compile(
        r"<!--\s*TODO:\s*вернуть когда будет контент\s+"
        r'(<a\b[^>]*\bhref="' + esc + r'"[^>]*>\s*Статьи\s*</a>)\s*-->',
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    def _sub(m: re.Match[str]) -> str:
        nonlocal repls
        repls += 1
        return m.group(1)

    text = pat.sub(_sub, text)
    return text, repls


def main() -> int:
    os.chdir(ROOT)
    p = PREFIX.rstrip("/") or PREFIX
    href_stati = f"{p}/stati/"
    changed_files = 0
    total = 0
    docs = ROOT / "docs"
    for path in sorted(docs.rglob("*.html")):
        raw = path.read_text(encoding="utf-8")
        new, n = patch_html(raw, href_stati)
        if n:
            path.write_text(new, encoding="utf-8")
            changed_files += 1
            total += n
    print(f"OK: обновлено файлов {changed_files}, раскомментировано блоков {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
