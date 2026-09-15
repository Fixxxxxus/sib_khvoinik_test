"""Тесты скрытого оптового каталога /opt/ и приёма заказов POST /api/opt/order/.

Битрикс24 и Telegram всегда замоканы: тесты не ходят в сеть.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from django.core.cache import cache
from django.test import Client, TestCase

from pages import wholesale, wholesale_orders, wholesale_pricing
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


class OptShellTest(TestCase):
    """Шапка, hero, лента ступеней, кроп фото, мобильная полоса и бейдж остатка."""

    def setUp(self):
        self.client = Client()
        self.section, self.tree, self.bush = make_catalog()
        self.urls = (
            "/opt/",
            f"/opt/{self.section.slug}/",
            f"/opt/{self.section.slug}/{self.tree.slug}/",
        )

    def test_header_with_cart_is_on_every_page_type(self):
        for url in self.urls:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("sticky top-0", html)
                self.assertIn("logo-main.", html)
                self.assertIn(">Опт<", html)
                self.assertIn(f'href="tel:{wholesale.OPT_PHONE_HREF}"', html)
                self.assertIn("data-opt-cart-open", html)
                self.assertIn("data-opt-cart-count", html)

    def test_hero_lives_only_on_the_storefront(self):
        home = self.client.get("/opt/").content.decode()
        self.assertIn(wholesale.OPT_HERO_TITLE, home)
        self.assertIn("opt-hero-sosna-mugus.", home)
        self.assertIn("Смотреть позиции", home)
        self.assertIn("Позвонить", home)
        for url in self.urls[1:]:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn(wholesale.OPT_HERO_TITLE, html)
                self.assertNotIn("opt-hero-sosna-mugus.", html)

    def test_tier_chips_are_built_from_the_pricing_config(self):
        html = self.client.get("/opt/").content.decode()
        for chip in wholesale_pricing.tiers_for_chips():
            with self.subTest(chip=chip["key"]):
                self.assertIn(f'data-opt-tier-chip="{chip["key"]}"', html)
                self.assertIn(chip["label"], html)
                self.assertIn(chip["value_text"], html)

    def test_tier_chip_rank_grows_with_the_tier(self):
        """Процент заметнее с каждой ступенью: ранг идёт 0,1,2..., у инд. его нет."""
        chips = wholesale_pricing.tiers_for_chips()
        ranks = [c["rank"] for c in chips if not c["individual"]]
        self.assertEqual(ranks, list(range(len(ranks))))
        self.assertIsNone([c for c in chips if c["individual"]][0]["rank"])
        html = self.client.get("/opt/").content.decode()
        self.assertIn("text-brand/70", html)
        self.assertIn("text-emerald-800", html)

    def test_max_button_only_with_a_link(self):
        with patch.object(wholesale, "OPT_MAX_URL", ""):
            html = self.client.get("/opt/").content.decode()
            self.assertNotIn("max.ru", html)
        with patch.object(wholesale, "OPT_MAX_URL", "https://max.ru/u/test"):
            html = self.client.get("/opt/").content.decode()
            self.assertIn('href="https://max.ru/u/test"', html)
            self.assertIn(">MAX<", html)

    def test_changed_grid_changes_the_chips(self):
        """Чипы не хардкод: подправили порог в конфиге - подпись поехала следом."""
        grid = list(wholesale_pricing.DISCOUNT_TIERS)
        grid[1] = dict(grid[1], min_quantity=42)
        with patch.object(wholesale_pricing, "DISCOUNT_TIERS", tuple(grid)):
            html = self.client.get("/opt/").content.decode()
            # Смотрим только общую лестницу: у деревьев своя сетка, там «От 30 шт»
            # остаётся на месте. Проверяем чип, а не конфиг скидок в <script>.
            common = html.split('data-opt-tier-group="derevya"')[0]
            self.assertIn(">От 42 шт<", common)
            self.assertNotIn(">От 30 шт<", common)

    def test_list_tile_crops_the_photo_and_card_keeps_it_whole(self):
        with patch.object(
            WholesaleItem, "cover_url", new_callable=PropertyMock, return_value="/media/test.webp"
        ):
            listing = self.client.get(f"/opt/{self.section.slug}/").content.decode()
        # Плитка списка: кроп по центру и рамка без полей.
        self.assertIn("object-cover object-center", listing)
        self.assertNotIn("bg-slate-100 p-2", listing)

        # Карточка позиции: кадр кропается по центру, без белых полей по бокам
        # (просьба маркетолога 15.09.2026), высоту держит .opt-gallery-frame.
        photo = SimpleNamespace(image=SimpleNamespace(url="/media/test.webp"), alt="Липа")
        # Подменяем настоящей функцией, а не Mock: шаблонизатор Django видит у
        # мока атрибут do_not_call_in_templates и не вызывает его.
        with patch.object(WholesaleItem, "gallery_photos", lambda self: [photo]):
            card = self.client.get(
                f"/opt/{self.section.slug}/{self.tree.slug}/"
            ).content.decode()
        self.assertNotIn("object-contain", card)
        self.assertIn("opt-gallery-frame", card)

    def test_mobile_bar_is_rendered_hidden_and_opens_the_cart(self):
        for url in self.urls:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("data-opt-mobile-bar", html)
                # Полоса приходит скрытой: показывает её JS, когда корзина не пуста.
                self.assertIn("<div data-opt-mobile-bar hidden", html)
                self.assertIn("data-opt-mobile-total", html)
                self.assertIn("Оформить", html)
                # Своего механизма у полосы нет - та же кнопка открытия корзины.
                self.assertIn("sm:hidden", html)

    def test_low_stock_badge_shows_below_the_threshold(self):
        self.assertEqual(self.tree.low_stock_left, 40)
        listing = self.client.get(f"/opt/{self.section.slug}/").content.decode()
        self.assertIn("осталось 40 шт", listing)
        card = self.client.get(f"/opt/{self.section.slug}/{self.tree.slug}/").content.decode()
        self.assertIn("осталось 40 шт", card)

    def test_no_badge_above_the_threshold_or_on_text_availability(self):
        self.tree.availability = f"в наличии {wholesale.LOW_STOCK_THRESHOLD + 10} шт"
        self.tree.save(update_fields=["availability"])
        self.assertIsNone(self.tree.low_stock_left)

        for text in ("в наличии", "уточняйте", ""):
            with self.subTest(text=text):
                self.bush.availability = text
                self.bush.save(update_fields=["availability"])
                self.assertIsNone(self.bush.low_stock_left)

        listing = self.client.get(f"/opt/{self.section.slug}/").content.decode()
        self.assertNotIn("осталось", listing)


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

    def test_bitrix_lead_is_assigned_to_the_wholesale_manager(self):
        """Лид с /opt/ уходит на ответственного из B24_ASSIGNED_BY_ID."""
        patch.stopall()
        patch("pages.wholesale_orders._notify_telegram").start()
        b24 = patch("pages.wholesale_orders.Bitrix24Client").start()
        b24.return_value.create_lead.return_value = 777

        res = self._post(self._payload())
        self.assertEqual(res.status_code, 200)
        kwargs = b24.return_value.create_lead.call_args.kwargs
        self.assertEqual(kwargs["extra_fields"]["ASSIGNED_BY_ID"], wholesale_orders.B24_ASSIGNED_BY_ID)
        self.assertEqual(kwargs["source_id"], wholesale_orders.B24_SOURCE_ID)
        self.assertNotEqual(kwargs["source_id"], "WEB")
        order = WholesaleOrder.objects.get()
        self.assertTrue(kwargs["title"].startswith("Опт: "))
        self.assertIn(f"{order.total_quantity} шт", kwargs["title"])
        self.assertNotIn(order.order_id, kwargs["title"])
        self.assertEqual(WholesaleOrder.objects.get().b24_lead_id, 777)

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

    def test_index_has_no_section_chips(self):
        """Чипы-якоря над группами убраны 14.09.2026, но ссылки живут в шапке.

        15.09.2026 маркетолог попросил вернуть разделы текстом рядом с логотипом:
        якоря переехали в шапку, в теле витрины их по-прежнему нет.
        """
        html = self.client.get("/opt/").content.decode()
        header, _, body = html.partition("</header>")
        self.assertNotIn("#section-kustarniki-test", body)
        self.assertIn("#section-kustarniki-test", header)
        self.assertIn('id="catalog"', html)

    def test_header_links_to_sections(self):
        """Разделы в шапке: на витрине якоря, на остальных страницах - путь на витрину."""
        index = self.client.get("/opt/").content.decode()
        self.assertIn('aria-label="Разделы оптового каталога"', index)
        self.assertIn('href="#section-derevya-test"', index)
        self.assertIn(">Деревья<", index)

        inner = self.client.get("/opt/derevya-test/").content.decode()
        self.assertIn('href="/opt/#section-derevya-test"', inner)


class SectionDiscountGroupsTest(TestCase):
    """Гибридная сетка по разделам: деревья считаются отдельно от остального.

    Сетка деревьев подтверждена маркетологом 15.09.2026: 5 / 10 / 15 / 20 и
    индивидуальные условия сверху. Кустарники и хвойные остаются на 20 / 25 / 30 / 35.
    """

    def test_section_slug_picks_the_ladder(self):
        self.assertEqual(wholesale_pricing.group_key_for_section("derevya"), "derevya")
        self.assertEqual(wholesale_pricing.group_key_for_section("kustarniki"), "default")
        self.assertEqual(wholesale_pricing.group_key_for_section(""), "default")

    def test_thirty_pieces_give_ten_on_trees_and_twenty_five_on_bushes(self):
        trees = wholesale_pricing.calculate_totals(Decimal("30000"), 30, "derevya")
        bushes = wholesale_pricing.calculate_totals(Decimal("30000"), 30)
        self.assertEqual(trees["discount_percent"], 10)
        self.assertEqual(bushes["discount_percent"], 25)

    def test_groups_do_not_share_volume(self):
        """20 деревьев + 20 кустарников: у каждой группы своя входная ступень."""
        totals = wholesale_pricing.calculate_order_totals(
            [
                {"section": "derevya", "price": Decimal("1000"), "quantity": 20},
                {"section": "kustarniki", "price": Decimal("500"), "quantity": 20},
            ]
        )
        self.assertEqual(totals["groups"]["derevya"]["discount_percent"], 5)
        self.assertEqual(totals["groups"]["default"]["discount_percent"], 20)
        self.assertEqual(totals["groups"]["derevya"]["tier_key"], "entry")
        self.assertEqual(totals["groups"]["default"]["tier_key"], "entry")
        # 40 штук в сумме, но ступень «от 30» не берёт ни одна группа.
        self.assertEqual(totals["quantity"], 40)
        self.assertEqual(totals["subtotal"], Decimal("30000.00"))
        # 20 000 x 5% + 10 000 x 20% = 1000 + 2000 = 3000 ₽.
        self.assertEqual(totals["discount_amount"], Decimal("3000.00"))
        self.assertEqual(totals["total"], Decimal("27000.00"))

    def test_check_tier_is_counted_inside_the_group(self):
        """Деревья на 120 000 ₽ берут свои 20%, кустарники на 10 000 ₽ остаются на входных."""
        totals = wholesale_pricing.calculate_order_totals(
            [
                {"section": "derevya", "price": Decimal("12000"), "quantity": 10},
                {"section": "hvoynye", "price": Decimal("1000"), "quantity": 10},
            ]
        )
        self.assertEqual(totals["groups"]["derevya"]["discount_percent"], 20)
        self.assertEqual(totals["groups"]["derevya"]["tier_key"], "a100k")
        self.assertEqual(totals["groups"]["default"]["discount_percent"], 20)
        self.assertEqual(totals["groups"]["default"]["tier_key"], "entry")
        # 120 000 x 20% + 10 000 x 20% = 26 000 ₽.
        self.assertEqual(totals["discount_amount"], Decimal("26000.00"))
        self.assertEqual(totals["discount_percent"], 20)

    def test_individual_in_one_group_marks_the_whole_order(self):
        totals = wholesale_pricing.calculate_order_totals(
            [
                {"section": "derevya", "price": Decimal("3000"), "quantity": 100},
                {"section": "kustarniki", "price": Decimal("500"), "quantity": 2},
            ]
        )
        self.assertTrue(totals["groups"]["derevya"]["individual"])
        self.assertFalse(totals["groups"]["default"]["individual"])
        self.assertTrue(totals["individual"])
        self.assertEqual(totals["individual_note"], wholesale_pricing.INDIVIDUAL_TIER_TEXT)

    def test_tree_price_ladder_follows_its_own_grid(self):
        ladder = wholesale_pricing.price_ladder(Decimal("1000.00"), "derevya")
        self.assertEqual([step["percent"] for step in ladder[1:]], [5, 10, 15, 20, None])
        self.assertEqual(wholesale_pricing.entry_percent("derevya"), 5)
        self.assertEqual(wholesale_pricing.wholesale_price(Decimal("1000.00"), "derevya"), Decimal("950.00"))

    def test_frontend_config_carries_the_tree_ladder(self):
        """Контракт JSON для фронта: by_section.derevya в том же формате, что tiers."""
        config = wholesale_pricing.tiers_for_frontend()
        self.assertEqual(config["entry_percent"], 20)
        block = config["by_section"]["derevya"]
        self.assertEqual(block["entry_percent"], 5)
        # Группа и её название едут рядом с лестницей: фронт не знает наизусть
        # ни слаги разделов, ни русские подписи групп (15.09.2026).
        self.assertEqual(set(block), {"group", "title", "entry_percent", "tiers"})
        self.assertEqual(block["group"], "derevya")
        self.assertEqual(block["title"], "Деревья")
        self.assertEqual(config["group_title"], "Кустарники и хвойные")
        self.assertEqual([tier["key"] for tier in block["tiers"]],
                         [tier["key"] for tier in config["tiers"]])
        self.assertEqual([tier["percent"] for tier in block["tiers"]], [5, 10, 15, 20, None])
        self.assertEqual(
            set(block["tiers"][0]),
            {"key", "label", "short", "percent", "individual", "min_quantity", "min_amount"},
        )
        self.assertTrue(block["tiers"][-1]["individual"])


class SectionLadderPagesTest(TestCase):
    """Страницы деревьев показывают свою лестницу, остальные - общую."""

    def setUp(self):
        self.trees = WholesaleSection.objects.create(title="Деревья", slug="derevya")
        self.bushes = WholesaleSection.objects.create(title="Кустарники", slug="kustarniki")
        self.maple = WholesaleItem.objects.create(
            section=self.trees, title="Клён", slug="klen-test", price=Decimal("1000.00")
        )
        self.spirea = WholesaleItem.objects.create(
            section=self.bushes, title="Спирея", slug="spireya-group-test", price=Decimal("1000.00")
        )

    def test_item_page_uses_the_section_ladder(self):
        res = self.client.get(f"/opt/{self.trees.slug}/{self.maple.slug}/")
        self.assertEqual(res.context["section_group"], "derevya")
        self.assertEqual([s["percent"] for s in res.context["price_ladder"][1:]], [5, 10, 15, 20, None])
        self.assertEqual(res.context["discount_entry_percent"], 5)

        other = self.client.get(f"/opt/{self.bushes.slug}/{self.spirea.slug}/")
        self.assertEqual(other.context["section_group"], "default")
        self.assertEqual([s["percent"] for s in other.context["price_ladder"][1:]], [20, 25, 30, 35, None])

    def test_section_page_carries_its_group(self):
        self.assertEqual(self.client.get(f"/opt/{self.trees.slug}/").context["section_group"], "derevya")
        self.assertEqual(self.client.get(f"/opt/{self.bushes.slug}/").context["section_group"], "default")

    def test_context_has_both_ladders_in_order(self):
        ctx = self.client.get("/opt/").context
        ladders = ctx["discount_ladders"]
        self.assertEqual([l["key"] for l in ladders], ["default", "derevya"])
        self.assertEqual([l["title"] for l in ladders], ["Кустарники и хвойные", "Деревья"])
        self.assertEqual([l["entry_percent"] for l in ladders], [20, 5])
        self.assertTrue(ladders[1]["chips"])
        self.assertTrue(ladders[1]["tiers"])
        self.assertIn('"by_section"', ctx["discount_config_json"])

    def test_storefront_shows_both_ladders(self):
        """Витрина рисует обе лестницы чипами: свои проценты у каждой группы."""
        html = self.client.get("/opt/").content.decode()
        self.assertIn('data-opt-tier-group="default"', html)
        self.assertIn('data-opt-tier-group="derevya"', html)
        self.assertIn("Кустарники и хвойные", html)
        self.assertIn("Входные 20% уже с первой позиции.", html)
        self.assertIn("Входные 5% уже с первой позиции.", html)
        common, _, trees = html.partition('data-opt-tier-group="derevya"')
        self.assertIn(">-25%<", common)
        self.assertIn(">-10%<", trees)
        # Сокращения «инд.» на чипах нет: маркетолог просил слово целиком.
        self.assertIn(">индивидуально<", html)

    def test_storefront_h1_carries_both_entry_discounts(self):
        """H1 витрины собирается из сетки, а не пишется руками."""
        html = self.client.get("/opt/").content.decode()
        self.assertIn("Опт с первой штуки. Кустарники и хвойные −20%, деревья −5%", html)

    def test_tree_card_renders_its_own_ladder(self):
        """Карточка дерева отдаёт лестницу 5 / 10 / 15 / 20 и группу на body."""
        html = self.client.get(f"/opt/{self.trees.slug}/{self.maple.slug}/").content.decode()
        self.assertIn('data-opt-section-group="derevya"', html)
        # Розница 1000 ₽: ступени идут 950 / 900 / 850 / 800 и «индивидуально».
        for price in ("950", "900", "850", "800"):
            with self.subTest(price=price):
                self.assertIn(f">{price} ₽<", html)
        # Общая лестница (650 ₽ = 1000 минус 35%) на дерево не заезжает.
        self.assertNotIn(">650 ₽<", html)

        bush = self.client.get(f"/opt/{self.bushes.slug}/{self.spirea.slug}/").content.decode()
        self.assertIn('data-opt-section-group="default"', bush)
        self.assertIn(">800 ₽<", bush)

    def test_tree_tile_shows_its_own_entry_discount(self):
        """Плитка дерева считает цену по своей группе: 1000 минус 5%."""
        html = self.client.get(f"/opt/{self.trees.slug}/").content.decode()
        self.assertIn("950 ₽", html)
        self.assertIn("Цена при входной скидке 5%", html)
        bushes = self.client.get(f"/opt/{self.bushes.slug}/").content.decode()
        self.assertIn("Цена при входной скидке 20%", bushes)

    def test_back_bar_lives_on_section_and_card_only(self):
        """Липкая плашка «К каталогу» есть у раздела и карточки, у витрины её нет."""
        for url in (f"/opt/{self.trees.slug}/", f"/opt/{self.trees.slug}/{self.maple.slug}/"):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("opt-back-bar", html)
                self.assertIn("К каталогу", html)
                # Крошки без слэшей-разделителей, первая полужирная.
                self.assertIn("opt-crumb", html)
                self.assertNotIn("<span>/</span>", html)
        self.assertNotIn("opt-back-bar", self.client.get("/opt/").content.decode())


class MixedOrderApiTest(TestCase):
    """POST /api/opt/order/ со смешанным заказом: скидка складывается из групп."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.trees = WholesaleSection.objects.create(title="Деревья", slug="derevya")
        self.bushes = WholesaleSection.objects.create(title="Кустарники", slug="kustarniki")
        self.tree = WholesaleItem.objects.create(
            section=self.trees, title="Липа", slug="lipa-mix", price=Decimal("6500.00")
        )
        self.bush = WholesaleItem.objects.create(
            section=self.bushes, title="Спирея", slug="spireya-mix", price=Decimal("380.00")
        )
        patch("pages.wholesale_orders._send_to_bitrix").start()
        patch("pages.wholesale_orders._notify_telegram").start()
        self.addCleanup(patch.stopall)

    def _post(self, items):
        return self.client.post(
            "/api/opt/order/",
            data=json.dumps({"name": "ООО Ромашка", "phone": "+7 (900) 000-00-00", "items": items}),
            content_type="application/json",
        )

    def _mixed_items(self):
        return [
            {"section": "derevya", "slug": self.tree.slug, "qty": 2},
            {"section": "kustarniki", "slug": self.bush.slug, "qty": 10},
        ]

    def test_order_stores_breakdown_by_group(self):
        res = self._post(self._mixed_items())
        self.assertEqual(res.status_code, 200)
        order = WholesaleOrder.objects.get()
        # 2 x 6500 = 13 000 ₽ деревьев (5%) + 10 x 380 = 3800 ₽ кустарников (20%).
        self.assertEqual(order.subtotal, Decimal("16800.00"))
        self.assertEqual(set(order.discount_breakdown), {"derevya", "default"})
        trees = order.discount_breakdown["derevya"]
        bushes = order.discount_breakdown["default"]
        self.assertEqual(trees["percent"], 5)
        self.assertEqual(trees["subtotal"], "13000.00")
        self.assertEqual(trees["discount_amount"], "650.00")
        self.assertEqual(trees["title"], "Деревья")
        self.assertEqual(bushes["percent"], 20)
        self.assertEqual(bushes["discount_amount"], "760.00")
        # Сумма скидок групп, а не процент от общей суммы.
        self.assertEqual(order.discount_amount, Decimal("1410.00"))
        self.assertEqual(order.total, Decimal("15390.00"))
        self.assertEqual(order.discount_percent, 8)
        self.assertEqual(res.json()["groups"]["derevya"]["percent"], 5)

    def test_notification_text_lists_every_group(self):
        self._post(self._mixed_items())
        order = WholesaleOrder.objects.get()
        lines, _, _ = build_order_lines(self._mixed_items())
        text = wholesale_orders.build_order_text(order, lines, {})
        self.assertIn("Деревья: 13000.00 ₽, скидка 5% (650.00 ₽)", text)
        self.assertIn("Кустарники и хвойные: 3800.00 ₽, скидка 20% (760.00 ₽)", text)
        self.assertNotIn(wholesale_pricing.INDIVIDUAL_TIER_TEXT, text)

    def test_minimum_order_is_checked_on_the_whole_subtotal(self):
        """Минимум один на заказ: группы по отдельности его не добирают, вместе - да."""
        with patch.object(wholesale_pricing, "MIN_ORDER_AMOUNT", 16_000):
            ok = self._post(self._mixed_items())
            self.assertEqual(ok.status_code, 200)
            small = self._post([{"section": "derevya", "slug": self.tree.slug, "qty": 2}])
        self.assertEqual(small.status_code, 400)
        self.assertIn("Минимальный заказ от 16 000 ₽", small.json()["error"])

    def test_order_line_knows_its_section(self):
        lines, subtotal, quantity = build_order_lines(self._mixed_items())
        self.assertEqual([line["section"] for line in lines], ["derevya", "kustarniki"])
        self.assertEqual(subtotal, Decimal("16800.00"))
        self.assertEqual(quantity, 12)
