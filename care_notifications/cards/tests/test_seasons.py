import datetime as dt
from django.test import SimpleTestCase
from care_notifications.cards.seasons import season_for_date


class SeasonForDateTests(SimpleTestCase):
    def test_siberian_shift_all_months(self):
        expected = {
            1: "winter", 2: "winter", 3: "winter",
            4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "autumn", 10: "autumn",
            11: "winter", 12: "winter",
        }
        for month, season in expected.items():
            self.assertEqual(season_for_date(dt.date(2026, month, 15)), season)
