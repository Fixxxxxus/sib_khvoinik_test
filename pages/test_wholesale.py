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
from pages.models import (
    WholesaleItem,
    WholesaleItemVariant,
    WholesaleOrder,
    WholesaleSection,
)
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
    """Гибридная сетка заказчика: ступени и по количеству, и по чеку."""

    def test_entry_discount_works_from_the_first_position(self):
        """Входные 20% включаются с первой штуки, а не с какого-то порога."""
        totals = wholesale_pricing.calculate_totals(Decimal("490"), 1)
        self.assertEqual(totals["discount_percent"], 20)
        self.assertEqual(totals["discount_amount"], Decimal("98.00"))
        self.assertEqual(totals["total"], Decimal("392.00"))
        self.assertFalse(totals["individual"])

    def test_empty_cart_has_no_discount(self):
        totals = wholesale_pricing.calculate_totals(Decimal("0"), 0)
        self.assertEqual(totals["discount_percent"], 0)

    def test_quantity_tier_beats_amount_tier(self):
        """50 дешёвых штук дают 30%, хотя по чеку взята только входная ступень."""
        percent = wholesale_pricing.discount_percent_for(Decimal("30000"), 50)
        self.assertEqual(percent, 30)
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("30000"), 30), 25)
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("30000"), 29), 20)

    def test_amount_tier_beats_quantity_tier(self):
        """Десять крупномеров - это 35% по чеку, хотя штук меньше тридцати."""
        percent = wholesale_pricing.discount_percent_for(Decimal("115000"), 10)
        self.assertEqual(percent, 35)
        totals = wholesale_pricing.calculate_totals(Decimal("115000"), 10)
        self.assertEqual(totals["discount_amount"], Decimal("40250.00"))
        self.assertEqual(totals["total"], Decimal("74750.00"))

    def test_best_axis_wins_when_both_are_reached(self):
        """Взяты обе оси - применяем ту ступень, что выгоднее клиенту."""
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("150000"), 60), 35)

    def test_top_tier_is_individual_without_a_percent(self):
        """Верхняя ступень - не процент, а текст: менеджер подтверждает цену."""
        totals = wholesale_pricing.calculate_totals(Decimal("250000"), 60)
        self.assertTrue(totals["individual"])
        # Никаких выдуманных процентов сверх последней числовой ступени.
        self.assertEqual(totals["discount_percent"], 35)
        self.assertEqual(totals["individual_note"], wholesale_pricing.INDIVIDUAL_TIER_TEXT)
        self.assertIn("индивидуально", totals["individual_note"].lower())

    def test_grid_is_marked_as_confirmed_by_the_customer(self):
        self.assertTrue(wholesale_pricing.DISCOUNT_TIERS_APPROVED)
        self.assertEqual(wholesale_pricing.DISCOUNT_TIERS_RECEIVED, "10.09.2026")
        self.assertTrue(wholesale_pricing.INDIVIDUAL_TIER_NEEDS_MANUAL_APPROVAL)
        self.assertTrue(wholesale_pricing.MIN_ORDER_APPROVED)
        self.assertEqual(wholesale_pricing.MIN_ORDER_AMOUNT, 15_000)

    def test_individual_tier_starts_at_hundred_pieces(self):
        """Заказчик переопределил порог по количеству: 100 штук, не 50."""
        self.assertEqual(wholesale_pricing.INDIVIDUAL_TIER_MIN_QUANTITY, 100)
        self.assertFalse(wholesale_pricing.is_individual(Decimal("30000"), 99))
        self.assertTrue(wholesale_pricing.is_individual(Decimal("30000"), 100))
        # На 99 штуках работает обычная ступень 30%, а не индивидуальная.
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("30000"), 99), 30)

    def test_cheap_thirty_pieces_and_big_check_pick_the_better_branch(self):
        """Проверка заказчика: 30 дешёвых штук - 25%, чек 100 000 при 5 штуках - 35%."""
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("14700"), 30), 25)
        self.assertEqual(wholesale_pricing.discount_percent_for(Decimal("100000"), 5), 35)

    def test_tiers_for_display_show_text_instead_of_percent_on_top(self):
        rows = wholesale_pricing.tiers_for_display()
        self.assertEqual(rows[0]["percent"], 20)
        self.assertTrue(rows[-1]["individual"])
        self.assertIsNone(rows[-1]["percent"])
        self.assertEqual(rows[-1]["value_text"], wholesale_pricing.INDIVIDUAL_TIER_PRICE_TEXT)


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

    def test_card_shows_price_ladder_stepper_and_progress(self):
        html = self.client.get(f"/opt/{self.section.slug}/{self.tree.slug}/").content.decode()
        self.assertIn("Липа тестовая", html)
        self.assertIn("высота 3 м", html)
        self.assertIn("Розница", html)
        self.assertIn("6 500 ₽", html)
        # Опт-цена с первой позиции: 6500 минус входные 20%.
        self.assertIn("5 200 ₽", html)
        self.assertIn("data-opt-tier-step", html)
        self.assertIn("data-opt-stepper", html)
        self.assertIn("data-opt-progress", html)
        self.assertIn("Минимальный заказ от:", html)
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
                    "qty": 10,
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
        self.assertEqual(line.line_total, Decimal("65000.00"))
        self.assertEqual(line.title, "Липа тестовая")
        self.assertEqual(order.subtotal, Decimal("65000.00"))

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


