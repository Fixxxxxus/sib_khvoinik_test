"""Экспорт каталога из БД в Excel (см. также действие в админке)."""

from pathlib import Path

from django.core.management.base import BaseCommand

from pages.catalog_io import export_catalog_workbook


class Command(BaseCommand):
    help = "Сохраняет categories / plants / variants / gallery в один .xlsx (openpyxl)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "output",
            nargs="?",
            default="catalog_export.xlsx",
            help="Путь к выходному файлу (по умолчанию catalog_export.xlsx в текущей папке).",
        )

    def handle(self, *args, **options) -> None:
        out = Path(options["output"]).resolve()
        out.write_bytes(export_catalog_workbook())
        self.stdout.write(self.style.SUCCESS(f"Записано: {out}"))
