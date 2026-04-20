"""Импорт каталога из Excel в БД."""

from pathlib import Path

from django.core.management.base import BaseCommand

from pages.catalog_io import import_catalog_workbook


class Command(BaseCommand):
    help = "Импортирует книгу в формате export_catalog_workbook (листы categories, plants, variants)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("input", type=str, help="Путь к .xlsx")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только посчитать строки, без записи в БД.",
        )

    def handle(self, *args, **options) -> None:
        path = Path(options["input"]).resolve()
        stats = import_catalog_workbook(path.read_bytes(), dry_run=options["dry_run"])
        self.stdout.write(str(stats))