class PriceLadderTest(TestCase):
    """Ценовая лестница карточки: ступени считаются из розницы и сетки скидок."""

    def test_steps_are_derived_from_retail_and_grid(self):
        ladder = wholesale_pricing.price_ladder(Decimal("1000.00"))
        self.assertEqual(ladder[0]["label"], "Розница")
        self.assertEqual(ladder[0]["price"], Decimal("1000.00"))
        self.assertEqual([step["percent"] for step in ladder[1:]], [20, 25, 30, 35, None])
        self.assertEqual(
            [step["price"] for step in ladder[1:-1]],
            [Decimal("800.00"), Decimal("750.00"), Decimal("700.00"), Decimal("650.00")],
        )

    def test_entry_step_is_the_default_wholesale_price(self):
        """Оптовая цена по умолчанию - розница минус входные 20%."""
        self.assertEqual(wholesale_pricing.entry_percent(), 20)
        self.assertEqual(wholesale_pricing.wholesale_price(Decimal("490.00")), Decimal("392.00"))

    def test_individual_step_has_text_instead_of_price(self):
        ladder = wholesale_pricing.price_ladder(Decimal("11900.00"))
        top = ladder[-1]
        self.assertTrue(top["individual"])
        self.assertIsNone(top["price"])
        self.assertIsNone(top["percent"])
        self.assertEqual(top["price_text"], wholesale_pricing.INDIVIDUAL_TIER_PRICE_TEXT)
        self.assertEqual(top["note"], wholesale_pricing.INDIVIDUAL_TIER_TEXT)

    def test_grid_change_moves_the_whole_ladder(self):
        """Отдельного поля под ступень нет: поменяли сетку - лестница поехала следом."""
        grid = (
            {"key": "entry", "label": "Входная", "percent": 50, "min_quantity": 1,
             "min_amount": None, "individual": False},
        )
        with patch.object(wholesale_pricing, "DISCOUNT_TIERS", grid):
            ladder = wholesale_pricing.price_ladder(Decimal("1000.00"))
        self.assertEqual(ladder[1]["price"], Decimal("500.00"))


