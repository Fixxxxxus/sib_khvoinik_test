"""Тесты посадочной «Озеленение · финал сезона» и приёма заявок POST /api/lead/.

Битрикс24 и Telegram здесь всегда замоканы: тесты не должны ходить в сеть,
а поведение при их сбое проверяется отдельно (заявка обязана сохраниться).
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from pages.landing_leads import build_telegram_text, format_phone, normalize_phone
from pages.models import LandingLead


def _payload(**overrides) -> dict:
    payload = {
        "name": "Иван",
        "phone": "+7 (900) 000-00-00",
        "consent": True,
        "landing_id": "ozelenenie-season-end",
        "landing_url": "https://gazony.ru/ozelenenie-season-end/?utm_source=yandex",
        "page_path": "/ozelenenie-season-end/",
        "source": "yandex_direct",
        "service_label": "Озеленение · получить предложение",
        "area_label": "от 100 м²",
        "utm": {
            "utm_source": "yandex",
            "utm_medium": "cpc",
            "utm_campaign": "ozelenenie-final",
            "utm_content": "ad-123",
            "utm_term": "озеленение участка",
            "yclid": "9876543210",
        },
        "referrer": "https://yandex.ru/",
    }
    payload.update(overrides)
    return payload


class PhoneNormalizationTest(TestCase):
    def test_accepts_common_input_forms(self):
        self.assertEqual(normalize_phone("+7 (900) 000-00-00"), "79000000000")
        self.assertEqual(normalize_phone("89000000000"), "79000000000")
        self.assertEqual(normalize_phone("9000000000"), "79000000000")

    def test_rejects_garbage(self):
        self.assertEqual(normalize_phone("123"), "")
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone("+1 202 555 0143"), "")

    def test_format_for_humans(self):
        self.assertEqual(format_phone("79000000000"), "+7 (900) 000-00-00")


class LandingLeadApiTest(TestCase):
    def setUp(self):
        cache.clear()  # rate limit по IP живёт в общем кэше и течёт между тестами
        self.client = Client()
        self.b24 = patch("pages.landing_leads._send_to_bitrix").start()
        self.tg = patch("pages.landing_leads._notify_telegram").start()
        self.addCleanup(patch.stopall)

    def _post(self, payload):
        return self.client.post(
            "/api/lead/", data=json.dumps(payload), content_type="application/json"
        )

    def test_success_saves_lead_with_attribution(self):
        res = self._post(_payload())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["lead_id"]), 16)

        lead = LandingLead.objects.get(lead_id=body["lead_id"])
        self.assertEqual(lead.landing_id, "ozelenenie-season-end")
        self.assertEqual(lead.name, "Иван")
        self.assertEqual(lead.phone, "79000000000")
        self.assertEqual(lead.source, "yandex_direct")
        self.assertEqual(lead.utm_campaign, "ozelenenie-final")
        self.assertEqual(lead.utm_content, "ad-123")
        self.assertEqual(lead.yclid, "9876543210")
        self.assertEqual(lead.page_path, "/ozelenenie-season-end/")
        self.assertTrue(lead.consent)
        self.assertEqual(self.b24.call_count, 1)
        self.assertEqual(self.tg.call_count, 1)

    def test_consent_required(self):
        res = self._post(_payload(consent=False))
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertIn("согласие", body["error"].lower())
        self.assertEqual(LandingLead.objects.count(), 0)

    def test_short_name_rejected(self):
        res = self._post(_payload(name="И"))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "name")
        self.assertEqual(LandingLead.objects.count(), 0)

    def test_bad_phone_rejected(self):
        res = self._post(_payload(phone="123"))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "phone")
        self.assertEqual(LandingLead.objects.count(), 0)

    def test_honeypot_is_silently_accepted(self):
        res = self._post(_payload(company_site="https://spam.example"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(LandingLead.objects.count(), 0)
        self.assertEqual(self.tg.call_count, 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/api/lead/").status_code, 405)

    def test_metrika_goal_sent_when_token_and_client_id_present(self):
        with override_settings(), patch("pages.landing_leads.requests.get") as http_get, patch.dict(
            os.environ, {"METRIKA_MP_TOKEN": "secret-token"}
        ):
            http_get.return_value.status_code = 200
            http_get.return_value.text = "<!-- OK -->"
            res = self._post(_payload(ym_client_id="1710232430899999999"))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(http_get.call_count, 1)
        url, kwargs = http_get.call_args[0][0], http_get.call_args[1]
        self.assertEqual(url, "https://mc.yandex.ru/collect/")
        query = kwargs["params"]
        self.assertEqual(query["tid"], "108722541")
        self.assertEqual(query["cid"], "1710232430899999999")
        self.assertEqual(query["t"], "event")
        self.assertEqual(query["ea"], "lead_submit")
        self.assertEqual(query["ms"], "secret-token")
        goal_params = json.loads(query["params"])
        self.assertEqual(goal_params["landing_id"], "ozelenenie-season-end")
        self.assertEqual(goal_params["utm_campaign"], "ozelenenie-final")
        self.assertEqual(goal_params["yclid"], "9876543210")

    def test_metrika_goal_skipped_without_token(self):
        env = {k: v for k, v in os.environ.items() if k != "METRIKA_MP_TOKEN"}
        with patch("pages.landing_leads.requests.get") as http_get, patch.dict(
            os.environ, env, clear=True
        ):
            res = self._post(_payload(ym_client_id="1710232430899999999"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(http_get.call_count, 0)

    def test_metrika_goal_skipped_without_client_id(self):
        with patch("pages.landing_leads.requests.get") as http_get, patch.dict(
            os.environ, {"METRIKA_MP_TOKEN": "secret-token"}
        ):
            res = self._post(_payload())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(http_get.call_count, 0)

    def test_broken_metrika_does_not_break_response(self):
        with patch(
            "pages.landing_leads.requests.get", side_effect=RuntimeError("metrika down")
        ), patch.dict(os.environ, {"METRIKA_MP_TOKEN": "secret-token"}):
            res = self._post(_payload(ym_client_id="17102324308"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(LandingLead.objects.count(), 1)

    def test_broken_bitrix_does_not_break_response(self):
        patch.stopall()
        patch("pages.landing_leads._notify_telegram").start()
        with patch(
            "pages.landing_leads.Bitrix24Client.create_lead", side_effect=RuntimeError("b24 down")
        ):
            res = self._post(_payload())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(LandingLead.objects.count(), 1)


class LandingLeadTelegramTextTest(TestCase):
    def test_alert_carries_landing_id_and_utm(self):
        lead = LandingLead(
            lead_id="a1b2c3d4e5f60718",
            landing_id="ozelenenie-season-end",
            name="Иван",
            phone="79000000000",
            service_label="Озеленение · получить предложение",
            area_label="от 100 м²",
            landing_url="https://gazony.ru/ozelenenie-season-end/",
        )
        text = build_telegram_text(
            lead,
            {"utm_source": "yandex", "utm_campaign": "ozelenenie-final", "yclid": "42"},
        )
        self.assertIn("Заявка: ozelenenie-season-end", text)
        self.assertIn("Телефон: +7 (900) 000-00-00", text)
        self.assertIn("lead_id: a1b2c3d4e5f60718", text)
        self.assertIn("utm_campaign=ozelenenie-final", text)
        self.assertIn("yclid=42", text)


class LandingHealthTest(TestCase):
    def test_health_reports_landing_and_telegram_state(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["landing_id"], "ozelenenie-season-end")
        self.assertIn("telegram_notify", body)
        self.assertIsInstance(body["telegram_notify"], bool)


# В тестах DEBUG выключен, а манифеста collectstatic в рабочей копии нет, поэтому
# на время рендера страницы подменяем хранилище статики на простое.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class LandingPageTest(TestCase):
    def test_page_renders_with_noindex_and_landing_id(self):
        res = self.client.get("/ozelenenie-season-end/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('<meta name="landing-id" content="ozelenenie-season-end" />', html)
        self.assertIn('name="robots" content="noindex,nofollow"', html)
        self.assertIn("Участок, куда хочется возвращаться", html)
        self.assertIn("Получить предложение", html)
        self.assertIn("tel:+73833830060", html)
        self.assertIn('name="company_site"', html)
        self.assertIn("landing-ozelenenie.js", html)

    def test_page_has_no_prices_or_promo_codes(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        # Раздел «Что входит» и hero по ТЗ не должны нести цен, процентов и промокодов.
        body = html.split("<main>")[1].split("</main>")[0]
        for forbidden in ("₽", "-10%", "-50%", "промокод", "Промокод", "скидк", "Скидк"):
            self.assertNotIn(forbidden, body)

    def test_single_phone_on_the_page(self):
        """Одна витрина - один номер (аудит маркетолога, п.7).

        Телефон отдела продаж сайта и Organization-граф с ним на посадочной
        под Директ не должны появляться ни в футере, ни в JSON-LD.
        """
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertIn("tel:+73833830060", html)
        self.assertNotIn("201-06-00", html)
        self.assertNotIn("+73832010600", html)

    def test_no_organization_jsonld(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertNotIn("#organization", html)
        self.assertNotIn("Organization", html)

    def test_hero_eyebrow_without_area_filter(self):
        """«от 100 м²» не в первом экране, но осталось мелко под формой (п.6)."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        # HTML-комментарии на выдаче срезает минификатор, поэтому границу первого
        # экрана ищем по разметке: всё до H1 - это eyebrow, всё до второй секции - hero.
        eyebrow = html.split('id="hero"')[1].split("<h1")[0]
        self.assertNotIn("100 м²", eyebrow)
        self.assertIn("Новосибирск и область · финал сезона", eyebrow)
        # Лид hero, наоборот, объём называет: правка маркетолога от 10.09.2026
        # вернула «от 100 м²» в подзаголовок, но не в eyebrow над H1.
        hero_lead = html.split("</h1>")[1].split("</p>")[0]
        self.assertIn("Озеленение под ключ от 100 м²", hero_lead)
        # Мелкая строка под кнопкой на месте, area_label в лиде не тронут.
        self.assertIn("Берём объекты от 100 м²", html)

    def test_reviews_block_removed(self):
        """Блок отзывов снят с посадочной (правка маркетолога, 10.09.2026).

        Сами данные REVIEWS_DATA остаются: их использует AggregateRating
        на остальных страницах сайта.
        """
        from pages.data import REVIEWS_DATA

        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertNotIn("Что говорят клиенты", html)
        self.assertNotIn("Средняя оценка компании на картах", html)
        self.assertNotIn("на основе %s оценок" % REVIEWS_DATA["aggregate"]["rating_count"], html)
        quoted = [r for r in REVIEWS_DATA["items"] if r["author"] == "Igor Baikalov"][0]
        self.assertNotIn(quoted["text"][:40], html)

    def test_dream_gallery_block_removed(self):
        """Блок «Участок мечты» снят: по вебвизору люди тапали по статичным фото."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertNotIn("Участок мечты", html)
        self.assertNotIn("Так выглядят объекты", html)
        for shot in ("gallery-pines-lawn", "gallery-house-lawn", "gallery-paved-yard"):
            self.assertNotIn(shot, html)

    def test_hero_background_is_ai_shot(self):
        """Реальное фото в hero заменено на AI-кадр из кейса «Коттедж»."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        hero = html.split('id="hero"')[1].split("</section>")[0]
        self.assertIn("cases/cottage-03-after.webp", hero)
        self.assertNotIn("hero-house-lawn.webp", html)

    def test_section_order_matches_marketing_brief(self):
        """Порядок секций: кейсы с «до/после» идут раньше текстовых блоков."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        anchors = (
            'id="hero"',
            "Почему сейчас",
            'id="cases"',
            "Хочу такой результат на своём участке",
            "Что входит",
            "Как проходит",
            "Частые сомнения",
            'id="lead-bottom"',
            "<footer",
        )
        positions = []
        for anchor in anchors:
            pos = html.find(anchor)
            self.assertNotEqual(pos, -1, "не найден якорь секции: %s" % anchor)
            positions.append(pos)
        self.assertEqual(positions, sorted(positions), "порядок секций не совпал с ТЗ")

    def test_landing_uses_marketing_palette(self):
        """Палитра лендинга - именованные токены land-* из tailwind.config.js."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        for token in ("bg-land-sheet", "text-land-heading", "bg-land-green", "border-land-line"):
            self.assertIn(token, html)
        self.assertIn("background: #eef1ec", html)

    def test_cases_rendered_as_three_tabs(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertIn("Как участок из стройки становится садом", html)
        cases = html.split('id="cases"')[1].split("</section>")[0]

        # Три таба и три панели: дача, частный дом, коттедж.
        for key, tab in (("dacha", "Дача"), ("house", "Частный дом"), ("cottage", "Коттедж")):
            self.assertIn('id="case-tab-%s"' % key, cases)
            self.assertIn('id="case-panel-%s"' % key, cases)
            self.assertIn(tab, cases)
        self.assertEqual(cases.count('role="tabpanel"'), 3)
        self.assertEqual(cases.count('role="tab"'), 3)

    def test_cases_have_all_twelve_photos(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        cases = html.split('id="cases"')[1].split("</section>")[0]
        for key in ("dacha", "house", "cottage"):
            for shot in ("01-before", "02-process", "03-after", "04-detail"):
                self.assertIn("cases/%s-%s.webp" % (key, shot), cases)
        # Ленивая загрузка обязательна: двенадцать кадров по ~200 КБ.
        self.assertEqual(cases.count('loading="lazy"'), 12)

    def test_first_case_panel_is_open_without_js(self):
        """Без JS должна быть видна первая панель, остальные - скрыты."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        cases = html.split('id="cases"')[1].split("</section>")[0]
        dacha = cases.split('id="case-panel-dacha"')[1].split(">")[0]
        self.assertNotIn("hidden", dacha)
        for key in ("house", "cottage"):
            panel = cases.split('id="case-panel-%s"' % key)[1].split(">")[0]
            self.assertIn("hidden", panel)
        # Активен только первый таб.
        self.assertEqual(cases.count('aria-selected="true"'), 1)
        self.assertEqual(cases.count('aria-selected="false"'), 2)

    def test_cases_cta_leads_to_bottom_form(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        cases = html.split('id="cases"')[1].split("</section>")[0]
        self.assertIn("Хочу такой результат на своём участке", cases)
        self.assertIn('href="#lead-bottom"', cases)
        self.assertIn("data-cases-cta", cases)

    def test_case_compare_is_two_shots_side_by_side(self):
        """Шторки нет: в каждом кейсе два снимка рядом с подписями «До» и «После»."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        cases = html.split('id="cases"')[1].split("</section>")[0]
        # Мёртвой разметки шторки не осталось.
        for legacy in (
            "data-case-compare-range",
            "data-case-compare-toggle",
            "data-case-compare-side",
            "data-case-compare-overlay",
            "data-before-after-start",
        ):
            self.assertNotIn(legacy, cases)
        # Три кейса, в каждом пара снимков с подписями.
        self.assertEqual(cases.count('data-case-compare="'), 3)
        self.assertEqual(cases.count("<figcaption"), 12)
        self.assertEqual(cases.count(">До<"), 3)
        self.assertEqual(cases.count(">После<"), 3)

    def test_case_shots_are_not_zoomable(self):
        """Приближение снимков убрано: в крупном виде читается генерация."""
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        cases = html.split('id="cases"')[1].split("</section>")[0]
        # По четыре кадра на кейс: до, после, «в работе», деталь.
        self.assertEqual(cases.count("<img"), 12)
        for legacy in ("data-case-zoom", "cursor-zoom-in", "caseLightbox", "data-case-lightbox"):
            self.assertNotIn(legacy, html)

    def test_why_now_cards_have_short_titles(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        for title in ("Окна в графике бригады", "Предложение по вашей заявке", "Один подрядчик"):
            self.assertIn(title, html)

    def test_sticky_mobile_cta_sits_above_cookie_banner(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertIn('id="stickyCta"', html)
        self.assertIn("--sg-cookie-banner-h", html)

    def test_robots_closes_the_landing(self):
        robots = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /ozelenenie-season-end/", robots)

    def test_landing_absent_from_sitemap(self):
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("ozelenenie-season-end", sitemap)
