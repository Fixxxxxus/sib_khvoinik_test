#!/usr/bin/env python3
"""
В уже собранных HTML в docs/ раскомментирует пункт «Статьи» в шапке и футере
(старый маркер <!-- TODO: вернуть когда будет контент ... -->).

Используется когда меняли templates/partials/navbar.html, но не перегоняли
весь каталог/календарь через export_*.

Запуск из корня проекта:
  python3 scripts/patch_docs_navbar_stati.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_raw = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test").strip()
PREFIX = (_raw if _raw.startswith("/") else f"/{_raw}").rstrip("/") or "/sib_khvoinik_test"


def pairs_for_prefix(prefix: str) -> list[tuple[str, str]]:
    p = prefix.rstrip("/") or prefix
    return [
        (
            f"""      <!-- TODO: вернуть когда будет контент
      <a href="{p}/stati/" class="whitespace-nowrap py-1.5 text-[15px] text-slate-700 transition hover:text-brand sm:text-[16px]">Статьи</a>
      -->""",
            f"""      <a href="{p}/stati/" class="whitespace-nowrap py-1.5 text-[15px] text-slate-700 transition hover:text-brand sm:text-[16px]">Статьи</a>""",
        ),
        (
            f"""        <!-- TODO: вернуть когда будет контент
        <a href="{p}/stati/" class="rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-brand/5 hover:text-brand transition">Статьи</a>
        -->""",
            f"""        <a href="{p}/stati/" class="rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-brand/5 hover:text-brand transition">Статьи</a>""",
        ),
        (
            f"""          <!-- TODO: вернуть когда будет контент
          <a class="block text-sm text-slate-700 hover:text-brand transition mt-2" href="{p}/stati/">Статьи</a>
          -->""",
            f"""          <a class="block text-sm text-slate-700 hover:text-brand transition mt-2" href="{p}/stati/">Статьи</a>""",
        ),
    ]


def main() -> int:
    os.chdir(ROOT)
    replacements = pairs_for_prefix(PREFIX)
    changed_files = 0
    total_repls = 0
    docs = ROOT / "docs"
    for path in sorted(docs.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        orig = text
        for old, new in replacements:
            c = text.count(old)
            if c:
                text = text.replace(old, new)
                total_repls += c
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed_files += 1
    print(f"OK: обновлено файлов {changed_files}, замен блоков {total_repls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
