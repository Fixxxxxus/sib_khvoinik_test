"""Рендер HTML карточек в PNG через Playwright + системный Chromium."""
from __future__ import annotations

import os
import pathlib

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1280, "height": 1280}
SCALE = 2


def chromium_path() -> str:
    return os.environ.get("CARE_CHROMIUM_PATH", "/usr/bin/chromium")


def render_html_to_png(html_docs: list[tuple[str, pathlib.Path]]) -> None:
    """Нарисовать список (html, out_path). Один запуск браузера на весь список."""
    if not html_docs:
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=chromium_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
        try:
            for doc, out_path in html_docs:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                page.set_content(doc, wait_until="networkidle")
                page.wait_for_function("window.__ready === true", timeout=15000)
                page.locator("#card").screenshot(path=str(out_path))
        finally:
            browser.close()
