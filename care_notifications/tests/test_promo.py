from django.test import Client, TestCase

from care_notifications.digest import build_payload, render_telegram
from care_notifications.models import CareSubscription, WeeklyPromo
from care_notifications.promo import active_promo_for_week, promo_for_payload


class WeeklyPromoModelTest(TestCase):
    def test_defaults_and_week_key_unique(self):
        promo = WeeklyPromo.objects.create(week_key="2026-W28")
        self.assertEqual(promo.status, WeeklyPromo.STATUS_AWAITING)
        self.assertEqual(promo.text, "")
        with self.assertRaises(Exception):
            WeeklyPromo.objects.create(week_key="2026-W28")

    def test_status_choices_cover_lifecycle(self):
        values = {c[0] for c in WeeklyPromo.STATUS_CHOICES}
        self.assertEqual(
            values,
            {"awaiting_content", "review", "confirmed", "sent", "cancelled"},
        )


class PromoGateTest(TestCase):
    def test_active_promo_only_confirmed(self):
        WeeklyPromo.objects.create(week_key="2026-W28", status=WeeklyPromo.STATUS_REVIEW, text="draft")
        self.assertIsNone(active_promo_for_week("2026-W28"))
        WeeklyPromo.objects.filter(week_key="2026-W28").update(status=WeeklyPromo.STATUS_CONFIRMED)
        self.assertIsNotNone(active_promo_for_week("2026-W28"))

    def test_payload_gated_on_subscription_flag(self):
        WeeklyPromo.objects.create(
            week_key="2026-W28", status=WeeklyPromo.STATUS_CONFIRMED, text="Скидка 20%"
        )
        sub_off = CareSubscription.objects.create(promo_subscribed=False)
        sub_on = CareSubscription.objects.create(promo_subscribed=True)
        self.assertEqual(
            promo_for_payload(sub_off, "2026-W28", "https://gazony.ru"), (None, None)
        )
        text, image = promo_for_payload(sub_on, "2026-W28", "https://gazony.ru")
        self.assertEqual(text, "Скидка 20%")
        self.assertIsNone(image)  # картинки нет


class PromoRenderTest(TestCase):
    def test_promo_text_in_telegram_render(self):
        WeeklyPromo.objects.create(
            week_key="2026-W28", status=WeeklyPromo.STATUS_CONFIRMED, text="Розы -20% до воскресенья"
        )
        sub = CareSubscription.objects.create(
            promo_subscribed=True, groups=["seasonal"], preferred_channel="telegram"
        )
        payload = build_payload(sub, week_key="2026-W28")
        self.assertIsNotNone(payload)
        text = render_telegram(payload)
        self.assertIn("Розы -20% до воскресенья", text)

    def test_no_promo_when_not_confirmed(self):
        WeeklyPromo.objects.create(
            week_key="2026-W28", status=WeeklyPromo.STATUS_REVIEW, text="Черновик акции"
        )
        sub = CareSubscription.objects.create(
            promo_subscribed=True, groups=["seasonal"], preferred_channel="telegram"
        )
        payload = build_payload(sub, week_key="2026-W28")
        self.assertNotIn("Черновик акции", render_telegram(payload))


class PromoApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.secret = "test-secret"
        self.admin = 971679598

    def _hdr(self):
        return {"HTTP_X_API_SECRET": self.secret}

    def test_requires_secret(self):
        import care_notifications.views as v
        v._TG_API_SECRET = self.secret
        r = self.client.post("/api/care/tg/promo/start/", data={"telegram_chat_id": self.admin})
        self.assertEqual(r.status_code, 403)

    def test_start_confirm_flow(self):
        import care_notifications.views as v
        v._TG_API_SECRET = self.secret
        v._PROMO_ADMIN_CHAT_ID = str(self.admin)
        r = self.client.post(
            "/api/care/tg/promo/start/",
            data={"telegram_chat_id": self.admin},
            content_type="application/json",
            **self._hdr(),
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["status"], "awaiting_content")

    def test_foreign_chat_id_rejected(self):
        import care_notifications.views as v
        v._TG_API_SECRET = self.secret
        v._PROMO_ADMIN_CHAT_ID = str(self.admin)
        r = self.client.post(
            "/api/care/tg/promo/start/",
            data={"telegram_chat_id": 111},
            content_type="application/json",
            **self._hdr(),
        )
        self.assertEqual(r.status_code, 403)
