"""
Однократный перенос категорий и растений из pages/data.py (CATALOG_PAGE) в БД.

После заполнения БД включите в окружении USE_DATABASE_CATALOG=1 (см. config/settings.py).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.data import CATALOG_PAGE
from pages.models import CatalogCategory, Plant, PlantVariant


class Command(BaseCommand):
    help = "Создаёт/обновляет записи каталога из CATALOG_PAGE в pages/data.py."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--plants-limit",
            type=int,
            default=None,
            metavar="N",
            help="Импортировать не более N растений (для теста). По умолчанию — все.",
        )

    def handle(self, *args, **options) -> None:
        limit = options["plants_limit"]
        cats = CATALOG_PAGE.get("categories") or []
        plants = CATALOG_PAGE.get("plants") or []
        if limit is not None:
            plants = plants[: max(0, limit)]

        with transaction.atomic():
            for c in cats:
                CatalogCategory.objects.update_or_create(
                    slug=str(c.get("slug") or "").strip(),
                    defaults={
                        "label": str(c.get("label") or "").strip() or str(c.get("slug")),
                        "card_label": str(c.get("card_label") or c.get("label") or "").strip(),
                        "description": str(c.get("desc") or "").strip(),
                        "sort_order": cats.index(c),
                        "cover_path": str(c.get("image") or "").strip(),
                        "image_alt": str(c.get("image_alt") or "").strip(),
                        "hub_links": list(c.get("category_hub_links") or []),
                        "legacy_paths": list(c.get("legacy_paths") or []),
                    },
                )

            for raw in plants:
                slug = str(raw.get("slug") or "").strip()
                if not slug:
                    continue
                cat_slug = str(raw.get("category_slug") or "").strip()
                cat = CatalogCategory.objects.filter(slug=cat_slug).first()
                if not cat:
                    self.stderr.write(f"Пропуск {slug}: нет категории {cat_slug}")
                    continue
                desc = (raw.get("description") or "").strip()
                if len(desc) < 20:
                    desc = "Черновик описания — дополните текст в админке (минимум 20 символов)."
                plant, _ = Plant.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "name": str(raw.get("name") or slug).strip(),
                        "category": cat,
                        "description": desc,
                        "cover_path": str(raw.get("image") or "").strip(),
                        "image_alt": str(raw.get("image_alt") or "").strip(),
                        "height_hint": str(raw.get("height") or "").strip(),
                        "frost": str(raw.get("frost") or "").strip(),
                        "light": str(raw.get("light") or "").strip(),
                        "catalog_teaser_override": str(raw.get("catalog_teaser") or "").strip(),
                        "is_new": bool(raw.get("is_new")),
                        "is_published": True,
                        "also_in_category_slugs": list(raw.get("also_in_category_slugs") or []),
                        "legacy_paths": list(raw.get("legacy_paths") or []),
                    },
                )
                plant.variants.all().delete()
                for i, v in enumerate(raw.get("variants") or [{}]):
                    PlantVariant.objects.create(
                        plant=plant,
                        sort_order=i,
                        height=str(v.get("height") or "").strip(),
                        container=str(v.get("container") or "").strip(),
                        price=str(v.get("price") or "").strip(),
                        in_stock=bool(v.get("in_stock", True)),
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: категорий {len(cats)}, растений импортировано {len(plants)} "
                f"(лимит {'нет' if limit is None else limit})."
            )
        )
