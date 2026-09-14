"""Импорт прайса 1С (xls) в оптовый каталог /opt/: сорта и размеры как варианты.

Заказчик выгружает из 1С «Прайс-лист» по разделу: Кустарники, Деревья, Хвоя,
Гортензия (xls, BIFF8). Лист устроен одинаково: колонка B - заголовки
(раздел, потом род: «Барбарис», «Дерен»), C - полное наименование с сортом
и размером, D - описание, E - свободный остаток, F - розничная цена. В колонке
B у каждой строки прибита картинка (pages/xls_pictures.py).

    python manage.py import_wholesale_price_xls КУСТАРНИКИ.xls Деревья.xls
    python manage.py import_wholesale_price_xls Гортензия.xls --dry-run

Как строки ложатся в каталог (решение с маркетологом 14.09.2026):

- Строки одного вида собираются в одну карточку, а сорта и размеры идут
  вариантами (WholesaleItemVariant) со своей ценой, остатком и фото. Витрина
  не раздувается: «Гортензия метельчатая» остаётся одной плиткой с двадцатью
  сортами внутри.
- Карточка «в ассортименте» (например «Барбарис в ассортименте») забирает все
  строки своего рода: род сверяется по началу слага.
- Карточка без пометки «в ассортименте» сверяется по виду и сорту: «Клен
  Гиннала» забирает обе свои строки (h 60-90 и h 2,0-2,5), у карточки
  появляются варианты по размеру.
- Вида в каталоге нет - карточка создаётся. Одна строка - обычная позиция
  с фото; несколько строк одного вида и сорта - позиция с вариантами.
- Цена в прайсе розничная, опт от неё считает pages/wholesale_pricing.py.
  Цена карточки с вариантами - минимальная из вариантов, наличие - сумма.

Повторный прогон обновляет, а не плодит: карточка ищется по слагу, вариант -
по названию внутри карточки, фото варианта не перезаливается, если уже есть.
"""

from __future__ import annotations

import io
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pages.management.commands.import_wholesale_items import (
    SECTIONS,
    _clean,
    parse_price,
    split_title_and_size,
)
from pages.models import WholesaleItem, WholesaleItemPhoto, WholesaleItemVariant, WholesaleSection
from pages.utils_slug import ascii_slugify
from pages.xls_pictures import pictures_by_row

# Колонки листа (с нуля, как в xlrd).
COL_GROUP = 1
COL_NAME = 2
COL_DESCRIPTION = 3
COL_STOCK = 4
COL_PRICE = 5

ASSORTMENT_RE = re.compile(r"\s*в\s+ассортименте\s*", re.IGNORECASE)
QUOTED_RE = re.compile(r"[\"«»“”]([^\"«»“”]+)[\"«»“”]")
LATIN_RE = re.compile(r"[A-Za-zÀ-ɏ]")

# 1С режет длинное наименование: «... D400) О», «... D400) ОСЕНЬ ». Обрубок
# слова «осень» в хвосте - это сезон отгрузки без года.
TRUNCATED_SEASON_RE = re.compile(r"\s+(о|ос|осе|осен|осень)\s*$", re.IGNORECASE)
# Латинская C в контейнере («C2/3») против кириллической «С2/3» в каталоге:
# приводим к кириллице, иначе одинаковые размеры не сходятся.
LATIN_C_RE = re.compile(r"(?<![A-Za-zА-Яа-я])C(?=\s?\d)")
DOT_DECIMAL_RE = re.compile(r"(\d)\.(\d)")
NO_SORT_TITLE = "Видовой"

PHOTO_MAX_SIDE = 1200
PHOTO_QUALITY = 82


@dataclass
class Row:
    """Одна товарная строка прайса после разбора."""

    line: int
    title: str  # наименование без размера и сезона
    species: str  # русский вид без сорта: «Дерен белый»
    sort: str  # сорт из кавычек: «Элегантиссима»
    latin: str  # латынь как в прайсе, без сорта
    size: str
    notes: list[str]
    description: str
    stock: int
    price: Decimal
    picture: bytes | None = None

    @property
    def key(self) -> str:
        return ascii_slugify(f"{self.species} {self.sort}".strip())

    @property
    def species_key(self) -> str:
        return ascii_slugify(self.species)


