from django.test import SimpleTestCase
from care_notifications.cards.shaper import build_category_card, shape_period


class ShaperFormatATests(SimpleTestCase):
    def test_format_a_dash_bullets(self):
        text = ("Активный ростДерево набирает массу - идёт активное развитие. "
                "Что важно:- умеренный полив- контроль вредителей и болезней- "
                "чистота приствольного круга 👉густая крона = риск")
        r = shape_period(text, "")
        self.assertEqual(r["kind"], "a")
        self.assertEqual(r["headline"], "Активный рост")
        self.assertEqual(r["bullets"],
                         ["Умеренный полив", "Контроль вредителей и болезней",
                          "Чистота приствольного круга"])

    def test_format_a_skips_emoji_subheaders(self):
        text = ("Первая волна цветенияСад играет цветом.\nЧто важно:\n"
                "🌸 Цветущие- удалять отцветшие- удалить цветоносы\n"
                "🌿 Теневые- мягкое питание\n👉избыток азота снижает цветение")
        r = shape_period(text, "")
        self.assertEqual(r["kind"], "a")
        self.assertNotIn("Цветущие", r["bullets"])
        self.assertIn("Удалять отцветшие", r["bullets"])

    def test_format_a_drops_weak_connectors(self):
        text = ("Стабильный режимВажно.\nЧто можно сделать:- регулярная стрижка- "
                "при необходимости - подсев\n👉плотный газон")
        r = shape_period(text, "")
        self.assertNotIn("При необходимости", r["bullets"])


class ShaperFormatBTests(SimpleTestCase):
    def test_format_b_theme_is_topic(self):
        text = "Молодые клёны нужно защитить от мышей и зайцев.\nИспользуйте:\nсетку\nлапник"
        r = shape_period(text, "Защита от грызунов")
        self.assertEqual(r["kind"], "b")
        self.assertEqual(r["topic"], "Защита от грызунов")


class BuildCategoryCardTests(SimpleTestCase):
    def test_format_a_wins_headline_and_bullets(self):
        periods = [
            ("Активный ростРост. Что важно:- умеренный полив- контроль вредителей- "
             "чистота круга 👉риск", ""),
        ]
        card = build_category_card(periods, fallback_headline="Что важно на неделе")
        self.assertEqual(card["headline"], "Активный рост")
        self.assertEqual(len(card["bullets"]), 3)

    def test_format_b_fills_bullets_with_themes(self):
        periods = [
            ("Проза без маркера про укрытие.", "Защита от грызунов"),
            ("Проза без маркера про мульчу.", "Защита на зиму"),
        ]
        card = build_category_card(periods, fallback_headline="Что важно на неделе")
        self.assertEqual(card["headline"], "Что важно на неделе")
        self.assertEqual(card["bullets"], ["Защита от грызунов", "Защита на зиму"])

    def test_empty_periods_no_bullets(self):
        card = build_category_card([], fallback_headline="Х")
        self.assertEqual(card["bullets"], [])
