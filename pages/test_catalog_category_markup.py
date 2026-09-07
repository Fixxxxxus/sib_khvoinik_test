"""Тесты облегчения разметки категории каталога (SEO-ТЗ, пункт A5).

Смысл правок: страница категории весила в проде 334 КБ. Мы свернули длинные
наборы Tailwind-классов в компонентные (.pc*, .cnav*), выкинули из HTML полные
описания в data-selection-description и перестали отдавать 42 лишних шаблона
модалок. Ни одно из этих действий не должно уносить со страницы то, за чем
приходит поисковик: названия товаров, ссылки на карточки и цены.

Числа карточек здесь зафиксированы намеренно. Они сняты с рендера ДО правок
(USE_DATABASE_CATALOG=0) и должны совпадать с рендером ПОСЛЕ: если карточки
начнут пропадать, тест упадёт.
"""
import re

from django.test import Client, TestCase, override_settings

from pages.templatetags.catalog_media import selection_description_hint

# Слепок «до правок»: сколько карточек отдают локальные категории из data.py.
CARDS_BEFORE = {
    "hvoynye-derevya": 47,
    "mnogoletnie-tsvety": 282,
}

# В тестовом прогоне DEBUG=False и статика идёт через манифест WhiteNoise,
# которого без collectstatic нет. Нам нужна разметка, а не хэши имён файлов.
render_pages = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)


@render_pages
class CatalogCategoryMarkupTest(TestCase):
    def setUp(self):
        self.client = Client()

    def html(self, slug: str) -> str:
        response = self.client.get(f"/catalog/{slug}/")
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_card_count_unchanged(self):
        """Число карточек товара на категории не изменилось после правок."""
        for slug, expected in CARDS_BEFORE.items():
            with self.subTest(slug=slug):
                html = self.html(slug)
                self.assertEqual(len(re.findall(r"data-selection-add", html)), expected)
                self.assertEqual(len(re.findall(r"data-catalog-more", html)), expected)

    def test_product_links_are_in_html(self):
        """Каждой карточке соответствует ссылка /catalog/<slug>/ в разметке."""
        html = self.html("hvoynye-derevya")
        ids = re.findall(r'data-selection-id="([^"]+)"', html)
        self.assertEqual(len(ids), CARDS_BEFORE["hvoynye-derevya"])
        for slug in ids:
            self.assertIn(f'href="/catalog/{slug}/"', html)

    def test_product_names_and_prices_are_in_html(self):
        """Названия и цены остаются текстом в HTML, а не уезжают в JS."""
        html = self.html("hvoynye-derevya")
        names = re.findall(r'class="pc-t">([^<]+)</div>', html)
        prices = re.findall(r'class="pc-price[^"]*">([^<]+)</div>', html)
        self.assertEqual(len(names), CARDS_BEFORE["hvoynye-derevya"])
        self.assertEqual(len(prices), CARDS_BEFORE["hvoynye-derevya"])
        self.assertIn("Ель канадская", names)
        # Часть позиций идёт тизером «цена по запросу», но большинство - с рублями.
        self.assertEqual(len([p for p in prices if "₽" in p]), 39)

    def test_full_descriptions_are_not_duplicated_into_attributes(self):
        """В data-selection-description остаётся короткая подсказка, а не абзац."""
        html = self.html("mnogoletnie-tsvety")
        values = re.findall(r'data-selection-description="([^"]*)"', html)
        self.assertTrue(all(len(v) <= 60 for v in values), values[:3])

    def test_only_whitelisted_modals_are_rendered(self):
        """Категория отдаёт только свои модалки, остальные страницы - все."""
        html = self.html("hvoynye-derevya")
        ids = set(re.findall(r'<template id="modal-template-([A-Za-z0-9_-]+)">', html))
        self.assertEqual(ids, {"contact_zaboty", "success"})

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        home_ids = set(
            re.findall(
                r'<template id="modal-template-([A-Za-z0-9_-]+)">',
                home.content.decode(),
            )
        )
        self.assertGreater(len(home_ids), 40)
        self.assertIn("gazon_calc", home_ids)

    def test_card_markup_stays_compact(self):
        """Карточка не должна снова обрасти разметкой.

        Меряем сетку карточек до минификации пробелов (её делает middleware).
        До правок карточка весила ~4.6 КБ, после - ~2.6 КБ; порог с запасом.
        """
        html = self.html("hvoynye-derevya")
        grid = re.search(
            r'<div class="[^"]*grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-stretch">.*?\n      </div>',
            html,
            re.S,
        )
        self.assertIsNotNone(grid)
        per_card = len(grid.group(0).encode()) / CARDS_BEFORE["hvoynye-derevya"]
        self.assertLess(per_card, 3200, f"{per_card:.0f} байт на карточку")

    def test_long_tailwind_class_strings_are_folded(self):
        """Длинные наборы утилит свёрнуты в компонентные классы."""
        html = self.html("hvoynye-derevya")
        for utility_soup in (
            "flex h-full min-h-0 flex-col rounded-3xl border border-black/5 bg-white p-6",
            "flex items-start gap-1.5 rounded-lg px-2 py-1.5 text-[13px] leading-snug",
            "relative overflow-visible flex-1 inline-flex items-center justify-center rounded-xl",
        ):
            self.assertNotIn(utility_soup, html)
        for component in ('class="pc"', 'class="pc-add"', 'class="cnav-l'):
            self.assertIn(component, html)


class SelectionDescriptionHintTest(TestCase):
    def test_keeps_bracketed_russian_clarification(self):
        self.assertEqual(
            selection_description_hint("Роза английская (Вильям Шекспир), куст 60 см"),
            "(Вильям Шекспир)",
        )

    def test_keeps_quoted_cultivar(self):
        self.assertEqual(
            selection_description_hint("Роза английская «Нора Барлоу», нежная"),
            "«Нора Барлоу»",
        )

    def test_drops_plain_description(self):
        self.assertEqual(
            selection_description_hint("Крупный кустарник высотой до 2 метров."),
            "",
        )

    def test_handles_empty(self):
        self.assertEqual(selection_description_hint(None), "")
