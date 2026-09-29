"""Зимовка садового центра у ТЦ МЕГА и акция -50% только в Новопичугово."""

from __future__ import annotations

import json
import re
from datetime import date
from unittest.mock import patch

from django.test import TestCase


def at(day: date):
    return patch("pages.context_processors.timezone.localdate", return_value=day)


class MegaSeasonTests(TestCase):
    def test_last_days_show_closing_date(self) -> None:
        with at(date(2026, 9, 30)):
            html = self.client.get("/sadovye-centry/").content.decode()
        self.assertIn("Работает до 30 сентября", html)
        self.assertIn("закрывается на зиму", html)
        self.assertIn("tel:+79137569016", html)

    def test_after_closing_center_is_closed(self) -> None:
        with at(date(2026, 10, 1)):
            html = self.client.get("/sadovye-centry/").content.decode()
        self.assertIn("Закрыт на зиму", html)
        self.assertIn("Новопичугово работает в обычном режиме", html)
        self.assertNotIn("tel:+79137569016", html)

    def test_jsonld_has_no_opening_hours_for_closed_mega(self) -> None:
        with at(date(2026, 10, 1)):
            html = self.client.get("/").content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        block = next(b for b in blocks if "#gc-mega" in b)
        graph = json.loads(block)["@graph"]
        mega = next(node for node in graph if node.get("@id") == "https://gazony.ru/#gc-mega")
        novo = next(node for node in graph if node.get("@id") == "https://gazony.ru/#gc-novopichugovo")
        self.assertNotIn("openingHoursSpecification", mega)
        self.assertIn("openingHoursSpecification", novo)

    def test_kontakty_marks_mega_closed(self) -> None:
        with at(date(2026, 10, 1)):
            html = self.client.get("/kontakty/").content.decode()
        self.assertIn("Закрыт на зиму, откроется весной", html)


class PromoSale50Tests(TestCase):
    def test_promo_pages_only_novopichugovo_until_october_10(self) -> None:
        # Мега остаётся в общих модалках сайта (со статусом зимовки), поэтому
        # проверяем контент самой акции: данные страницы и её тексты.
        for url in ("/akciya-hvoynye-50/", "/direct-50/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                ctx = response.context
                self.assertEqual([c["name"] for c in ctx["centers"]], ["Садовый центр Новопичугово"])
                self.assertEqual(ctx["primary_phone_tel"], "+79137569061")
                self.assertEqual(ctx["promo_deadline"], "10 октября")
                html = response.content.decode()
                self.assertIn("Акция продлена до 10 октября", html)
                self.assertNotIn("1 октября", html.replace("10 октября", ""))
                self.assertNotIn("«Мега»", html)
                self.assertNotIn("обоих садовых центрах", html)
