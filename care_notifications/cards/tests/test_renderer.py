import os
import pathlib
import shutil
import tempfile
import unittest
from django.test import SimpleTestCase
from care_notifications.cards.renderer import render_html_to_png
from care_notifications.cards.templates_html import render_card_html


def _chromium():
    return os.environ.get("CARE_CHROMIUM_PATH") or shutil.which("chromium") \
        or shutil.which("chromium-browser")


@unittest.skipUnless(_chromium(), "system chromium not available")
class RendererTests(SimpleTestCase):
    def test_renders_png_file(self):
        if "CARE_CHROMIUM_PATH" not in os.environ:
            os.environ["CARE_CHROMIUM_PATH"] = _chromium()
        html = render_card_html(season="summer", category_label="Деревья",
                                category_icon="tree-deciduous", headline="Тест",
                                bullets=["Полив", "Контроль", "Чистота"])
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "card.png"
            render_html_to_png([(html, out)])
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 10000)
