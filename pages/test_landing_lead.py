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
        # Первый абзац после H1 - лид hero: фильтра по метражу в нём тоже нет.
        hero_lead = html.split("</h1>")[1].split("</p>")[0]
        self.assertNotIn("100 м²", hero_lead)
        # Мелкая строка под кнопкой на месте, area_label в лиде не тронут.
        self.assertIn("Берём объекты от 100 м²", html)

    def test_reviews_block_rendered_with_jsonld_rating(self):
        from pages.data import REVIEWS_DATA

        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertIn("Что говорят клиенты", html)
        self.assertIn(REVIEWS_DATA["aggregate"]["rating_value"], html)
        self.assertIn(str(REVIEWS_DATA["aggregate"]["rating_count"]), html)
        # Цитаты - реальные тексты из REVIEWS_DATA, не второй набор текстов.
        quoted = [r for r in REVIEWS_DATA["items"] if r["author"] == "Igor Baikalov"][0]
        self.assertIn(quoted["text"][:40], html)

    def test_before_after_cases_rendered(self):
        html = self.client.get("/ozelenenie-season-end/").content.decode()
        self.assertIn("Примеры работ: до и после", html)
        self.assertIn("cases/case-house.webp", html)
        self.assertIn("cases/case-office-yard.webp", html)
        # Ленивая загрузка обязательна: пять карточек по ~200 КБ.
        cases = html.split('id="cases"')[1].split("</section>")[0]
        self.assertEqual(cases.count('loading="lazy"'), 5)

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
