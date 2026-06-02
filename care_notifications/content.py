"""Селектор контента дайджеста: подбор растений и работ на ISO-неделю.

Контракт:
    entries = select_entries_for_week(
        group_slugs=["roses", "lawn"],
        week_key="2026-W21",
    )
    # entries: list[CategoryEntries], каждая категория с list[PlantEntry]

Алгоритм:
1. Для каждой группы из CARE_SUBSCRIPTION_GROUPS берём category_slugs (slug
   календаря). Например, "roses" -> ["rozy"].
2. ORM: CareCalendarPeriod по этим категориям, prefetch_related plant.
3. Парсим period.date_label через date_parser. Непарсимые - в warning лог.
4. Фильтр 1 (текущая неделя): пересечение period с week_range.
5. Если по категории пусто - фильтр 2 (fallback): ближайшие предстоящие
   периоды в горизонте lookahead_weeks недель вперёд.
6. На каждом периоде формируем PlantEntry: имя, тизер, URL, флаг is_upcoming.
7. Hero-картинка - первое непустое фото первого выбранного периода категории.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from django.db.models import Q

from .date_parser import iso_week_range, overlaps, parse_date_label


logger = logging.getLogger(__name__)

# Эмодзи для групп подписки. Совпадают с эмодзи на сайте /calendar/<slug>/.
_GROUP_EMOJI = {
    "rozy": "🌹",
    "gazon": "🌾",
    "derevya": "🌳",
    "kustarniki": "🌿",
    "mnogoletniki": "💐",
}

# Максимум символов в одной строке-тизере (1 предложение или 1 фраза).
_SUMMARY_MAX_CHARS = 140


@dataclass
class PlantEntry:
    name: str
    summary: str
    url: str
    date_label: str
    is_upcoming: bool
    plant_slug: str
    category_slug: str


@dataclass
class CategoryEntries:
    category_slug: str
    category_label: str
    emoji: str
    plants: list[PlantEntry] = field(default_factory=list)
    hero_image_url: str | None = None
    hero_image_path: str | None = None


def _make_summary(theme: str, content_text: str, content_html: str) -> str:
    """Однострочный тизер для письма.

    Приоритет: theme (короткая 'тема работ', до 300 символов) -> первое
    предложение content_text -> первое предложение content_html без HTML-тегов.
    Обрезка до _SUMMARY_MAX_CHARS по границе слова.
    """
    src = (theme or "").strip()
    if not src:
        src = (content_text or "").strip()
    if not src and content_html:
        src = re.sub(r"<[^>]+>", " ", content_html)
        src = re.sub(r"\s+", " ", src).strip()
    if not src:
        return ""
    # Берём первый смысловой кусок (обычно это «тема» периода). Режем по самой
    # ранней из границ: перенос строки, конец предложения или стык
    # «строчнаяЗаглавная». Последнее ловит записи, где при стрипе HTML потерялся
    # разделитель между заголовком и телом ("Первая стрижкаГазон начал...") -
    # без этого в тизер уезжает кусок тела с лишним текстом.
    candidates: list[int] = []
    for sep in ("\n", ". ", "! ", "? "):
        idx = src.find(sep)
        if idx > 0:
            candidates.append(idx)
    glue = re.search(r"[а-яё][А-ЯЁ]", src)
    if glue:
        candidates.append(glue.start() + 1)
    if candidates:
        src = src[: min(candidates)].rstrip(".!?")
    src = src.strip(" .;:-")
    if len(src) <= _SUMMARY_MAX_CHARS:
        return src
    # Обрезаем по границе слова.
    cut = src[:_SUMMARY_MAX_CHARS].rsplit(" ", 1)[0]
    return f"{cut}…"


def _period_image_url(period) -> tuple[str | None, str | None]:
    """Первое непустое фото периода. Возвращает (url, local_path)."""
    for i in range(1, 7):
        field_name = f"period_image_{i}"
        img = getattr(period, field_name, None)
        if img and getattr(img, "name", ""):
            try:
                return img.url, img.path
            except Exception:  # noqa: BLE001
                # Файл удалён с диска - игнорируем
                continue
    return None, None


def _plant_url(category_slug: str, plant_slug: str, site_url: str) -> str:
    return f"{site_url}/sluzhba-zaboty/calendar/{category_slug}/#{plant_slug}"


def select_entries_for_week(
    group_slugs: Iterable[str],
    week_key: str,
    *,
    site_url: str = "https://gazony.ru",
    lookahead_weeks: int = 4,
) -> list[CategoryEntries]:
    """Главная точка входа. Возвращает блоки контента для подписанных групп.

    Пустые группы (нет периодов ни на этой неделе, ни в lookahead-горизонте)
    в результат не попадают.
    """
    from pages.data import CARE_SUBSCRIPTION_GROUPS
    from pages.models import CareCalendarCategory, CareCalendarPeriod

    week_range = iso_week_range(week_key)
    if not week_range:
        logger.warning("select_entries_for_week: bad week_key=%r", week_key)
        return []
    week_start, week_end = week_range
    year = week_start.year
    horizon_end = week_end + dt.timedelta(weeks=lookahead_weeks)

    # group_slug -> [category_slug, ...]
    group_to_cats: dict[str, list[str]] = {
        g["slug"]: list(g.get("category_slugs") or [])
        for g in CARE_SUBSCRIPTION_GROUPS
    }

    # Соберём все нужные category_slugs.
    needed_cat_slugs: set[str] = set()
    for slug in group_slugs:
        if slug == "seasonal":
            continue  # hero-группа, не имеет блока с растениями
        for cat in group_to_cats.get(slug, []):
            needed_cat_slugs.add(cat)

    if not needed_cat_slugs:
        return []

    categories = {
        c.slug: c
        for c in CareCalendarCategory.objects.filter(slug__in=needed_cat_slugs)
    }

    # Одним запросом тянем все периоды этих категорий вместе с растениями.
    periods_qs = (
        CareCalendarPeriod.objects
        .select_related("plant", "plant__primary_category")
        .filter(plant__primary_category__slug__in=needed_cat_slugs, plant__is_published=True)
        .order_by("plant__sort_order", "sort_order")
    )

    # category_slug -> [(period, start, end), ...]
    by_cat_now: dict[str, list[tuple]] = {c: [] for c in needed_cat_slugs}
    by_cat_upcoming: dict[str, list[tuple]] = {c: [] for c in needed_cat_slugs}
    unparsed = 0
    for period in periods_qs:
        cat_slug = period.plant.primary_category.slug
        parsed = parse_date_label(period.date_label, year)
        if parsed is None:
            unparsed += 1
            continue
        start, end = parsed
        if overlaps((start, end), week_range):
            by_cat_now[cat_slug].append((period, start, end))
        elif start > week_end and start <= horizon_end:
            by_cat_upcoming[cat_slug].append((period, start, end))

    if unparsed:
        logger.info("select_entries_for_week: skipped %s периодов с непарсимым date_label", unparsed)

    # Сборка результата.
    result: list[CategoryEntries] = []
    for cat_slug in needed_cat_slugs:
        cat = categories.get(cat_slug)
        if not cat:
            continue
        nows = by_cat_now[cat_slug]
        is_upcoming = False
        if nows:
            chosen = nows
        else:
            ups = sorted(by_cat_upcoming[cat_slug], key=lambda t: t[1])
            if not ups:
                continue
            # Берём только ближайший по дате (а не все будущие на 4 недели).
            min_start = ups[0][1]
            chosen = [t for t in ups if t[1] == min_start]
            is_upcoming = True

        entries: list[PlantEntry] = []
        for period, _, _ in chosen:
            plant = period.plant
            entries.append(PlantEntry(
                name=plant.name,
                summary=_make_summary(period.theme, period.content_text, period.content_html),
                url=_plant_url(cat_slug, plant.slug, site_url),
                date_label=period.date_label,
                is_upcoming=is_upcoming,
                plant_slug=plant.slug,
                category_slug=cat_slug,
            ))

        # Hero-картинка категории: первое фото первого периода с фотом.
        hero_url, hero_path = None, None
        for period, _, _ in chosen:
            hero_url, hero_path = _period_image_url(period)
            if hero_url:
                break

        result.append(CategoryEntries(
            category_slug=cat_slug,
            category_label=cat.label,
            emoji=_GROUP_EMOJI.get(cat_slug, ""),
            plants=entries,
            hero_image_url=hero_url,
            hero_image_path=hero_path,
        ))

    return result
