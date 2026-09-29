"""Поиск в админке каталога: кириллица без учёта регистра и группа «Все деревья».

На SQLite штатный поиск Django не находил «Яблоня» по запросу «яблоня», а сортовые
яблони из раздела «Плодовые» пропадали при фильтре «Деревья».
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pages.models import (
    CatalogCategory,
    Plant,
    WholesaleItem,
    WholesaleItemVariant,
    WholesaleSection,
)


class PlantAdminSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_superuser("olga", "olga@example.com", "pass")
        trees = CatalogCategory.objects.create(label="Деревья", slug="derevya", sort_order=1)
        fruit = CatalogCategory.objects.create(label="Плодовые", slug="plodovye", sort_order=7)
        roses = CatalogCategory.objects.create(label="Розы", slug="rozy", sort_order=8)
        cls.decor = Plant.objects.create(name='Яблоня декоративная "Роялти"', slug="yablonya-royalti", category=trees)
        cls.melba = Plant.objects.create(name='Яблоня "Мельба"', slug="yablonya-melba", category=fruit)
        cls.rose = Plant.objects.create(name="Роза чайная", slug="roza-chaynaya", category=roses)
        cls.url = reverse("admin:pages_plant_changelist")

    def setUp(self) -> None:
        self.client.force_login(self.user)

    def names(self, response) -> set[str]:
        return {obj.name for obj in response.context["cl"].result_list}

    def test_lowercase_query_finds_capitalized_names(self) -> None:
        for query in ("яблоня", "ЯБЛОНЯ", "Яблоня", "мельба"):
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})
                self.assertEqual(response.status_code, 200)
                expected = {self.melba.name} if query == "мельба" else {self.decor.name, self.melba.name}
                self.assertEqual(self.names(response), expected)

    def test_all_trees_group_includes_fruit_trees(self) -> None:
        response = self.client.get(self.url, {"razdel": "group:trees", "q": "яблоня"})
        self.assertEqual(self.names(response), {self.decor.name, self.melba.name})

    def test_hint_about_matches_outside_selected_category(self) -> None:
        trees = CatalogCategory.objects.get(slug="derevya")
        response = self.client.get(self.url, {"razdel": str(trees.pk), "q": "яблоня"})
        self.assertEqual(self.names(response), {self.decor.name})
        text = " ".join(str(m) for m in response.context["messages"])
        self.assertIn("Плодовые: 1", text)
        self.assertIn('href="?q=', text)


class WholesaleAdminSearchTests(TestCase):
    def test_search_by_variant_title_case_insensitive(self) -> None:
        user = User.objects.create_superuser("olga", "olga@example.com", "pass")
        section = WholesaleSection.objects.create(title="Деревья", slug="derevya", sort_order=1)
        item = WholesaleItem.objects.create(
            section=section, title="Плодовые деревья", slug="plodovye", price=Decimal("1000")
        )
        WholesaleItemVariant.objects.create(item=item, title="Яблоня Мельба", stock=3)
        self.client.force_login(user)
        response = self.client.get(reverse("admin:pages_wholesaleitem_changelist"), {"q": "мельба"})
        self.assertEqual([obj.pk for obj in response.context["cl"].result_list], [item.pk])
