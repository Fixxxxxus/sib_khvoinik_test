"""Общая пост-обработка HTML при экспорте в docs/ (GitHub Pages зеркало).

Зеркало - только fallback/preview, прод живёт на gazony.ru. Поэтому:
1. noindex: зеркало не должно конкурировать с продом в индексе;
2. чиним абсолютные URL на gazony.ru, которым blanket-replace «/static/» в
   apply_site_prefix дописал Pages-префикс.
"""
from __future__ import annotations

NOINDEX_META = '<meta name="robots" content="noindex,nofollow" />'


def postprocess_docs_html(html: str, prefix: str) -> str:
    # Абсолютные URL прода не должны получать Pages-префикс.
    html = html.replace(f"https://gazony.ru{prefix}/static/", "https://gazony.ru/static/")
    if 'name="robots"' not in html and "<head>" in html:
        html = html.replace("<head>", f"<head>\n    {NOINDEX_META}", 1)
    return html


def main() -> None:
    """Прогон постобработки по всем docs/**/*.html. Запускать после экспортов:

        python3 scripts/export_common.py
    """
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    prefix = os.environ.get("SITE_PREFIX", "/sib_khvoinik_test")
    changed = 0
    for f in sorted((root / "docs").rglob("*.html")):
        html = f.read_text(encoding="utf-8")
        fixed = postprocess_docs_html(html, prefix)
        if fixed != html:
            f.write_text(fixed, encoding="utf-8")
            changed += 1
    print(f"OK: постобработано файлов: {changed}")


if __name__ == "__main__":
    main()
