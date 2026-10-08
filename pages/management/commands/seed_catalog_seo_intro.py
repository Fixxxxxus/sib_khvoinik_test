"""Заполняет SEO-интро разделов каталога из pages/catalog_seo_intros.py.

Для каждого слага из SEO_INTROS ищет строку в БД: сначала CatalogCategory,
потом CatalogSubcategory. Нашлась - пишет seo_intro, если поле пустое
(с --force перезаписывает и непустое). Не нашлась - это статический подраздел
из pages/catalog_subcategories.py: поля у него нет, текст выводится на сайте
напрямую из SEO_INTROS, команда только сообщает об этом.

Повторный запуск ничего не портит: совпадающий текст пропускается.

Запуск:
    python manage.py seed_catalog_seo_intro [--dry-run] [--force]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.catalog_seo_intros import SEO_INTROS
from pages.models import CatalogCategory, CatalogSubcategory


class Command(BaseCommand):
    help = "Заполняет seo_intro у категорий и подкатегорий каталога (идемпотентно)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Только показать, что изменится.")
        parser.add_argument("--force", action="store_true", help="Перезаписать непустой seo_intro.")

    def handle(self, *args, **opts):
        dry, force = opts["dry_run"], opts["force"]
        stats = {"written": 0, "same": 0, "kept": 0, "static": 0}
        with transaction.atomic():
            for slug, html in SEO_INTROS.items():
                obj = (
                    CatalogCategory.objects.filter(slug=slug).first()
                    or CatalogSubcategory.objects.filter(slug=slug).first()
                )
                if obj is None:
                    stats["static"] += 1
                    self.stdout.write(f"  static  {slug}: строки в БД нет, текст идёт из SEO_INTROS")
                    continue
                kind = type(obj).__name__
                current = (obj.seo_intro or "").strip()
                if current == html.strip():
                    stats["same"] += 1
                    self.stdout.write(f"  same    {slug} ({kind}): уже совпадает")
                    continue
                if current and not force:
                    stats["kept"] += 1
                    self.stdout.write(f"  kept    {slug} ({kind}): поле заполнено вручную, нужен --force")
                    continue
                stats["written"] += 1
                verb = "would write" if dry else "write"
                self.stdout.write(f"  {verb:<7} {slug} ({kind}): {len(html)} симв.")
                if not dry:
                    obj.seo_intro = html
                    obj.save(update_fields=["seo_intro"])
            if dry:
                transaction.set_rollback(True)
        prefix = "[dry-run] " if dry else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}записано {stats['written']}, совпадает {stats['same']}, "
                f"оставлено как есть {stats['kept']}, статических {stats['static']}"
            )
        )
