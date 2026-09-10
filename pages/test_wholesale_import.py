"""Тесты импорта позиций оптового каталога из прайса заказчика (xlsx).

Файл собираем прямо в тесте: он повторяет реальную структуру top20.xlsx
(шапка, размер внутри наименования, «много» и пустое количество, цена строкой
с запятой), но не зависит от того, лежит ли исходник на диске.
"""

from __future__ import annotations

import io
from decimal import Decimal

import openpyxl
from django.core.management import call_command
from django.test import TestCase

from pages.management.commands.import_wholesale_items import (
    parse_availability,
    parse_price,
    section_for,
    split_title_and_size,
)
from pages.models import WholesaleItem, WholesaleSection

ROWS = [
    (1, "Пузыреплодник калинолистный В АССОРТИМЕНТЕ  h 40-60 С2/3", "много", "шт.", 490, "Кустарники"),
    (2, 'Роза морщинистая "Рубра" Rosa rugosa "Rubra" h 40-60  С5', 2088, "шт.", 1500, "Кустарники"),
    (3, "Барбарис В АССОРТИМЕНТЕ !!!!!  h 30-40 C2/3", "МНОГО", "шт.", 690, "Кустарники"),
    (4, "Липа мелколистная Tilia cordata h 1,8-2,5 (ком+сетка, D500) Н/С Осень 2026", 486, "шт.", 5900, "ДЕРЕВЬЯ"),
    (5, 'Сосна горная "Мугус" Pinus mugo "Mughus" h 50-60 C20', None, None, "11 900,00", "Хвойные "),
    (6, "Битая строка без цены", 10, "шт.", "цена по звонку", "Кустарники"),
]


def make_workbook(path) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Лист2"
    sheet.append(["№", "Наименование", "Кол-во", None, "Розница", "Категория"])
    # Подзаголовок блока, как в файле заказчика: имя раздела без цены.
    sheet.append([None, "Кустарники", None, None, None, None])
    for row in ROWS:
        sheet.append(list(row))
    book.save(path)


class ParsingTest(TestCase):
    """Разбор строки: размер, наличие, цена, категория."""

    def test_size_is_cut_out_of_the_name(self):
        title, size, notes = split_title_and_size(
            "Пузыреплодник калинолистный В АССОРТИМЕНТЕ  h 40-60 С2/3"
        )
        self.assertEqual(title, "Пузыреплодник калинолистный в ассортименте")
        self.assertEqual(size, "h 40-60 С2/3")
        self.assertEqual(notes, [])

    def test_ball_and_net_size_and_season_note(self):
        title, size, notes = split_title_and_size(
            "Липа мелколистная Tilia cordata h 1,8-2,5 (ком+сетка, D500) Н/С Осень 2026"
        )
        self.assertEqual(title, "Липа мелколистная Tilia cordata")
        self.assertEqual(size, "h 1,8-2,5 (ком+сетка, D500)")
        self.assertEqual(notes, ["Отгрузка: осень 2026.", "Отметка заказчика: Н/С."])

    def test_exclamation_marks_are_dropped(self):
        title, size, _ = split_title_and_size("Барбарис В АССОРТИМЕНТЕ !!!!!  h 30-40 C2/3")
        self.assertEqual(title, "Барбарис в ассортименте")
        self.assertEqual(size, "h 30-40 C2/3")

    def test_many_is_not_a_number(self):
        self.assertEqual(parse_availability("много", "шт"), "в наличии")
        self.assertEqual(parse_availability("МНОГО", "шт"), "в наличии")

    def test_empty_quantity_means_ask(self):
        self.assertEqual(parse_availability(None, "шт"), "уточняйте")
        self.assertEqual(parse_availability("   ", "шт"), "уточняйте")

    def test_number_quantity_becomes_text(self):
        self.assertEqual(parse_availability(2088, "шт"), "в наличии 2088 шт")

    def test_price_from_string_with_comma_and_nbsp(self):
        self.assertEqual(parse_price("11 900,00"), Decimal("11900.00"))
        self.assertEqual(parse_price(490), Decimal("490.00"))

    def test_broken_price_raises(self):
        with self.assertRaises(ValueError):
            parse_price("цена по звонку")
        with self.assertRaises(ValueError):
            parse_price(None)

    def test_category_case_and_spaces_are_normalized(self):
        self.assertEqual(section_for("Хвойные ")["slug"], "hvoynye")
        self.assertEqual(section_for("ДЕРЕВЬЯ")["title"], "Деревья")
        self.assertEqual(section_for(" кустарники")["slug"], "kustarniki")


