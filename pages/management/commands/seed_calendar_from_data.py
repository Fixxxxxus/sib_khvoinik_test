"""
Однократный импорт календаря из pages/calendar_data.py в модели CareCalendar*.

После импорта в .env задайте USE_DATABASE_CALENDAR=1 и перезапустите сервер.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.calendar_data import CALENDAR_CATEGORIES, CALENDAR_PLANTS
from pages.models import CareCalendarCategory, CareCalendarPeriod, CareCalendarPlant


class Command(BaseCommand):
    help = "Импорт категорий и растений календаря из calendar_data.py в БД."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Удалить все записи календаря в БД перед импортом",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if CareCalendarPlant.objects.exists() and not options["force"]:
            self.stderr.write(
                self.style.WARNING(
                    "В БД уже есть растения календаря. Для повторного импорта запустите с --force "
                    "(удалит все CareCalendar* записи)."
                )
            )
            return

        with transaction.atomic():
            if options["force"]:
                CareCalendarPeriod.objects.all().delete()
                CareCalendarPlant.objects.all().delete()
                CareCalendarCategory.objects.all().delete()

            slug_to_cat: dict[str, CareCalendarCategory] = {}
            for i, row in enumerate(CALENDAR_CATEGORIES):
                slug = (row.get("slug") or "").strip()
                label = (row.get("label") or slug).strip()
                if not slug:
                    continue
                c = CareCalendarCategory.objects.create(
                    label=label or slug,
                    slug=slug,
                    sort_order=i,
                )
                slug_to_cat[slug] = c

            n_plants = 0
            n_periods = 0
            for row in CALENDAR_PLANTS:
                cat_slug = (row.get("category_slug") or "").strip()
                cat = slug_to_cat.get(cat_slug)
                if not cat:
                    self.stderr.write(self.style.WARNING(f"Пропуск растения без категории: {row.get('slug')}"))
                    continue
                varieties = row.get("varieties") or []
                if not isinstance(varieties, list):
                    varieties = []
                plant = CareCalendarPlant(
                    name=(row.get("name") or "").strip() or row.get("slug"),
                    latin=(row.get("latin") or "").strip(),
                    slug=(row.get("slug") or "").strip(),
                    varieties_json=varieties,
                    primary_category=cat,
                    sort_order=n_plants,
                    is_published=True,
                    show_paid_service_cta=False,
                    yonote_id=str(row.get("yonote_id") or "")[:80],
                )
                plant.save()
                plant.categories.add(cat)
                n_plants += 1
                for j, per in enumerate(row.get("periods") or []):
                    if not isinstance(per, dict):
                        continue
                    imgs = per.get("images") or []
                    if not isinstance(imgs, list):
                        imgs = []
                    prods = per.get("products") or []
                    if not isinstance(prods, list):
                        prods = []
                    vids = per.get("videos") or []
                    if not isinstance(vids, list):
                        vids = []
                    CareCalendarPeriod.objects.create(
                        plant=plant,
                        sort_order=j,
                        date_label=str(per.get("date_label") or "")[:240],
                        theme=str(per.get("theme") or "")[:300],
                        content_text=str(per.get("content_text") or ""),
                        content_html=str(per.get("content_html") or ""),
                        images_json=imgs,
                        products_json=prods,
                        videos_json=vids,
                    )
                    n_periods += 1

        self.stdout.write(self.style.SUCCESS(f"Готово: категорий {len(slug_to_cat)}, растений {n_plants}, сроков {n_periods}."))