@dataclass
class Target:
    """Карточка, в которую едут строки: существующая или новая."""

    key: str
    item: WholesaleItem | None
    rows: list[Row] = field(default_factory=list)

    @property
    def is_new(self) -> bool:
        return self.item is None

    @property
    def as_variants(self) -> bool:
        if len(self.rows) > 1:
            return True
        return self.item is not None and self.item.variants.filter(is_active=True).exists()

    def common_size(self) -> str:
        sizes = {row.size for row in self.rows}
        return self.rows[0].size if len(sizes) == 1 else ""


def parse_stock(raw) -> int:
    """Остаток из 1С: «1 984,000» - это 1984, число - как есть, пусто - ноль."""
    if raw is None:
        return 0
    if isinstance(raw, (int, float, Decimal)):
        return max(int(Decimal(str(raw))), 0)
    text = _clean(raw).replace(" ", "")
    if not text:
        return 0
    whole = text.split(",")[0].split(".")[0]
    digits = re.sub(r"\D", "", whole)
    return int(digits) if digits else 0


def normalize_size(size: str) -> str:
    """Размер в единой записи каталога: кириллическая «С», запятая в дробях."""
    text = LATIN_C_RE.sub("С", _clean(size))
    return DOT_DECIMAL_RE.sub(r"\1,\2", text)


def strip_truncated_season(name: str) -> tuple[str, list[str]]:
    """Обрубок «О»/«ОСЕНЬ» без года в хвосте наименования -> заметка об отгрузке."""
    match = TRUNCATED_SEASON_RE.search(name)
    if not match:
        return name, []
    return name[: match.start()], ["Отгрузка: осень."]


def split_species(title: str) -> tuple[str, str, str]:
    """(вид по-русски, сорт, латынь) из наименования без размера.

    «Дерен белый "Элегантиссима" Cornus alba "Elegantissima"» ->
    («Дерен белый», «Элегантиссима», «Cornus alba»).
    Русская часть - всё до первой латинской буквы; сорт - первые кавычки в ней.
    """
    text = _clean(title)
    match = LATIN_RE.search(text)
    russian = text[: match.start()] if match else text
    latin = text[match.start() :] if match else ""

    sort = ""
    quoted = QUOTED_RE.search(russian)
    if quoted:
        sort = _clean(quoted.group(1))
        russian = QUOTED_RE.sub(" ", russian, count=1)
    latin = _clean(QUOTED_RE.sub(" ", latin)).strip(" ,/;-")
    species = _clean(ASSORTMENT_RE.sub(" ", russian)).strip(" ,/;-")
    return species, sort, latin


def item_key(item: WholesaleItem) -> tuple[str, bool]:
    """Ключ существующей карточки: (слаг русской части с сортом, «в ассортименте»?)."""
    assortment = bool(ASSORTMENT_RE.search(item.title))
    species, sort, _latin = split_species(item.title)
    return ascii_slugify(f"{species} {sort}".strip()), assortment


def _slug_prefix(prefix: str, slug: str) -> bool:
    return slug == prefix or slug.startswith(prefix + "-")


def match_item(row: Row, items: list[WholesaleItem]) -> WholesaleItem | None:
    """Карточка для строки: точное совпадение вида и сорта, иначе род «в ассортименте»."""
    exact = [item for item in items if item_key(item)[0] == row.key]
    if len(exact) == 1:
        return exact[0]
    assorted = [
        item
        for item in items
        if item_key(item)[1] and _slug_prefix(item_key(item)[0], row.species_key)
    ]
    if len(assorted) == 1:
        return assorted[0]
    return None


def variant_title(row: Row, target: Target) -> str:
    """Название варианта: сорт (если в карточке их несколько), размер (если разный), сезон.

    У карточки «Черемуха "Шуберт"» сорт уже в названии, вариантам остаётся
    размер. У карточки «в ассортименте» сорт - главное, он идёт первым, а
    строка без сорта зовётся видовой.
    """
    sorts = {r.sort for r in target.rows}
    assortment = target.item is not None and item_key(target.item)[1]
    show_sort = assortment or len(sorts) > 1
    parts: list[str] = []
    if show_sort:
        parts.append(row.sort or NO_SORT_TITLE)
    if row.size and (not target.common_size() or not parts):
        parts.append(row.size)
    if not parts:
        parts.append(row.title)
    season = [note for note in row.notes if note.startswith("Отгрузка:")]
    if season:
        parts.append(season[0].removeprefix("Отгрузка:").strip(" ."))
    return ", ".join(parts)[:200]


