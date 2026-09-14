"""Тесты импорта прайса 1С (xls) в /opt/: сорта и размеры как варианты.

Сам xls в тесте не собираем (xlwt в проекте нет): чтение файла подменяется,
команда получает уже разобранные строки. Разбор наименований проверяется
на строках из реальных прайсов заказчика от 14.09.2026.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from pages.management.commands import import_wholesale_price_xls as cmd
from pages.models import WholesaleItem, WholesaleItemVariant, WholesaleSection


def make_row(line, name, stock, price, description="", picture=None) -> cmd.Row:
    name, tail_notes = cmd.strip_truncated_season(name)
    title, size, notes = cmd.split_title_and_size(name)
    species, sort, latin = cmd.split_species(title)
    return cmd.Row(
        line=line,
        title=title,
        species=species,
        sort=sort,
        latin=latin,
        size=cmd.normalize_size(size),
        notes=notes + tail_notes,
        description=description,
        stock=cmd.parse_stock(stock),
        price=cmd.parse_price(price),
        picture=picture,
    )


class ParsingTest(TestCase):
    def test_split_species_takes_sort_from_quotes_and_latin_apart(self):
        species, sort, latin = cmd.split_species('Дерен белый "Элегантиссима" Cornus alba "Elegantissima"')
        self.assertEqual((species, sort, latin), ("Дерен белый", "Элегантиссима", "Cornus alba"))

    def test_split_species_without_sort_and_with_assortment(self):
        self.assertEqual(cmd.split_species("Клен Гинна́ла Acer tataricum ginnala")[:2], ("Клен Гинна́ла", ""))
        self.assertEqual(cmd.split_species("Барбарис в ассортименте"), ("Барбарис", "", ""))

    def test_parse_stock_reads_1c_numbers(self):
        self.assertEqual(cmd.parse_stock("1 984,000"), 1984)
        self.assertEqual(cmd.parse_stock("21,000"), 21)
        self.assertEqual(cmd.parse_stock(55.0), 55)
        self.assertEqual(cmd.parse_stock(""), 0)

    def test_normalize_size_unifies_container_letter_and_decimals(self):
        self.assertEqual(cmd.normalize_size("h 40-60 C2/3"), "h 40-60 С2/3")
        self.assertEqual(cmd.normalize_size("(ком+сетка) h 3.0-3.5"), "(ком+сетка) h 3,0-3,5")

    def test_truncated_season_tail_becomes_note(self):
        name, notes = cmd.strip_truncated_season('Пузыреплодник "Диабло" h 0,8-1,0 (ком+сетка, D400) О')
        self.assertEqual(name, 'Пузыреплодник "Диабло" h 0,8-1,0 (ком+сетка, D400)')
        self.assertEqual(notes, ["Отгрузка: осень."])
        self.assertEqual(cmd.strip_truncated_season("Спирея серая h 70-90 ОСЕНЬ ")[1], ["Отгрузка: осень."])
        self.assertEqual(cmd.strip_truncated_season("Ива ломкая Salix h 60-80 C3")[1], [])


class MatchingTest(TestCase):
    def setUp(self):
        self.section = WholesaleSection.objects.create(slug="kustarniki", title="Кустарники")
        self.trees = WholesaleSection.objects.create(slug="derevya", title="Деревья")
        self.barbaris = WholesaleItem.objects.create(
            section=self.section, slug="barbaris-v-assortimente", title="Барбарис в ассортименте",
            price=Decimal("690"), is_active=True,
        )
        self.gortenziya = WholesaleItem.objects.create(
            section=self.section, slug="gortenziia-metelchataia-v-assortimente",
            title="Гортензия метельчатая в ассортименте", price=Decimal("1190"), is_active=True,
        )
        self.klen = WholesaleItem.objects.create(
            section=self.trees, slug="klen-ginnala-acer-tataricum-ginnala",
            title="Клен Гинна́ла Acer tataricum ginnala", size="h 60-90 С2/3", price=Decimal("490"), is_active=True,
        )
        self.cheremukha = WholesaleItem.objects.create(
            section=self.trees, slug="cheremukha-virginskaia-shubert",
            title='Черемуха виргинская "Шуберт" Prunus virginiana "Shubert"', price=Decimal("9000"), is_active=True,
        )

    def test_assortment_item_takes_its_genus(self):
        row = make_row(6, 'Барбарис оттавский "Аурикома" Berberis ottawensis "Auricoma" h 40-60 C2/3', "184,000", 690)
        self.assertEqual(cmd.match_item(row, [self.barbaris, self.gortenziya]), self.barbaris)

    def test_other_species_of_the_genus_is_not_glued_to_species_item(self):
        row = make_row(6, 'Гортензия древовидная "Аннабель" Hydrangea arborescens "Annabelle" h 40-60 С2/3', "95,000", 1890)
        self.assertIsNone(cmd.match_item(row, [self.barbaris, self.gortenziya]))
        row = make_row(7, 'Гортензия метельчатая "Мохито" Hydrangea paniculata "Mojito" h 40-60 C2/3', "371,000", 1890)
        self.assertEqual(cmd.match_item(row, [self.barbaris, self.gortenziya]), self.gortenziya)

    def test_exact_species_and_sort_match(self):
        row = make_row(16, "Клен Гинна́ла Acer tataricum ginnala h 2,0-2,5 (Ком+сетка, D600)", "55,000", 11000)
        self.assertEqual(cmd.match_item(row, [self.klen, self.cheremukha]), self.klen)
        row = make_row(26, 'Черемуха виргинская "Шуберт" Prunus virginiana "Shubert" h 2,0-2,5 (Ком+сетка, D600) Осень 2026', "493,000", 9000)
        self.assertEqual(cmd.match_item(row, [self.klen, self.cheremukha]), self.cheremukha)

    def test_variant_titles(self):
        rows = [
            make_row(11, 'Дерен белый "Элегантиссима" Cornus alba "Elegantissima" h 40-60 С2/3', "1 984,000", 620),
            make_row(12, 'Дерен белый "Элегантиссима" Cornus alba "Elegantissima" h 60-80 С5/7,5', "652,000", 1190),
            make_row(28, "Пузыреплодник калинолистный Physocarpus opulifolius h 40-60 C2/3", "105,000", 490),
        ]
        target = cmd.Target(key="item", item=self.barbaris, rows=rows)  # карточка «в ассортименте»
        self.assertEqual(cmd.variant_title(rows[0], target), "Элегантиссима, h 40-60 С2/3")
        self.assertEqual(cmd.variant_title(rows[2], target), "Видовой, h 40-60 С2/3")

        sizes = [
            make_row(26, 'Черемуха "Шуберт" Prunus h 2,0-2,5 (Ком+сетка, D600) Осень 2026', "493,000", 9000),
            make_row(27, 'Черемуха "Шуберт" Prunus h 2,5-3,0 (Ком+сетка, D600) Осень 2026', "485,000", 13900),
        ]
        target = cmd.Target(key="item", item=self.cheremukha, rows=sizes)
        self.assertEqual(cmd.variant_title(sizes[0], target), "h 2,0-2,5 (Ком+сетка, D600), осень 2026")

        same = [
            make_row(7, 'Гортензия метельчатая "Мохито" Hydrangea h 40-60 C2/3', "371,000", 1890),
            make_row(8, 'Гортензия метельчатая "Фантом" Hydrangea h 40-60 С2/3', "109,000", 1190),
        ]
        target = cmd.Target(key="item", item=self.gortenziya, rows=same)
        self.assertEqual(target.common_size(), "h 40-60 С2/3")
        self.assertEqual(cmd.variant_title(same[0], target), "Мохито")

    def test_new_item_title(self):
        rows = [
            make_row(7, "Ель обыкновенная Pícea ábies (ком+сетка) h 0,5-1,0", "29,000", 4500),
            make_row(8, "Ель обыкновенная Pícea ábies (ком+сетка) h 1,5-2,0", "1,000", 9000),
        ]
        self.assertEqual(cmd.new_item_title(cmd.Target(key="new", item=None, rows=rows)), "Ель обыкновенная Pícea ábies")
        single = [make_row(9, "Боярышник Арнольда Crataegus arnoldiana h 2,0-2,5 (ком+сетка, D600) Осень 2026", "60,000", 21900)]
        self.assertEqual(cmd.new_item_title(cmd.Target(key="new", item=None, rows=single)), "Боярышник Арнольда Crataegus arnoldiana")


class CommandTest(TestCase):
    def setUp(self):
        self.section = WholesaleSection.objects.create(slug="kustarniki", title="Кустарники")
        self.gortenziya = WholesaleItem.objects.create(
            section=self.section, slug="gortenziia-metelchataia-v-assortimente",
            title="Гортензия метельчатая в ассортименте", size="h 40-60 С2/3",
            price=Decimal("1190"), availability="в наличии", is_active=True,
        )
        self.rows = [
            make_row(6, 'Гортензия древовидная "Аннабель" Hydrangea arborescens "Annabelle" h 40-60 С2/3', "95,000", 1890, "Раскидистый куст."),
            make_row(7, 'Гортензия метельчатая "Мохито" Hydrangea paniculata "Mojito" h 40-60 C2/3', "371,000", 1890),
            make_row(8, 'Гортензия метельчатая "Фантом" Hydrangea paniculata "Phantom" h 40-60 C2/3', "109,000", 1190),
        ]

    def _run(self, *args):
        with patch.object(cmd, "load_rows", return_value=("кустарники", self.rows, [])), patch.object(
            Path, "is_file", return_value=True
        ):
            call_command("import_wholesale_price_xls", "Гортензия.xls", *args)

    def test_dry_run_writes_nothing(self):
        self._run("--dry-run")
        self.assertEqual(WholesaleItem.objects.count(), 1)
        self.assertEqual(WholesaleItemVariant.objects.count(), 0)

    def test_sorts_become_variants_and_new_species_becomes_item(self):
        self._run()
        self.gortenziya.refresh_from_db()
        variants = list(self.gortenziya.variants.order_by("sort_order"))
        self.assertEqual([v.title for v in variants], ["Мохито", "Фантом"])
        self.assertEqual([v.stock for v in variants], [371, 109])
        self.assertEqual(variants[0].price, Decimal("1890.00"))
        self.assertEqual(self.gortenziya.price, Decimal("1190.00"))
        self.assertEqual(self.gortenziya.availability, "в наличии 480 шт")
        self.assertEqual(self.gortenziya.size, "h 40-60 С2/3")

        annabelle = WholesaleItem.objects.get(section=self.section, slug__startswith="gortenziia-drevovidnaia")
        self.assertEqual(annabelle.title, 'Гортензия древовидная "Аннабель" Hydrangea arborescens "Annabelle"')
        self.assertEqual(annabelle.price, Decimal("1890.00"))
        self.assertEqual(annabelle.availability, "в наличии 95 шт")
        self.assertEqual(annabelle.short_description, "Раскидистый куст.")
        self.assertEqual(annabelle.variants.count(), 0)

    def test_second_run_updates_instead_of_duplicating(self):
        self._run()
        self.rows[1].stock = 5
        self._run()
        self.assertEqual(WholesaleItem.objects.count(), 2)
        self.assertEqual(WholesaleItemVariant.objects.count(), 2)
        self.assertEqual(WholesaleItemVariant.objects.get(title="Мохито").stock, 5)