class ProgressHintTest(TestCase):
    """Подсказка «сколько добрать»: ведёт к ближайшей ступени по обеим осям."""

    def test_empty_cart_promises_the_entry_discount(self):
        self.assertEqual(
            wholesale_pricing.progress_hint(Decimal("0"), 0),
            "Оптовая скидка 20% включается с первой штуки",
        )

    def test_hint_counts_positions_when_quantity_is_closer(self):
        """До 30 позиций осталось 20 штук, до чека - далеко: ведём по штукам."""
        self.assertEqual(
            wholesale_pricing.progress_hint(Decimal("20000"), 10),
            "До скидки 25% осталось 20 шт",
        )

    def test_hint_counts_money_when_the_check_is_closer(self):
        """До чека 100 000 ₽ осталось 10 000 ₽, до 30 позиций - две трети корзины."""
        self.assertEqual(
            wholesale_pricing.progress_hint(Decimal("90000"), 10),
            "До скидки 35% осталось 10 000 ₽",
        )

    def test_next_tier_switches_axis(self):
        by_quantity = wholesale_pricing.next_tier_for(Decimal("20000"), 10)
        self.assertEqual(by_quantity["axis"], "quantity")
        self.assertEqual(by_quantity["remaining"], Decimal("20"))
        by_amount = wholesale_pricing.next_tier_for(Decimal("90000"), 10)
        self.assertEqual(by_amount["axis"], "amount")
        self.assertEqual(by_amount["remaining"], Decimal("10000"))

    def test_hint_leads_to_individual_tier(self):
        self.assertEqual(
            wholesale_pricing.progress_hint(Decimal("180000"), 55),
            "До индивидуальных условий осталось 20 000 ₽",
        )

    def test_individual_tier_says_text_not_percent(self):
        hint = wholesale_pricing.progress_hint(Decimal("250000"), 60)
        self.assertEqual(hint, wholesale_pricing.INDIVIDUAL_TIER_TEXT)
        self.assertNotIn("%", hint)

    def test_progress_state_carries_tiers_and_min_order(self):
        with patch.object(wholesale_pricing, "MIN_ORDER_AMOUNT", 3_000):
            state = wholesale_pricing.progress_state(Decimal("1000"), 2)
        self.assertEqual(state["percent"], 20)
        self.assertFalse(state["min_order_reached"])
        self.assertEqual(state["min_order_remaining"], Decimal("2000.00"))
        self.assertEqual(len(state["tiers"]), len(wholesale_pricing.DISCOUNT_TIERS))
        self.assertTrue(state["tiers"][0]["reached"])
        self.assertEqual(state["tiers"][0]["fill"], 100.0)