def new_item_title(target: Target) -> str:
    """Название новой карточки: одна строка - как в прайсе, несколько - вид и латынь."""
    first = target.rows[0]
    if len(target.rows) == 1:
        return first.title[:200]
    sort = first.sort if all(row.sort == first.sort for row in target.rows) else ""
    title = first.species
    if sort:
        title += f' "{sort}"'
    if first.latin:
        title += f" {first.latin}"
    return title[:200]


def load_rows(path: Path) -> tuple[str, list[Row], list[str]]:
    """Раздел, товарные строки листа и пометки о пропущенных строках (через xlrd)."""
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover - зависимость в requirements
        raise CommandError("Нужен xlrd: pip install xlrd") from exc
    try:
        book = xlrd.open_workbook(str(path))
    except Exception as exc:
        raise CommandError(f"Файл {path} не открывается: {exc}") from exc
    sheet = book.sheet_by_index(0)
    pictures = pictures_by_row(path)

    section_key = ""
    rows: list[Row] = []
    errors: list[str] = []
    for index in range(sheet.nrows):
        values = [sheet.cell_value(index, col) if col < sheet.ncols else "" for col in range(6)]
        group = _clean(values[COL_GROUP])
        name = _clean(values[COL_NAME])
        if group and not name:
            key = group.lower().replace("ё", "е")
            if key in SECTIONS and not section_key:
                section_key = key
            continue
        if not name:
            continue
        if not _clean(values[COL_PRICE]) and parse_stock(values[COL_STOCK]) == 0:
            continue  # шапка таблицы («НаименованиеПолное») или пустая строка
        try:
            name, tail_notes = strip_truncated_season(name)
            title, size, notes = split_title_and_size(name)
            notes = notes + tail_notes
            size = normalize_size(size)
            species, sort, latin = split_species(title)
            price = parse_price(values[COL_PRICE])
        except ValueError as exc:
            errors.append(f"строка {index + 1}: пропущена, {exc}. Значение: «{name}»")
            continue
        rows.append(
            Row(
                line=index,
                title=title,
                species=species,
                sort=sort,
                latin=latin,
                size=size,
                notes=notes,
                description=_clean(values[COL_DESCRIPTION]),
                stock=parse_stock(values[COL_STOCK]),
                price=price,
                picture=pictures.get(index),
            )
        )
    if not section_key:
        raise CommandError(
            f"В {path.name} не найден заголовок раздела ({', '.join(SECTIONS)}): "
            "он должен стоять в колонке B над строками."
        )
    return section_key, rows, errors


def build_targets(rows: list[Row], items: list[WholesaleItem]) -> list[Target]:
    """Строки по карточкам: существующим по совпадению, новым по виду и сорту."""
    targets: "OrderedDict[str, Target]" = OrderedDict()
    for row in rows:
        item = match_item(row, items)
        key = f"item:{item.pk}" if item is not None else f"new:{row.key}"
        target = targets.get(key)
        if target is None:
            target = Target(key=key, item=item)
            targets[key] = target
        target.rows.append(row)
    return list(targets.values())


def picture_file(blob: bytes, name: str) -> ContentFile | None:
    """PNG/JPEG из прайса в webp не больше PHOTO_MAX_SIDE по стороне."""
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover
        return None
    try:
        image = Image.open(io.BytesIO(blob))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception:  # noqa: BLE001 - битая картинка не должна ронять импорт
        return None
    if max(image.size) < 64:
        return None  # иконка-заглушка из шапки, не фото
    image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=PHOTO_QUALITY, method=6)
    return ContentFile(buffer.getvalue(), name=f"{name}.webp")


