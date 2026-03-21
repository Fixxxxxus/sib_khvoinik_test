#!/usr/bin/env python3
"""
Собирает docs/gazon/index.html из templates/pages/gazon.html (как на localhost).
Запуск из корня проекта:
  python3 scripts/export_gazon_page_to_docs.py
Требуется вручную вставить фрагмент в docs/gazon/index.html между <main> и </main>
или доработать скрипт под полную сборку страницы.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMPL = ROOT / "templates/pages/gazon.html"
OUT_FRAG = ROOT / "docs/_gazon_main_fragment.html"
BASE_PREFIX = "/sib_khvoinik_test/static/"


def main() -> None:
    raw = TMPL.read_text(encoding="utf-8")
    m = re.search(r"\{% block content %\}(.*)\{% endblock %\}", raw, re.DOTALL)
    if not m:
        raise SystemExit("Не найден {% block content %} в templates/pages/gazon.html")
    content = m.group(1)
    content = re.sub(r"\{% static '([^']+)' %\}", lambda x: BASE_PREFIX + x.group(1), content)
    OUT_FRAG.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"OK: {OUT_FRAG} ({len(content)} символов)")
    print("Дальше: вставить этот фрагмент в docs/gazon/index.html между <main> и </main>.")


if __name__ == "__main__":
    main()
