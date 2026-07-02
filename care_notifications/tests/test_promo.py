from django.test import TestCase

from care_notifications.models import WeeklyPromo


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
