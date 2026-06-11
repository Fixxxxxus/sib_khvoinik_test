"""Сборка дайджеста Службы заботы для одной подписки.

Контракт для каналов (используется 1B Telegram, 1D Unisender, 1E оркестратор):

    payload = build_payload(subscription, week_key=None)
    html = render_email(payload)
    tg_text = render_telegram(payload)
    max_text = render_max(payload)

Где payload - dataclass DigestPayload (см. ниже). У всех каналов одинаковый
контент (hero + блоки по группам + подвал), различается только разметка.

Источник контента:
- HERO: синтетический сезонный текст по неделе ISO + опциональная картинка
  static/media/digest/<year>-W<num>.jpg. В апреле-октябре hero про работы недели,
  в ноябре-марте про планирование сезона.
- BLOCKS: по выбранным группам подписки. На MVP берём первые 1-2 растения из
  категории БД и описываем коротко. Точный матчинг date_label с текущей неделей
  оставлен на следующую итерацию (1F).
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from pages.data import CARE_SUBSCRIPTION_GROUPS

from .content import CategoryEntries, PlantEntry, select_entries_for_week
from .models import CareSubscription


SITE_URL = os.environ.get("CARE_SITE_URL", "https://gazony.ru")
TELEGRAM_BOT_URL = os.environ.get("CARE_TELEGRAM_BOT_URL", "https://t.me/sg_customer_care_bot")
MAX_BOT_URL = os.environ.get("CARE_MAX_BOT_URL", "")  # пока MAX-бот не подключён


@dataclass
class DigestBlock:
    """Блок одной категории в дайджесте: список растений с тизерами.

    Каждое растение - одна строка `PlantEntry`. Полный текст работ остаётся
    на сайте, в дайджесте только тизер + ссылка `подробнее`.

    `category_url` - ссылка на весь раздел календаря, нужна для «ещё N
    растений на сайте» при ограничении количества строк в коротких каналах.
    """
    emoji: str
    title: str
    plants: list[PlantEntry]
    category_slug: str = ""
    category_url: str = ""
    hero_image_url: str | None = None
    hero_image_path: str | None = None


# Максимум строк-растений на одну категорию в коротких каналах (TG/MAX).
# Telegram sendMessage лимит = 4096 символов; при 6 группах подписки и ~150
# символов на строку безопасный потолок ~5 растений на группу.
_PLANTS_PER_CATEGORY_TG = 5


@dataclass
class DigestFooter:
    site_url: str
    telegram_url: str
    max_url: str
    manage_url: str
    unsubscribe_url: str


@dataclass
class DigestPayload:
    week_key: str
    subject: str
    hero_image_url: str | None
    hero_image_path: str | None
    hero_title: str
    hero_text: str
    blocks: list[DigestBlock]
    footer: DigestFooter
    season_label: str
    meta: dict[str, Any] = field(default_factory=dict)


_SLUG_TO_GROUP = {g["slug"]: g for g in CARE_SUBSCRIPTION_GROUPS}


def get_current_week_key(when: dt.datetime | None = None) -> str:
    """ISO week key вида '2026-W21'. Используется как ключ идемпотентности доставок.

    Неделя считается по локальному времени проекта (settings.TIME_ZONE,
    Asia/Krasnoyarsk = тот же UTC+7, что и Новосибирск): понедельник 00:00 -
    воскресенье 23:59. ISO-неделя по определению начинается с понедельника,
    поэтому достаточно перевести момент в локальную зону до isocalendar() -
    иначе граница недели «съезжает» на смещение UTC (ночь вс→пн по Новосибирску).
    """
    when = when or timezone.now()
    if timezone.is_aware(when):
        when = timezone.localtime(when)
    iso = when.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def format_week_display(week_key: str) -> str:
    """Человекочитаемое представление недели для шаблонов: '2026-неделя 21'.

    Принимает week_key вида '2026-W21' (формат хранения в БД). Если строка
    не подходит под шаблон, возвращает её как есть (защита от мусора в legacy
    записях DigestDelivery).
    """
    if not week_key or "-W" not in week_key:
        return week_key
    year, _, num = week_key.partition("-W")
    if not (year.isdigit() and num.isdigit()):
        return week_key
    return f"{year}-неделя {int(num)}"


def _season_label(now: dt.datetime) -> str:
    """Активный сезон апрель-октябрь, межсезонье ноябрь-март."""
    m = now.month
    return "active" if 4 <= m <= 10 else "off"


_ACTIVE_HERO_TITLE = "Что важно успеть на этой неделе"
_ACTIVE_HERO_TEXT = (
    "На этой неделе в Новосибирске сад активно растёт, но погода ещё нестабильна. "
    "Возвратные заморозки в конце мая случаются почти каждый год, а к выходным "
    "обычно прогревается до +18. Главный совет на ближайшие дни: держите укрытия "
    "и нетканку в режиме готовности - днём проветривайте, на ночь возвращайте."
    "\n\n"
    "Ниже короткие рекомендации по группам, на которые вы подписаны."
)

_OFF_HERO_TITLE = "Что делать в межсезонье"
_OFF_HERO_TEXT = (
    "Открытых работ в саду сейчас немного, но это лучшее время, чтобы спланировать "
    "следующий сезон: пересмотреть схему посадок, отметить, какие места просят "
    "обновления, и подобрать сорта."
    "\n\n"
    "Ниже короткие подсказки по группам, на которые вы подписаны."
)


def _hero_for_season(season: str) -> tuple[str, str]:
    if season == "active":
        return _ACTIVE_HERO_TITLE, _ACTIVE_HERO_TEXT
    return _OFF_HERO_TITLE, _OFF_HERO_TEXT


def _hero_image_paths_legacy(week_key: str) -> tuple[str | None, str | None]:
    """Старый путь поиска hero-картинки. Сохранён для fallback-режима legacy."""
    static_root = getattr(settings, "BASE_DIR", None)
    if not static_root:
        return None, None
    rel_candidates = [
        f"media/digest/{week_key}.jpg",
        "media/digest/default-active.jpg",
        "media/digest/default-off.jpg",
    ]
    for rel in rel_candidates:
        local = static_root / "static" / rel
        if local.exists():
            return f"{SITE_URL}/static/{rel}", str(local)
    return None, None


# Legacy: статичные сезонные подсказки. Используются только если feature-flag
# CARE_USE_DB_CONTENT=0 (аварийный откат) - на случай если БД на проде не
# засеяна или ORM сломался. В нормальной работе блоки приходят из content.py.
_LEGACY_GROUP_HINTS_ACTIVE = {
    "trees": (
        "🌳",
        "Деревья",
        "Осмотр коры после зимы, санитарная обрезка, профилактика медьсодержащими "
        "до распускания почек.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/derevya/",
    ),
    "shrubs": (
        "🌿",
        "Кустарники",
        "Снимаем зимнее укрытие, проверяем корневую шейку у гортензии, "
        "обрезаем сухие ветви.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/kustarniki/",
    ),
    "perennials": (
        "💐",
        "Многолетники",
        "Цветущие, теневые и засухоустойчивые требуют разного подхода. "
        "Лёгкая стартовая подкормка и мульча.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/mnogoletniki/",
    ),
    "roses": (
        "🌹",
        "Розы",
        "Формирующая обрезка после снятия укрытия и первая подкормка азотом. "
        "От этой обрезки зависит цветение в июле.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/rozy/",
    ),
    "lawn": (
        "🌾",
        "Газон",
        "Вычёсывание после зимы, аэрация, первая стрижка на максимальной высоте.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/gazon/",
    ),
}

_LEGACY_GROUP_HINTS_OFF = {
    "trees": (
        "🌳",
        "Деревья",
        "Зимняя проверка обвязки от грызунов, защита штамбов от солнечных ожогов.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/derevya/",
    ),
    "shrubs": (
        "🌿",
        "Кустарники",
        "Контроль укрытия гортензий, осмотр после оттепелей, защита от снеголома.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/kustarniki/",
    ),
    "perennials": (
        "💐",
        "Многолетники",
        "Планируем размещение на следующий сезон, изучаем каталог сортов.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/mnogoletniki/",
    ),
    "roses": (
        "🌹",
        "Розы",
        "Контроль воздушно-сухого укрытия, проветривание в оттепели.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/rozy/",
    ),
    "lawn": (
        "🌾",
        "Газон",
        "Зимой газон в покое. Планируем подкормки и регенерацию весной.",
        f"{SITE_URL}/sluzhba-zaboty/calendar/gazon/",
    ),
}


def _blocks_from_db(slugs: list[str], week_key: str) -> list[DigestBlock]:
    """Блоки на основе CareCalendarPeriod в БД (основной путь)."""
    entries = select_entries_for_week(slugs, week_key, site_url=SITE_URL)
    blocks: list[DigestBlock] = []
    for cat in entries:
        blocks.append(DigestBlock(
            emoji=cat.emoji,
            title=cat.category_label,
            plants=cat.plants,
            category_slug=cat.category_slug,
            category_url=f"{SITE_URL}/sluzhba-zaboty/calendar/{cat.category_slug}/",
            hero_image_url=cat.hero_image_url,
            hero_image_path=cat.hero_image_path,
        ))
    return blocks


def _trim_blocks_for_short_channel(blocks: list[DigestBlock], limit: int) -> list[DigestBlock]:
    """Возвращает копию blocks с ограничением списка растений на категорию.

    Email пусть видит весь список (там лимита нет), а TG/MAX отдают первые
    `limit` штук плюс маркер `extra_count`, который шаблон превращает в
    строку «и ещё N растений с работами на этой неделе → раздел календаря».
    """
    trimmed: list[DigestBlock] = []
    for b in blocks:
        if len(b.plants) <= limit:
            extra = 0
            plants = b.plants
        else:
            extra = len(b.plants) - limit
            plants = b.plants[:limit]
        nb = DigestBlock(
            emoji=b.emoji,
            title=b.title,
            plants=plants,
            category_slug=b.category_slug,
            category_url=b.category_url,
            hero_image_url=b.hero_image_url,
            hero_image_path=b.hero_image_path,
        )
        nb.extra_count = extra  # type: ignore[attr-defined]
        trimmed.append(nb)
    return trimmed


def _blocks_legacy(slugs: list[str], season: str) -> list[DigestBlock]:
    """Аварийный путь: статичные подсказки одного предложения на категорию.

    Используется только если CARE_USE_DB_CONTENT=0 или БД недоступна. Каждый
    блок имеет ровно одну псевдо-запись растения без даты.
    """
    table = _LEGACY_GROUP_HINTS_ACTIVE if season == "active" else _LEGACY_GROUP_HINTS_OFF
    out: list[DigestBlock] = []
    for slug in slugs:
        if slug == "seasonal":
            continue
        hint = table.get(slug)
        if not hint:
            continue
        emoji, title, body, url = hint
        out.append(DigestBlock(
            emoji=emoji,
            title=title,
            plants=[PlantEntry(
                name=title,
                summary=body,
                url=url,
                date_label="",
                is_upcoming=False,
                plant_slug="",
                category_slug="",
            )],
        ))
    return out


def _absolute_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{SITE_URL}{path}"


def _manage_links(sub: CareSubscription) -> tuple[str, str]:
    sig = sub.signed_token()
    base_manage = reverse("care_notifications:manage")
    base_unsub = reverse("care_notifications:unsubscribe")
    manage = _absolute_url(f"{base_manage}?t={sub.token}&s={sig}")
    unsub = _absolute_url(f"{base_unsub}?t={sub.token}&s={sig}")
    return manage, unsub


def build_payload(subscription: CareSubscription, week_key: str | None = None) -> DigestPayload | None:
    """Сборка полезной нагрузки дайджеста для подписки.

    Возвращает None, если у подписки нет ни одной группы с актуальным
    контентом - оркестратор интерпретирует это как «пропустить отправку
    на этой неделе». Это бывает зимой по группам без работ в межсезонье.
    """
    now = timezone.now()
    week = week_key or get_current_week_key(now)
    season = _season_label(now)
    hero_title, hero_text = _hero_for_season(season)

    slugs = list(subscription.groups or [])

    if os.environ.get("CARE_USE_DB_CONTENT", "1").strip() == "1":
        blocks = _blocks_from_db(slugs, week)
    else:
        blocks = _blocks_legacy(slugs, season)

    # Если подписка только на seasonal-группу - блоки пусты, но письмо всё
    # равно отправляем (там hero-текст со сводкой по сезону).
    has_seasonal = "seasonal" in slugs
    if not blocks and not has_seasonal:
        return None

    # Hero-картинка: первое непустое фото первого блока (если у пользователя
    # есть блоки). Если только seasonal - hero-картинки нет.
    hero_url: str | None = None
    hero_local: str | None = None
    for b in blocks:
        if b.hero_image_url:
            hero_url, hero_local = b.hero_image_url, b.hero_image_path
            break

    manage_url, unsub_url = _manage_links(subscription)
    footer = DigestFooter(
        site_url=SITE_URL,
        telegram_url=TELEGRAM_BOT_URL,
        max_url=MAX_BOT_URL,
        manage_url=manage_url,
        unsubscribe_url=unsub_url,
    )

    subject = f"{hero_title} - {format_week_display(week)}" if blocks else hero_title
    return DigestPayload(
        week_key=week,
        subject=subject,
        hero_image_url=hero_url,
        hero_image_path=hero_local,
        hero_title=hero_title,
        hero_text=hero_text,
        blocks=blocks,
        footer=footer,
        season_label=season,
        meta={"subscription_id": subscription.id},
    )


def _ctx(payload: DigestPayload) -> dict[str, Any]:
    return {
        "week_key": payload.week_key,
        "week_display": format_week_display(payload.week_key),
        "subject": payload.subject,
        "hero_image_url": payload.hero_image_url,
        "hero_title": payload.hero_title,
        "hero_text": payload.hero_text,
        "blocks": payload.blocks,
        "footer": payload.footer,
        "season_label": payload.season_label,
    }


def render_email(payload: DigestPayload) -> str:
    """HTML для отправки в Unisender (inline CSS, без внешних ресурсов кроме hero-img)."""
    return render_to_string("care_notifications/digest_email.html", _ctx(payload))


def render_telegram(payload: DigestPayload) -> str:
    """Markdown-V1 текст для Telegram Bot API (parse_mode=Markdown).

    Лимит Telegram sendMessage = 4096 символов, поэтому каждую категорию
    ужимаем до _PLANTS_PER_CATEGORY_TG записей с «и ещё N на сайте».
    """
    ctx = _ctx(payload)
    ctx["blocks"] = _trim_blocks_for_short_channel(payload.blocks, _PLANTS_PER_CATEGORY_TG)
    return render_to_string("care_notifications/digest_telegram.txt", ctx)


def render_max(payload: DigestPayload) -> str:
    """Markdown для MAX Bot API. Тот же лимит длины, что у TG."""
    ctx = _ctx(payload)
    ctx["blocks"] = _trim_blocks_for_short_channel(payload.blocks, _PLANTS_PER_CATEGORY_TG)
    return render_to_string("care_notifications/digest_max.txt", ctx)
