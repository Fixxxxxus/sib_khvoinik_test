"""Тесты первой волны SEO-правок (ТЗ W37).

Покрывают: 301 со старого /ozelenenie/, H1 и развилку направлений на главной,
AggregateOffer на прайсе, лендинг укладки (200 / H1 / Service / FAQPage /
sitemap), входящие ссылки на укладку, перелинковку статей из БД командой
link_ukladka_articles и формулы title/description каталога.
"""
import json
import re

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from pages import views
from pages.data import UKLADKA_PAGE
from pages.management.commands.link_ukladka_articles import UKLADKA_URL
from pages.models import Article


# Тесты рендерят шаблоны, а в тестовом прогоне DEBUG=False и статика идёт через
# манифест WhiteNoise, которого без collectstatic нет. Для тестов достаточно
# простого storage: проверяем разметку, а не хэши имён файлов.
render_pages = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)


def jsonld_blocks(html: str) -> list[dict]:
    """Все JSON-LD со страницы, разобранные как JSON (битый JSON уронит тест)."""
    raw = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    blocks = []
    for chunk in raw:
        data = json.loads(chunk)
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def block_of_type(html: str, type_name: str) -> dict | None:
    for block in jsonld_blocks(html):
        if block.get("@type") == type_name:
            return block
    return None


class RedirectTest(TestCase):
    def test_ozelenenie_301_to_b2c(self):
        resp = Client().get("/ozelenenie/")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], "/ozelenenie-b2c/")


@render_pages
class HomePageTest(TestCase):
    def setUp(self):
        self.html = Client().get("/").content.decode("utf-8")

    def test_h1_covers_three_directions_and_city(self):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, re.S).group(1)
        self.assertIn("Рулонный газон", h1)
        self.assertIn("питомник растений", h1)
        self.assertIn("озеленение", h1)
        self.assertIn("Новосибирске", h1)

    def test_old_claim_kept_as_subheading(self):
        """Старая фраза осталась на странице, но уже не как H1."""
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, re.S).group(1)
        self.assertNotIn("Самый технологичный питомник", h1)
        self.assertIn("Самый технологичный питомник в Сибири", self.html)

    def test_four_direction_links_present(self):
        for href in ("/gazon/", "/catalog/", "/ozelenenie-b2c/", "/sadovye-centry/"):
            self.assertIn('href="%s"' % href, self.html)

    def test_direction_cards_carry_price_or_count(self):
        self.assertIn("от 540 ₽/м²", self.html)
        self.assertIn("от 100 м²", self.html)
        self.assertIn("2 точки в Новосибирске", self.html)
        # Подпись каталога считается из реального размера каталога.
        note = views._catalog_positions_note()
        self.assertIn(note, self.html)

    def test_seo_title_and_description_intact(self):
        title = re.search(r"<title>(.*?)</title>", self.html, re.S).group(1)
        self.assertIn("Рулонный газон, питомник растений и озеленение в Новосибирске", title)
        self.assertIn('<meta name="description" content="Собственное производство', self.html)


@render_pages
class RollLawnPriceTest(TestCase):
    def setUp(self):
        self.html = Client().get("/prais-rulonnyy-gazon/").content.decode("utf-8")

    def test_product_aggregate_offer(self):
        product = block_of_type(self.html, "Product")
        self.assertIsNotNone(product)
        offers = product["offers"]
        self.assertEqual(offers["@type"], "AggregateOffer")
        self.assertEqual(offers["priceCurrency"], "RUB")
        self.assertEqual(offers["lowPrice"], "540")
        self.assertEqual(offers["highPrice"], "590")
        self.assertEqual(offers["offerCount"], "4")
        self.assertEqual(offers["availability"], "https://schema.org/InStock")

    def test_links_to_ukladka(self):
        self.assertIn(UKLADKA_URL, self.html)


@render_pages
class UkladkaLandingTest(TestCase):
    def setUp(self):
        self.resp = Client().get(UKLADKA_URL)
        self.html = self.resp.content.decode("utf-8")

    def test_page_opens_with_h1(self):
        self.assertEqual(self.resp.status_code, 200)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, re.S).group(1).strip()
        self.assertEqual(h1, "Укладка рулонного газона в Новосибирске")

    def test_title_and_description(self):
        title = re.search(r"<title>(.*?)</title>", self.html, re.S).group(1)
        self.assertEqual(
            title,
            "Укладка рулонного газона в Новосибирске: цена за м², сроки | Сибирские газоны",
        )
        self.assertIn("Уложим рулонный газон в Новосибирске", self.html)

    def test_service_and_faq_jsonld(self):
        service = block_of_type(self.html, "Service")
        self.assertIsNotNone(service)
        self.assertEqual(service["name"], "Укладка рулонного газона")
        faq = block_of_type(self.html, "FAQPage")
        self.assertIsNotNone(faq)
        self.assertEqual(len(faq["mainEntity"]), len(UKLADKA_PAGE["faq"]))
        self.assertIsNotNone(block_of_type(self.html, "BreadcrumbList"))

    def test_price_placeholder_never_leaks(self):
        """Пока цена укладки не утверждена, на странице не должно быть [ЦЕНА]."""
        self.assertNotIn("[ЦЕНА]", self.html)

    def test_form_and_fields(self):
        self.assertIn('data-form-tag="B2C/ukladka"', self.html)
        for field in ('name="name"', 'name="phone"', 'name="area"', 'name="photo"'):
            self.assertIn(field, self.html)
        self.assertIn("Получить смету", self.html)

    def test_in_sitemap(self):
        xml = Client().get("/sitemap.xml").content.decode("utf-8")
        self.assertIn("https://gazony.ru" + UKLADKA_URL, xml)


