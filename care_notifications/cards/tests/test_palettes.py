from django.test import SimpleTestCase
from care_notifications.cards.palettes import PALETTES, SEASON_EMBLEM, CATEGORY_ICON


class PaletteTests(SimpleTestCase):
    def test_all_seasons_present(self):
        self.assertEqual(set(PALETTES), {"spring", "summer", "autumn", "winter"})

    def test_spring_kicker_and_cta_white(self):
        self.assertEqual(PALETTES["spring"]["kicker"], "#FFFFFF")
        self.assertEqual(PALETTES["spring"]["cta_bg"], "#FFFFFF")

    def test_required_fields(self):
        fields = {"bg", "bg_accent", "accent", "accent_ink", "ink", "surface",
                  "body_on_dark", "muted", "kicker", "cta_bg", "cta_ink"}
        for season, p in PALETTES.items():
            self.assertTrue(fields <= set(p), f"{season} missing fields")

    def test_emblems_and_icons(self):
        self.assertEqual(set(SEASON_EMBLEM), {"spring", "summer", "autumn", "winter"})
        for slug in ("derevya", "kustarniki", "mnogoletniki", "rozy", "gazon"):
            self.assertIn(slug, CATEGORY_ICON)
