import json
import pathlib
import tempfile
from unittest import mock
from django.test import TestCase, override_settings
from pages.models import CareCalendarCategory, CareCalendarPlant, CareCalendarPeriod


def _fake_render(html_docs):
    for _html, out in html_docs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"PNG")


class BuildWeekCardsTests(TestCase):
    def setUp(self):
        self.cat = CareCalendarCategory.objects.create(
            label="Деревья", slug="derevya", sort_order=1)
        self.plant = CareCalendarPlant.objects.create(
            name="Клён", slug="klen", primary_category=self.cat,
            sort_order=1, is_published=True)
        CareCalendarPeriod.objects.create(
            plant=self.plant, sort_order=1, date_label="15 июня - 5 июля",
            theme="", content_text=("Активный рост. Что важно:- умеренный полив- "
                                    "контроль вредителей- чистота круга 👉риск"))

    def test_builds_manifest_and_files(self):
        with tempfile.TemporaryDirectory() as d, \
             override_settings(MEDIA_ROOT=d), \
             mock.patch("care_notifications.cards.builder.render_html_to_png", _fake_render):
            from care_notifications.cards.builder import build_week_cards, manifest_path
            man = build_week_cards("2026-W27")
            self.assertEqual(man["season"], "summer")
            self.assertIn("derevya", man["categories"])
            self.assertTrue(manifest_path("2026-W27").exists())
            self.assertEqual(man["categories"]["derevya"]["label"], "Деревья")

    def test_idempotent_skips_second_render(self):
        # mock.patch с new=функция возвращает саму функцию, а не Mock,
        # поэтому оборачиваем в MagicMock(side_effect=...) чтобы иметь call_count
        mock_render = mock.MagicMock(side_effect=_fake_render)
        with tempfile.TemporaryDirectory() as d, \
             override_settings(MEDIA_ROOT=d), \
             mock.patch("care_notifications.cards.builder.render_html_to_png", mock_render) as r:
            from care_notifications.cards.builder import build_week_cards
            build_week_cards("2026-W27")
            calls_after_first = r.call_count
            build_week_cards("2026-W27")
            self.assertEqual(r.call_count, calls_after_first)

    def test_empty_week_no_categories(self):
        with tempfile.TemporaryDirectory() as d, \
             override_settings(MEDIA_ROOT=d), \
             mock.patch("care_notifications.cards.builder.render_html_to_png", _fake_render):
            from care_notifications.cards.builder import build_week_cards
            man = build_week_cards("2026-W50")  # декабрь, контента нет
            self.assertEqual(man["categories"], {})