class Command(BaseCommand):
    help = "Импорт прайса 1С (xls) в оптовый каталог /opt/: сорта и размеры как варианты."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="Файлы xls из 1С (по одному на раздел).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Сухой прогон: показать, как строки лягут в каталог, в БД не писать.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        stats = {"items_new": 0, "items_updated": 0, "variants": 0, "photos": 0}
        for raw_path in options["paths"]:
            path = Path(raw_path).expanduser()
            if not path.is_file():
                raise CommandError(f"Файл не найден: {path}")
            section_key, rows, errors = load_rows(path)
            for message in errors:
                self.stderr.write(f"{path.name}: {message}")
            block = SECTIONS[section_key]
            self.stdout.write(self.style.MIGRATE_HEADING(f"{path.name}: раздел «{block['title']}», строк: {len(rows)}"))

            section = WholesaleSection.objects.filter(slug=block["slug"]).first()
            items = list(section.items.all()) if section else []
            targets = build_targets(rows, items)

            if dry:
                self._report(targets)
                continue
            with transaction.atomic():
                if section is None:
                    section = WholesaleSection.objects.create(
                        slug=block["slug"], title=block["title"], sort_order=block["sort_order"], is_active=True
                    )
                for target in targets:
                    self._apply(section, target, path.stem, stats)

        if dry:
            self.stdout.write(self.style.SUCCESS("Сухой прогон закончен, в БД ничего не записано."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Импорт закончен. Карточек создано: {stats['items_new']}, обновлено: {stats['items_updated']}, "
                f"вариантов: {stats['variants']}, фото: {stats['photos']}."
            )
        )

    def _report(self, targets: list[Target]) -> None:
        for target in targets:
            if target.item is not None:
                head = f"[есть] {target.item.slug} «{target.item.title}»"
            else:
                head = f"[новая] «{new_item_title(target)}»"
            if target.as_variants:
                self.stdout.write(f"{head}: {len(target.rows)} вариант(ов), размер карточки: {target.common_size() or '-'}")
                for row in target.rows:
                    self.stdout.write(
                        f"    - {variant_title(row, target)} | {row.stock} шт | {row.price} ₽"
                        f" | фото: {'да' if row.picture else 'нет'}"
                    )
            else:
                row = target.rows[0]
                self.stdout.write(
                    f"{head}: размер {row.size or '-'} | {row.stock} шт | {row.price} ₽"
                    f" | фото: {'да' if row.picture else 'нет'}"
                )

    def _apply(self, section: WholesaleSection, target: Target, source: str, stats: dict) -> None:
        rows = target.rows
        first = rows[0]
        item = target.item
        as_variants = target.as_variants

        if item is None:
            title = new_item_title(target)
            slug = ascii_slugify(title.split('"')[0] if len(rows) > 1 else title) or ascii_slugify(title)
            base_slug = slug
            suffix = 2
            while WholesaleItem.objects.filter(section=section, slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            item = WholesaleItem(section=section, slug=slug, title=title, unit="шт", sort_order=first.line * 10)
            stats["items_new"] += 1
            self.stdout.write(f"создана: /opt/{section.slug}/{slug}/ «{title}»")
        else:
            stats["items_updated"] += 1
            self.stdout.write(f"обновлена: {item.get_absolute_url()}")

        if as_variants:
            item.size = target.common_size()
            item.price = min(row.price for row in rows)
            item.availability = f"в наличии {sum(row.stock for row in rows)} {item.unit or 'шт'}"
        else:
            item.size = first.size
            item.price = first.price
            item.availability = f"в наличии {first.stock} {item.unit or 'шт'}" if first.stock else "уточняйте"
        if not item.short_description:
            notes = " ".join(first.notes)
            item.short_description = (first.description if not as_variants else "") or notes
        item.is_active = True
        item.is_demo = False
        item.save()

        if as_variants:
            for order, row in enumerate(rows, start=1):
                title = variant_title(row, target)
                variant, _created = WholesaleItemVariant.objects.update_or_create(
                    item=item,
                    title=title,
                    defaults={
                        "stock": row.stock,
                        "price": row.price,
                        "sort_order": order * 10,
                        "is_active": True,
                    },
                )
                stats["variants"] += 1
                if row.picture and not variant.image:
                    # Имя короткое: путь с длинным слагом не влезает в поле файла.
                    content = picture_file(row.picture, f"{item.slug[:40]}-v{order:02d}")
                    if content is not None:
                        variant.image.save(content.name, content, save=True)
                        stats["photos"] += 1
                self.stdout.write(f"    вариант: {title} | {row.stock} шт | {row.price} ₽")

        # Фото карточки из прайса: только если своих снимков ещё нет, сортовые
        # фото сюда не сливаем - у них есть варианты.
        if first.picture and not item.photos.exists() and not item.image:
            source_name = f"{source}:{first.line + 1}"
            content = picture_file(first.picture, "01")  # галерея кладёт файл в папку слага
            if content is not None:
                photo = WholesaleItemPhoto(item=item, sort_order=10, source_name=source_name)
                photo.image.save(content.name, content, save=False)
                photo.save()
                stats["photos"] += 1
