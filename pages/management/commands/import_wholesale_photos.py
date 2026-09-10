"""Заливка фотографий позиций оптового каталога /opt/ пачкой из папки.

Заказчик снимает позиции на телефон и присылает по 4-7 кадров на каждую.
Команда ждёт папку, внутри которой подпапки названы слагом позиции, а внутри
подпапки лежат готовые файлы с порядковыми именами:

    photos/
      sosna-gornaia-mugus-pinus-mugo-mughus/
        01.webp
        02.webp
        03.webp
      lipa-melkolistnaya/
        01.webp

    python manage.py import_wholesale_photos /path/photos
    python manage.py import_wholesale_photos /path/photos --dry-run

Порядок снимков берётся из имени файла: 01 идёт первым и становится обложкой
позиции. Ресайза здесь нет - файлы приходят уже подготовленными.

Повторный запуск не плодит дубли: снимок с таким именем файла у позиции уже
есть - пропускаем. Неизвестный слаг не роняет прогон: пишем строку в вывод и
идём к следующей подпапке.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from pages.models import WholesaleItem, WholesaleItemPhoto

# Что считаем снимком. Остальное в папке (Thumbs.db, .DS_Store) молча пропускаем.
IMAGE_SUFFIXES = {".webp", ".jpg", ".jpeg", ".png"}

# Ключ сортировки: «01», «2», «10» должны идти по числу, а не по алфавиту.
NUMBER_RE = re.compile(r"(\d+)")


def sort_key(path: Path) -> tuple:
    """Порядок файлов: сперва по числам в имени, потом по самому имени."""
    parts = NUMBER_RE.split(path.name.lower())
    key = []
    for index, part in enumerate(parts):
        key.append((0, int(part)) if index % 2 else (1, part))
    return tuple(key)


def folder_images(folder: Path) -> list[Path]:
    """Снимки подпапки в порядке имён файлов."""
    files = [
        entry
        for entry in folder.iterdir()
        if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(files, key=sort_key)


class Command(BaseCommand):
    help = "Заливает фотографии позиций /opt/ из папки, где подпапки названы слагом позиции"

    def add_arguments(self, parser):
        parser.add_argument("folder", help="Папка со снимками: подпапка на позицию")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Сухой прогон: только показать, что было бы залито",
        )

    def handle(self, *args, **options):
        root = Path(options["folder"]).expanduser()
        dry = bool(options["dry_run"])
        if not root.is_dir():
            raise CommandError(f"Папка не найдена: {root}")

        folders = sorted((entry for entry in root.iterdir() if entry.is_dir()), key=lambda p: p.name)
        if not folders:
            raise CommandError(f"Внутри {root} нет подпапок с именами-слагами позиций")

        attached = 0
        skipped_files = 0
        skipped_folders = 0

        for folder in folders:
            slug = folder.name.strip()
            items = list(WholesaleItem.objects.select_related("section").filter(slug=slug))
            if not items:
                skipped_folders += 1
                self.stdout.write(
                    self.style.WARNING(f"пропускаю «{slug}»: позиции с таким слагом нет в каталоге")
                )
                continue
            if len(items) > 1:
                skipped_folders += 1
                where = ", ".join(item.section.slug for item in items)
                self.stdout.write(
                    self.style.WARNING(
                        f"пропускаю «{slug}»: слаг встречается в нескольких разделах ({where}), "
                        "залейте снимки через админку"
                    )
                )
                continue

            item = items[0]
            files = folder_images(folder)
            if not files:
                skipped_folders += 1
                self.stdout.write(self.style.WARNING(f"пропускаю «{slug}»: в папке нет снимков"))
                continue

            existing = {photo.file_name for photo in item.photos.all()}

            for index, path in enumerate(files, start=1):
                if path.name in existing:
                    skipped_files += 1
                    self.stdout.write(f"уже залит: {slug}/{path.name}")
                    continue

                if dry:
                    attached += 1
                    self.stdout.write(f"[сухой прогон] {slug}/{path.name} -> {item.get_absolute_url()}")
                    continue

                photo = WholesaleItemPhoto(item=item, sort_order=index * 10, source_name=path.name)
                photo.image.save(path.name, ContentFile(path.read_bytes()), save=False)
                photo.save()
                existing.add(photo.file_name)
                attached += 1
                self.stdout.write(f"залит: {slug}/{path.name} -> {item.get_absolute_url()}")

        prefix = "Сухой прогон закончен" if dry else "Заливка закончена"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}. Снимков: {attached}, уже было: {skipped_files}, "
                f"папок пропущено: {skipped_folders}."
            )
        )
