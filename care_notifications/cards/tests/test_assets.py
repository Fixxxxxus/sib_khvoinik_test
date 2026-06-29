from django.test import SimpleTestCase
from care_notifications.cards.assets import lucide_src, font_face_css


class AssetsTests(SimpleTestCase):
    def test_lucide_nonempty(self):
        self.assertGreater(len(lucide_src()), 1000)

    def test_font_face_inlines_three_weights(self):
        css = font_face_css()
        self.assertEqual(css.count("@font-face"), 3)
        self.assertIn("data:font/woff2;base64,", css)
        for w in ("500", "700", "800"):
            self.assertIn(f"font-weight:{w}", css)
