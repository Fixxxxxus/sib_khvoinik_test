"""Тесты скрытого оптового каталога /opt/ и приёма заказов POST /api/opt/order/.

Битрикс24 и Telegram всегда замоканы: тесты не ходят в сеть.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase

from pages import wholesale_pricing
from pages.models import WholesaleItem, WholesaleOrder, WholesaleSection
from pages.wholesale_orders import build_order_lines


def make_catalog() -> tuple[WholesaleSection, WholesaleItem, WholesaleItem]:
    section = WholesaleSection.objects.create(
        title="Тестовые деревья", slug="test-derevya", sort_order=1
    )
    tree = WholesaleItem.objects.create(
        section=section,
        title="Липа тестовая",
        slug="lipa-test",
        size="высота 3 м",
        price=Decimal("6500.00"),
        availability="в наличии 40 шт",
        is_highlighted=True,
    )
    bush = WholesaleItem.objects.create(
        section=section,
        title="Спирея тестовая",
        slug="spireya-test",
        size="C2",
        price=Decimal("380.00"),
    )
    return section, tree, bush


class DiscountGridTest(TestCase):
    """Сетка скидок: пороги живут в одном конфиге, логика их не знает в лицо."""

    def test_no_discount_below_first_threshold(self):
        totals = wholesale_pricing.calculate_totals(Decimal("50000"), 10)
        self.assertEqual(totals["discount_percent"], 0)
        self.assertEqual(totals["discount_amount"], Decimal("0.00"))
        self.assertEqual(totals["total"], Decimal("50000.00"))

    def test_takes_highest_reached_tier(self):
        with patch.object(
            wholesale_pricing, "DISCOUNT_TIERS", ((100_000, 3), (300_000, 5), (500_000, 8))
        ):
            self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("99999"), 1), 0)
            self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("100000"), 1), 3)
            self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("350000"), 1), 5)
            self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("900000"), 1), 8)

    def test_amount_math(self):
        with patch.object(wholesale_pricing, "DISCOUNT_TIERS", ((100_000, 10),)):
            totals = wholesale_pricing.calculate_totals(Decimal("200000"), 5)
        self.assertEqual(totals["discount_percent"], 10)
        self.assertEqual(totals["discount_amount"], Decimal("20000.00"))
        self.assertEqual(totals["total"], Decimal("180000.00"))

    def test_rule_switches_to_quantity_without_touching_logic(self):
        """Смена правила на «по штукам» - это одна константа, а не правка формул."""
        with patch.object(wholesale_pricing, "DISCOUNT_BASIS", "quantity"), patch.object(
            wholesale_pricing, "DISCOUNT_TIERS", ((100, 7),)
        ):
            self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("1000000"), 99), 0)
            totals = wholesale_pricing.calculate_totals(Decimal("50000"), 100)
        self.assertEqual(totals["discount_percent"], 7)
        self.assertEqual(totals["total"], Decimal("46500.00"))


class OptPagesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.section, self.tree, self.bush = make_catalog()

    def test_url_contour_returns_200(self):
        for url in (
            "/opt/",
            f"/opt/{self.section.slug}/",
            f"/opt/{self.section.slug}/{self.tree.slug}/",
        ):
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200)

    def test_pages_are_noindex(self):
        for url in (
            "/opt/",
            f"/opt/{self.section.slug}/",
            f"/opt/{self.section.slug}/{self.tree.slug}/",
        ):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('name="robots"', html)
                self.assertIn("noindex", html)

    def test_card_shows_price_size_and_add_button(self):
        html = self.client.get(f"/opt/{self.section.slug}/{self.tree.slug}/").content.decode()
        self.assertIn("Липа тестовая", html)
        self.assertIn("высота 3 м", html)
        self.assertIn("6500", html)
        self.assertIn("data-opt-add", html)
        self.assertIn("В корзину", html)

    def test_inactive_items_and_sections_are_hidden(self):
        self.bush.is_active = False
        self.bush.save(update_fields=["is_active"])
        res = self.client.get(f"/opt/{self.section.slug}/{self.bush.slug}/")
        self.assertEqual(res.status_code, 404)
        html = self.client.get(f"/opt/{self.section.slug}/").content.decode()
        self.assertNotIn("Спирея тестовая", html)

    def test_unknown_urls_are_404(self):
        self.assertEqual(self.client.get("/opt/net-takogo-razdela/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/opt/{self.section.slug}/net-takoy-pozicii/").status_code, 404
        )

    def test_catalog_is_hidden_from_seo_surfaces(self):
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("/opt/", sitemap)
        self.assertNotIn(self.tree.slug, sitemap)

        llms = self.client.get("/llms.txt").content.decode()
        self.assertNotIn("/opt/", llms)

        robots = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /opt/", robots)

    def test_no_links_from_public_pages(self):
        """Каталог не светится в навигации сайта: ни в меню, ни в футере."""
        home = self.client.get("/").content.decode()
        self.assertNotIn('href="/opt/', home)


class OptOrderApiTest(TestCase):
    def setUp(self):
        cache.clear()  # rate limit по IP живёт в общем кэше и течёт между тестами
        self.client = Client()
        self.section, self.tree, self.bush = make_catalog()
        self.b24 = patch("pages.wholesale_orders._send_to_bitrix").start()
        self.tg = patch("pages.wholesale_orders._notify_telegram").start()
        self.addCleanup(patch.stopall)

    def _post(self, payload):
        return self.client.post(
            "/api/opt/order/", data=json.dumps(payload), content_type="application/json"
        )

    def _payload(self, **overrides):
        payload = {
            "name": "ООО Ромашка",
            "company": "ООО Ромашка",
            "phone": "+7 (900) 000-00-00",
            "email": "opt@example.com",
            "comment": "Самовывоз в четверг",
            "items": [
                {"section": self.section.slug, "slug": self.tree.slug, "qty": 10},
                {"section": self.section.slug, "slug": self.bush.slug, "qty": 100},
            ],
            "utm": {"utm_source": "yandex", "utm_campaign": "opt-derevya"},
            "page_path": "/opt/test-derevya/",
        }
        payload.update(overrides)
        return payload

    def test_order_is_saved_with_lines_and_totals(self):
        res = self._post(self._payload())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])

        order = WholesaleOrder.objects.get(order_id=body["order_id"])
        self.assertEqual(order.name, "ООО Ромашка")
        self.assertEqual(order.phone, "79000000000")
        self.assertEqual(order.total_quantity, 110)
        self.assertEqual(order.lines.count(), 2)

        # 10 x 6500 + 100 x 380 = 103 000 ₽, первый порог сетки взят.
        self.assertEqual(order.subtotal, Decimal("103000.00"))
        expected = wholesale_pricing.calculate_totals(Decimal("103000.00"), 110)
        self.assertEqual(order.discount_percent, expected["discount_percent"])
        self.assertEqual(order.discount_amount, expected["discount_amount"])
        self.assertEqual(order.total, expected["total"])
        self.assertEqual(order.utm_campaign, "opt-derevya")

    def test_price_from_request_is_ignored(self):
        """Цену в теле запроса можно подменить через консоль - сервер её не берёт."""
        payload = self._payload(
            items=[
                {
                    "section": self.section.slug,
                    "slug": self.tree.slug,
                    "qty": 2,
                    "price": 1,
                    "line_total": 2,
                    "title": "Бесплатно",
                }
            ]
        )
        res = self._post(payload)
        order = WholesaleOrder.objects.get(order_id=res.json()["order_id"])
        line = order.lines.get()
        self.assertEqual(line.price, Decimal("6500.00"))
        self.assertEqual(line.line_total, Decimal("13000.00"))
        self.assertEqual(line.title, "Липа тестовая")
        self.assertEqual(order.subtotal, Decimal("13000.00"))

    def test_honeypot_drops_spam(self):
        res = self._post(self._payload(company_site="https://spam.example"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(WholesaleOrder.objects.count(), 0)
        self.b24.assert_not_called()
        self.tg.assert_not_called()

    def test_rate_limit_blocks_flood(self):
        for _ in range(11):
            self._post(self._payload())
        res = self._post(self._payload())
        self.assertEqual(res.status_code, 429)

    def test_validation(self):
        self.assertEqual(self._post(self._payload(name="")).status_code, 400)
        self.assertEqual(self._post(self._payload(phone="123")).status_code, 400)
        self.assertEqual(self._post(self._payload(items=[])).status_code, 400)
        self.assertEqual(WholesaleOrder.objects.count(), 0)

    def test_unknown_and_inactive_items_are_skipped(self):
        self.bush.is_active = False
        self.bush.save(update_fields=["is_active"])
        lines, subtotal, quantity = build_order_lines(
            [
                {"section": self.section.slug, "slug": self.tree.slug, "qty": 1},
                {"section": self.section.slug, "slug": self.bush.slug, "qty": 5},
                {"section": self.section.slug, "slug": "net-takoy", "qty": 3},
            ]
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(subtotal, Decimal("6500.00"))
        self.assertEqual(quantity, 1)

    def test_bitrix_failure_does_not_break_order(self):
        """Сбой Б24 не отменяет заказ: он уже в БД, менеджер увидит его в админке."""
        patch.stopall()
        patch("pages.wholesale_orders._notify_telegram").start()
        b24 = patch("pages.wholesale_orders.Bitrix24Client").start()
        b24.return_value.create_lead.side_effect = RuntimeError("Б24 лежит")

        res = self._post(self._payload())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        order = WholesaleOrder.objects.get()
        self.assertIsNone(order.b24_lead_id)