class ImportCommandTest(TestCase):
    """Команда импорта: разделы, обновление без дублей, битые строки."""

    def setUp(self):
        import tempfile

        self.path = tempfile.mktemp(suffix=".xlsx")
        make_workbook(self.path)

    def _run(self, **options) -> str:
        out = io.StringIO()
        err = io.StringIO()
        call_command("import_wholesale_items", self.path, stdout=out, stderr=err, **options)
        return out.getvalue() + err.getvalue()

    def test_import_creates_sections_and_items(self):
        self._run()
        self.assertEqual(WholesaleItem.objects.count(), 5)
        self.assertEqual(
            sorted(WholesaleSection.objects.values_list("slug", flat=True)),
            ["derevya", "hvoynye", "kustarniki"],
        )
        item = WholesaleItem.objects.get(slug="lipa-melkolistnaia-tilia-cordata")
        self.assertEqual(item.section.slug, "derevya")
        self.assertEqual(item.size, "h 1,8-2,5 (ком+сетка, D500)")
        self.assertEqual(item.price, Decimal("5900.00"))
        self.assertEqual(item.availability, "в наличии 486 шт")
        self.assertIn("осень 2026", item.short_description)
        self.assertFalse(item.is_demo)

    def test_conifer_without_quantity_and_price_with_comma(self):
        self._run()
        pine = WholesaleItem.objects.get(section__slug="hvoynye")
        self.assertEqual(pine.price, Decimal("11900.00"))
        self.assertEqual(pine.availability, "уточняйте")
        self.assertEqual(pine.unit, "шт")

    def test_broken_row_is_reported_and_skipped(self):
        output = self._run()
        self.assertIn("пропущена", output)
        self.assertIn("Битая строка без цены", output)
        self.assertFalse(WholesaleItem.objects.filter(title="Битая строка без цены").exists())

    def test_second_run_updates_instead_of_duplicating(self):
        self._run()
        first = set(WholesaleItem.objects.values_list("slug", flat=True))
        WholesaleItem.objects.filter(slug="barbaris-v-assortimente").update(price=Decimal("1.00"))
        self._run()
        self.assertEqual(WholesaleItem.objects.count(), 5)
        self.assertEqual(set(WholesaleItem.objects.values_list("slug", flat=True)), first)
        self.assertEqual(
            WholesaleItem.objects.get(slug="barbaris-v-assortimente").price, Decimal("690.00")
        )

    def test_dry_run_writes_nothing(self):
        output = self._run(dry_run=True)
        self.assertIn("сухой прогон", output)
        self.assertEqual(WholesaleItem.objects.count(), 0)
        self.assertEqual(WholesaleSection.objects.count(), 0)

    def test_drop_demo_removes_stub_items(self):
        section = WholesaleSection.objects.create(
            title="Кустарники", slug="kustarniki", is_demo=True
        )
        WholesaleItem.objects.create(
            section=section, title="Демо-куст", slug="demo-kust", price=Decimal("1.00"), is_demo=True
        )
        self._run(drop_demo=True)
        self.assertFalse(WholesaleItem.objects.filter(is_demo=True).exists())
        # Раздел с тем же слагом остаётся, но уже как реальный, не демо.
        section = WholesaleSection.objects.get(slug="kustarniki")
        self.assertFalse(section.is_demo)
        self.assertTrue(section.items.exists())
