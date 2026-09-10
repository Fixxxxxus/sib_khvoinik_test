"""Тесты галереи позиций оптового каталога /opt/ и заливки снимков из папки.

MEDIA_ROOT на время тестов уводим во временную папку: реальный media/ не
засоряем, файлы уезжают вместе с временной директорией.
"""

from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings

from pages.models import WholesaleItem, WholesaleItemPhoto, WholesaleSection

# Минимальный валидный PNG 1x1: содержимое кадра тестам неважно, важен файл.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def make_item(slug: str = "lipa-test") -> tuple[WholesaleSection, WholesaleItem]:
    section = WholesaleSection.objects.create(
        title="Тестовые деревья", slug="test-derevya", sort_order=1
    )
    item = WholesaleItem.objects.create(
        section=section,
        title="Липа тестовая",
        slug=slug,
        size="высота 3 м",
        price=Decimal("6500.00"),
    )
    return section, item


def add_photo(item: WholesaleItem, name: str, sort_order: int = 100) -> WholesaleItemPhoto:
    photo = WholesaleItemPhoto(item=item, sort_order=sort_order)
    photo.image.save(name, ContentFile(PIXEL), save=False)
    photo.save()
    return photo


class MediaSandboxMixin:
    """Свой MEDIA_ROOT на каждый тест: файлы одного теста не мешают другому."""

    def use_sandbox_media(self):
        media = tempfile.mkdtemp(prefix="opt-photos-media-")
        self.addCleanup(shutil.rmtree, media, True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)


class GalleryRenderTest(MediaSandboxMixin, TestCase):
    """Карточка позиции: крупный кадр, лента миниатюр и обложка-запаска."""

    def setUp(self):
        self.use_sandbox_media()
        self.client = Client()
        self.section, self.item = make_item()

    def card(self) -> str:
        url = f"/opt/{self.section.slug}/{self.item.slug}/"
        return self.client.get(url).content.decode()

    def test_gallery_with_several_photos_renders_slides_and_thumbs(self):
        for index, name in enumerate(("01.png", "02.png", "03.png"), start=1):
            add_photo(self.item, name, sort_order=index * 10)

        html = self.card()
        self.assertEqual(html.count("data-opt-gallery-slide"), 3)
        self.assertEqual(html.count("data-opt-gallery-thumb "), 3)
        self.assertIn("data-opt-gallery-thumbs", html)
        self.assertIn("Листайте стрелками или свайпом", html)

    def test_single_photo_has_no_thumbs_strip(self):
        add_photo(self.item, "01.png", sort_order=10)

        html = self.card()
        self.assertEqual(html.count("data-opt-gallery-slide"), 1)
        self.assertNotIn("data-opt-gallery-thumbs", html)
        self.assertNotIn("data-opt-gallery-thumb ", html)

    def test_empty_gallery_falls_back_to_the_old_image_field(self):
        self.item.image.save("cover.png", ContentFile(PIXEL), save=True)

        html = self.card()
        self.assertNotIn("data-opt-gallery-slide", html)
        self.assertNotIn("data-opt-gallery-thumbs", html)
        self.assertIn(self.item.image.url, html)
        self.assertNotIn("фото готовим", html)

    def test_cover_is_the_first_gallery_photo_not_the_image_field(self):
        self.item.image.save("cover.png", ContentFile(PIXEL), save=True)
        first = add_photo(self.item, "01.png", sort_order=10)
        add_photo(self.item, "02.png", sort_order=20)

        item = WholesaleItem.objects.get(pk=self.item.pk)
        self.assertEqual(item.cover_url, first.image.url)
        self.assertEqual(item.photos_count, 2)

        # В списке раздела карточка показывает ту же обложку и пометку о кадрах.
        html = self.client.get(f"/opt/{self.section.slug}/").content.decode()
        self.assertIn(first.image.url, html)
        self.assertIn("2 фото", html)

    def test_no_photos_at_all_keeps_the_placeholder(self):
        self.assertEqual(self.item.cover_url, "")
        self.assertEqual(self.item.photos_count, 0)
        self.assertIn("фото готовим", self.card())


class ImportPhotosCommandTest(MediaSandboxMixin, TestCase):
    """Заливка пачкой: папка на позицию, файлы 01, 02, 03."""

    def setUp(self):
        self.use_sandbox_media()
        self.section, self.item = make_item(slug="sosna-gornaia-mugus")
        self.root = Path(tempfile.mkdtemp(prefix="opt-photos-src-"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def make_folder(self, slug: str, names: tuple[str, ...]) -> Path:
        folder = self.root / slug
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / name).write_bytes(PIXEL)
        return folder

    def run_command(self, *flags) -> str:
        out = StringIO()
        call_command("import_wholesale_photos", str(self.root), *flags, stdout=out)
        return out.getvalue()

    def test_photos_are_attached_by_slug_in_file_name_order(self):
        self.make_folder("sosna-gornaia-mugus", ("02.webp", "01.webp", "10.webp"))

        self.run_command()

        photos = list(self.item.photos.all())
        self.assertEqual([photo.file_name for photo in photos], ["01.webp", "02.webp", "10.webp"])
        self.assertEqual([photo.sort_order for photo in photos], [10, 20, 30])

    def test_second_run_does_not_duplicate_photos(self):
        self.make_folder("sosna-gornaia-mugus", ("01.webp", "02.webp"))
        self.run_command()

        output = self.run_command()

        self.assertEqual(self.item.photos.count(), 2)
        self.assertIn("уже залит", output)

    def test_unknown_slug_is_reported_and_skipped(self):
        self.make_folder("takoy-pozicii-net", ("01.webp",))
        self.make_folder("sosna-gornaia-mugus", ("01.webp",))

        output = self.run_command()

        self.assertIn("takoy-pozicii-net", output)
        self.assertIn("позиции с таким слагом нет", output)
        # Соседняя папка при этом залилась: одна битая не роняет прогон.
        self.assertEqual(self.item.photos.count(), 1)
        self.assertEqual(WholesaleItemPhoto.objects.count(), 1)

    def test_dry_run_changes_nothing(self):
        self.make_folder("sosna-gornaia-mugus", ("01.webp", "02.webp"))

        output = self.run_command("--dry-run")

        self.assertIn("сухой прогон", output)
        self.assertEqual(WholesaleItemPhoto.objects.count(), 0)

    def test_missing_folder_is_a_clear_error(self):
        with self.assertRaises(CommandError):
            call_command("import_wholesale_photos", str(self.root / "нет-такой"), stdout=StringIO())