class MinOrderTest(TestCase):
    """Минимальная сумма заказа: фронт кнопку блокирует, сервер проверяет сам."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.section, self.tree, self.bush = make_catalog()
        patch("pages.wholesale_orders._send_to_bitrix").start()
        patch("pages.wholesale_orders._notify_telegram").start()
        self.addCleanup(patch.stopall)

    def _post(self, items):
        return self.client.post(
            "/api/opt/order/",
            data=json.dumps(
                {
                    "name": "ООО Ромашка",
                    "phone": "+7 (900) 000-00-00",
                    "items": items,
                }
            ),
            content_type="application/json",
        )

    def test_order_below_minimum_is_rejected(self):
        with patch.object(wholesale_pricing, "MIN_ORDER_AMOUNT", 30_000):
            res = self._post([{"section": self.section.slug, "slug": self.bush.slug, "qty": 10}])
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertIn("Минимальный заказ от 30 000 ₽", body["error"])
        self.assertIn("ещё на 26 200 ₽", body["error"])
        self.assertEqual(WholesaleOrder.objects.count(), 0)

    def test_order_at_minimum_goes_through(self):
        with patch.object(wholesale_pricing, "MIN_ORDER_AMOUNT", 6_500):
            res = self._post([{"section": self.section.slug, "slug": self.tree.slug, "qty": 1}])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WholesaleOrder.objects.count(), 1)

    def test_min_order_line_is_shown_on_pages(self):
        html = self.client.get(f"/opt/{self.section.slug}/{self.tree.slug}/").content.decode()
        expected = wholesale_pricing.min_order_for_display()["text"]
        self.assertIn(expected, html)


class VariantTest(TestCase):
    """Варианты позиции: свой остаток, своя цена, отдельная строка корзины."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.section, self.tree, self.bush = make_catalog()
        self.blue = WholesaleItemVariant.objects.create(
            item=self.tree, title="Ком 60 см", stock=930, sort_order=10
        )
        self.grey = WholesaleItemVariant.objects.create(
            item=self.tree, title="Ком 80 см", stock=5, price=Decimal("7900.00"), sort_order=20
        )
        patch("pages.wholesale_orders._send_to_bitrix").start()
        patch("pages.wholesale_orders._notify_telegram").start()
        self.addCleanup(patch.stopall)

    def test_card_shows_variants_with_stock_and_steppers(self):
        html = self.client.get(f"/opt/{self.section.slug}/{self.tree.slug}/").content.decode()
        self.assertIn("Ком 60 см", html)
        self.assertIn("Осталось 930", html)
        self.assertIn(f'data-variant="{self.blue.pk}"', html)
        self.assertIn(f'data-variant="{self.grey.pk}"', html)

    def test_variant_price_falls_back_to_item_price(self):
        self.assertEqual(self.blue.effective_price, Decimal("6500.00"))
        self.assertEqual(self.grey.effective_price, Decimal("7900.00"))

    def test_cart_keeps_two_variants_of_one_item_apart(self):
        lines, subtotal, quantity = build_order_lines(
            [
                {"section": self.section.slug, "slug": self.tree.slug, "variant": self.blue.pk, "qty": 2},
                {"section": self.section.slug, "slug": self.tree.slug, "variant": self.grey.pk, "qty": 3},
            ]
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual([line["variant_title"] for line in lines], ["Ком 60 см", "Ком 80 см"])
        # 2 x 6500 + 3 x 7900 = 36 700 ₽
        self.assertEqual(subtotal, Decimal("36700.00"))
        self.assertEqual(quantity, 5)

    def test_quantity_is_capped_by_variant_stock(self):
        lines, subtotal, quantity = build_order_lines(
            [{"section": self.section.slug, "slug": self.tree.slug, "variant": self.grey.pk, "qty": 999}]
        )
        self.assertEqual(quantity, 5)
        self.assertEqual(subtotal, Decimal("39500.00"))

    def test_sold_out_and_foreign_variants_are_skipped(self):
        sold_out = WholesaleItemVariant.objects.create(item=self.tree, title="Нет в наличии", stock=0)
        foreign = WholesaleItemVariant.objects.create(item=self.bush, title="Чужой", stock=10)
        lines, subtotal, quantity = build_order_lines(
            [
                {"section": self.section.slug, "slug": self.tree.slug, "variant": sold_out.pk, "qty": 5},
                {"section": self.section.slug, "slug": self.tree.slug, "variant": foreign.pk, "qty": 5},
            ]
        )
        self.assertEqual(lines, [])
        self.assertEqual(subtotal, Decimal("0.00"))
        self.assertEqual(quantity, 0)

    def test_item_with_variants_needs_an_explicit_choice(self):
        lines, _, _ = build_order_lines(
            [{"section": self.section.slug, "slug": self.tree.slug, "qty": 5}]
        )
        self.assertEqual(lines, [])

    def test_order_stores_variant_on_the_line(self):
        res = self.client.post(
            "/api/opt/order/",
            data=json.dumps(
                {
                    "name": "ООО Ромашка",
                    "phone": "+7 (900) 000-00-00",
                    "items": [
                        {"section": self.section.slug, "slug": self.tree.slug, "variant": self.blue.pk, "qty": 5},
                        {"section": self.section.slug, "slug": self.tree.slug, "variant": self.grey.pk, "qty": 5},
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        order = WholesaleOrder.objects.get()
        self.assertEqual(order.lines.count(), 2)
        line = order.lines.get(variant=self.grey)
        self.assertEqual(line.variant_title, "Ком 80 см")
        # Цена варианта из БД, а не из браузера; количество урезано остатком.
        self.assertEqual(line.price, Decimal("7900.00"))
        self.assertEqual(line.quantity, 5)
        self.assertEqual(order.total_quantity, 10)
        self.assertEqual(order.subtotal, Decimal("72000.00"))


class OptIndexCatalogTest(TestCase):
    """Витрина держит весь каталог на одной странице (просьба заказчика 11.09.2026)."""

    def setUp(self):
        self.section = WholesaleSection.objects.create(
            title="Кустарники", slug="kustarniki-test", is_active=True
        )
        self.other = WholesaleSection.objects.create(
            title="Деревья", slug="derevya-test", is_active=True
        )
        WholesaleItem.objects.create(
            section=self.section, title="Сирень", slug="siren-test",
            size="h 40-60", price=Decimal("750.00"), is_active=True,
        )
        WholesaleItem.objects.create(
            section=self.other, title="Липа", slug="lipa-index-test",
            size="h 1,8-2,5", price=Decimal("5900.00"), is_active=True,
        )

    def test_index_lists_every_item_grouped_by_section(self):
        html = self.client.get("/opt/").content.decode()
        self.assertIn("Сирень", html)
        self.assertIn("Липа", html)
        self.assertIn('id="section-kustarniki-test"', html)
        self.assertIn('id="section-derevya-test"', html)

    def test_index_keeps_links_to_standalone_sections(self):
        html = self.client.get("/opt/").content.decode()
        self.assertIn("/opt/kustarniki-test/", html)
        self.assertIn("#section-kustarniki-test", html)
