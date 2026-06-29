from django.test import SimpleTestCase
from care_notifications.cards.templates_html import render_card_html, render_promo_html


class CardHtmlTests(SimpleTestCase):
    def test_card_contains_content_and_font(self):
        html = render_card_html(season="summer", category_label="Деревья",
                                category_icon="tree-deciduous",
                                headline="Активный рост",
                                bullets=["Полив", "Контроль", "Чистота"])
        self.assertIn("Деревья", html)
        self.assertIn("Активный рост", html)
        self.assertIn("@font-face", html)
        self.assertIn('id="card"', html)
        self.assertIn("window.__ready", html)

    def test_card_escapes_html(self):
        html = render_card_html(season="summer", category_label="A&B",
                                category_icon="flower", headline="<x>",
                                bullets=["a<b>"])
        self.assertNotIn("<x>", html.split('id="card"')[1].split("__ready")[0]
                         .replace("&lt;x&gt;", ""))

    def test_promo_contains_cta(self):
        html = render_promo_html("spring")
        self.assertIn("gazony.ru/sluzhba-zaboty", html)
        self.assertIn("СЛУЖБА ЗАБОТЫ", html)
        self.assertIn('id="card"', html)