@render_pages
class InboundLinksTest(TestCase):
    def test_gazon_links_to_ukladka(self):
        html = Client().get("/gazon/").content.decode("utf-8")
        self.assertIn('href="%s"' % UKLADKA_URL, html)
        self.assertIn("Заказать укладку", html)

    def test_static_articles_link_to_ukladka(self):
        for slug in (
            "kak-ukladyvat-gazon",
            "rulonnyy-ili-posevnoy-gazon",
            "rulonnyy-gazon-v-zharu",
        ):
            html = Client().get("/stati/%s/" % slug).content.decode("utf-8")
            self.assertIn('href="%s"' % UKLADKA_URL, html, slug)


@render_pages
class LinkUkladkaArticlesCommandTest(TestCase):
    SLUG = "kak-ulozhit-rulonnyy-gazon"

    def setUp(self):
        self.article = Article.objects.create(
            slug=self.SLUG,
            title="Как уложить рулонный газон",
            excerpt="Тест",
            sections=[{"heading": "Подготовка", "paragraphs": ["Текст"]}],
            status=Article.STATUS_PUBLISHED,
            date_published="2026-09-01",
        )

    def links_count(self):
        self.article.refresh_from_db()
        return sum(
            1
            for section in self.article.sections
            for link in section.get("links") or []
            if link.get("href") == UKLADKA_URL
        )

    def test_dry_run_changes_nothing(self):
        before = list(self.article.sections)
        call_command("link_ukladka_articles", "--dry-run")
        self.article.refresh_from_db()
        self.assertEqual(self.article.sections, before)
        self.assertEqual(self.links_count(), 0)

    def test_adds_link_once_and_is_idempotent(self):
        call_command("link_ukladka_articles")
        self.assertEqual(self.links_count(), 1)
        call_command("link_ukladka_articles")
        self.assertEqual(self.links_count(), 1)

    def test_link_renders_on_article_page(self):
        call_command("link_ukladka_articles")
        html = Client().get("/stati/%s/" % self.SLUG).content.decode("utf-8")
        self.assertIn('href="%s"' % UKLADKA_URL, html)
        self.assertIn("заказать укладку рулонного газона", html)


class CatalogSeoFormulaTest(TestCase):
    def test_category_title_and_description(self):
        result = views._category_commercial_seo("Хвойные деревья", 24)
        self.assertEqual(
            result["seo_title"],
            "Хвойные деревья купить в Новосибирске: цена и наличие | Сибирские газоны",
        )
        self.assertIn(
            "Хвойные деревья из собственного питомника под Новосибирском: 24 сорта в наличии",
            result["meta_description"],
        )

    def test_category_without_plants_has_no_zero(self):
        result = views._category_commercial_seo("Пустая", 0)
        self.assertNotIn("0 сорт", result["meta_description"])
        self.assertNotIn("  ", result["meta_description"])
        self.assertIn("адаптированы к сибирской зиме", result["meta_description"])

    def test_subcategory_label_loses_arrow(self):
        result = views._category_commercial_seo("Деревья → Черёмуха", 1)
        self.assertNotIn("→", result["seo_title"])
        self.assertTrue(result["seo_title"].startswith("Черёмуха (деревья) купить"))

    def test_plant_title_with_latin(self):
        plant = {
            "title_ru": "Вяз мелколистный",
            "title_latin": "Ulmus parvifolia",
            "catalog_display_name": "Вяз мелколистный Ulmus parvifolia",
            "height": "выберите формат ниже",
            "variants": [{"height": "h 40-60", "container": "C5/7", "price": "1 590 ₽", "in_stock": True}],
        }
        result = views._plant_commercial_seo(plant)
        self.assertEqual(
            result["seo_title"],
            "Вяз мелколистный (Ulmus parvifolia) купить в Новосибирске "
            "- саженцы из питомника | Сибирские газоны",
        )
        self.assertIn("h 40-60, контейнер C5/7", result["meta_description"])
        self.assertIn("самовывоз в Кольцово", result["meta_description"])

    def test_plant_without_latin_has_no_empty_brackets(self):
        plant = {
            "title_ru": "Вишня Десертная",
            "title_latin": "",
            "catalog_display_name": "Вишня Десертная",
            "height": "уточняйте",
            "variants": [{"height": "уточняйте", "container": "формат уточняйте", "price": "550 ₽"}],
        }
        result = views._plant_commercial_seo(plant)
        self.assertNotIn("()", result["seo_title"])
        self.assertNotIn("  ", result["seo_title"])
        self.assertNotIn("  ", result["meta_description"])
        self.assertNotIn("уточняйте", result["meta_description"])
        self.assertIn("Саженцы Вишня Десертная в Новосибирске: зимостойкость", result["meta_description"])
