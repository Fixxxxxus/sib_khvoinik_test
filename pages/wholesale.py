"""Скрытый оптовый каталог /opt/ под Яндекс.Директ: витрина, раздел, карточка.

Контур URL зафиксирован под объявления и UTM, менять его после запуска рекламы
нельзя:
    /opt/                        - витрина каталога
    /opt/<раздел>/               - раздел
    /opt/<раздел>/<позиция>/     - карточка позиции

Каталог скрыт: ссылок из меню и футера нет, страницы отдаются с noindex,
в sitemap.xml и llms.txt не попадают. Публичный /catalog/ не затрагивается.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from . import wholesale_pricing
from .models import WholesaleItem, WholesaleSection

# Тексты витрины держим здесь, а не в data.py: раздел рекламный и живёт
# отдельным контуром, смешивать его с контентом сайта незачем.
OPT_BRAND = "Сибирские газоны"
OPT_TITLE = "Оптовый каталог"
OPT_INTRO = (
    "Позиции текущего плана продаж для садовых центров, подрядчиков и озеленителей. "
    "Цены оптовые, отгрузка партиями. Соберите заказ и отправьте его менеджеру."
)

# Телефон и адрес витрины заказчик подтвердит отдельно (см. ТЗ, §7.5).
# Пока показываем общий отдел продаж с сайта.
OPT_PHONE = "+7 (913) 721-76-55"
OPT_PHONE_HREF = "+79137217655"
# Кнопка «MAX»: ссылка на профиль владельца оптового номера (от Стаса
# 14.09.2026). Ссылки по номеру телефона у MAX нет. Пусто - кнопки нет.
OPT_MAX_URL = "https://max.ru/u/f9LHodD0cOK1I6zZHasDVYn3xHS3CI-9moSrEV7GZbFIJNwInW_6-AP8UZ0"

# Ниже этого остатка на плитке и в карточке загорается бейдж «осталось N шт».
# Порог живёт здесь одним числом: разбрасывать его по шаблонам нельзя.
# Работает только по числовому остатку из поля «Наличие»: «в наличии» и
# «уточняйте» остатка не несут, бейджа у них нет.
LOW_STOCK_THRESHOLD = 200

# Фон hero на витрине: сосна горная «Мугус» из макета маркетолога (по его
# просьбе от 13.09.2026). Общий кадр питомника лежит рядом в opt-hero-pitomnik.webp.
OPT_HERO_IMAGE = "media/images/opt/opt-hero-sosna-mugus.webp"
OPT_HERO_KICKER = OPT_BRAND


def hero_title() -> str:
    """H1 витрины: обе входные скидки прямо в заголовке.

    Проценты берутся из сетки скидок, а не пишутся руками: поменяли лестницу -
    заголовок поехал следом. Первая группа идёт с большой буквы, остальные
    перечисляются через запятую строчными.
    """
    parts = []
    for key in wholesale_pricing.group_keys():
        title = wholesale_pricing.group_title(key)
        if parts:
            title = title.lower()
        parts.append(f"{title} −{wholesale_pricing.entry_percent(key)}%")
    return "Опт с первой штуки. " + ", ".join(parts)


OPT_HERO_TITLE = hero_title()
OPT_HERO_LEAD = (
    "Актуальный план для садовых центров и подрядчиков: деревья, кустарники, "
    "хвойные. Соберите заказ и отправьте менеджеру."
)


def _base_context(request: HttpRequest, group: str | None = None) -> dict:
    """Общая обвязка страниц каталога: скрытость, корзина, конфиг скидок.

    group - ключ лестницы страницы (деревья считаются по своей). Ключи без
    суффикса остаются лестницей группы страницы, а для витрины это default:
    шаблоны, не знающие о группах, работают как раньше.
    """
    group = group or wholesale_pricing.DEFAULT_GROUP
    return {
        "brand": OPT_BRAND,
        # Ссылки на разделы в шапке: строятся из активных разделов, а не
        # прибиты к слагам. На витрине это якоря, на остальных страницах -
        # переход на витрину к нужной группе.
        "nav_sections": _nav_sections(request),
        "opt_phone": OPT_PHONE,
        "opt_phone_href": OPT_PHONE_HREF,
        "opt_max_url": OPT_MAX_URL,
        # noindex + отсутствие навбара и футера сайта: рекламный контур не должен
        # ни индексироваться, ни утекать в общую навигацию.
        "noindex": True,
        "landing_mode": True,
        "hide_footer": True,
        "skip_schema_org": True,
        "discount_config_json": json.dumps(
            wholesale_pricing.tiers_for_frontend(), ensure_ascii=False
        ),
        "discount_tiers": wholesale_pricing.tiers_for_display(group),
        # Лента чипов на витрине: подписи собираются из той же сетки скидок.
        "discount_chips": wholesale_pricing.tiers_for_chips(group),
        # Обе лестницы сразу: витрине надо показать и деревья, и остальное.
        "discount_ladders": _discount_ladders(),
        "section_group": group,
        "discount_approved": wholesale_pricing.DISCOUNT_TIERS_APPROVED,
        "discount_disclaimer": wholesale_pricing.DISCOUNT_DISCLAIMER,
        "discount_basis": wholesale_pricing.DISCOUNT_BASIS,
        "discount_entry_percent": wholesale_pricing.entry_percent(group),
        "discount_individual_text": wholesale_pricing.INDIVIDUAL_TIER_TEXT,
        # Деления полосы прогресса: по одному на ступень сетки. Заполнение считает
        # JS, разметку делений отдаём сразу, чтобы полоса не прыгала после загрузки.
        "progress_marks": _progress_marks(group),
        "progress_hint_default": wholesale_pricing.progress_hint(Decimal(0), 0, group),
        "min_order": wholesale_pricing.min_order_for_display(),
    }


def _nav_sections(request: HttpRequest) -> list[dict]:
    """Разделы для шапки: заголовок и ссылка на якорь группы на витрине."""
    on_index = request.path == "/opt/"
    rows = []
    sections = (
        WholesaleSection.objects.filter(is_active=True, items__is_active=True)
        .only("title", "slug")
        .distinct()
    )
    for section in sections:
        anchor = f"#section-{section.slug}"
        rows.append({"title": section.title, "href": anchor if on_index else f"/opt/{anchor}"})
    return rows


def _discount_ladders() -> list[dict]:
    """Обе лестницы для шаблона: общая первой, деревья второй.

    Порядок фиксированный: сначала «Кустарники и хвойные», потом «Деревья».
    Структура одна на обе, чтобы шаблон рисовал их одним циклом.
    """
    ladders = []
    for key in wholesale_pricing.group_keys():
        ladders.append(
            {
                "key": key,
                "title": wholesale_pricing.group_title(key),
                "entry_percent": wholesale_pricing.entry_percent(key),
                "chips": wholesale_pricing.tiers_for_chips(key),
                "tiers": wholesale_pricing.tiers_for_display(key),
            }
        )
    return ladders


def _progress_marks(group: str | None = None) -> list[dict]:
    """Подписи делений полосы: по ступеням сетки, в порядке выгодности."""
    group = group or wholesale_pricing.DEFAULT_GROUP
    marks = [{"key": "start", "label": "0", "percent": 0, "individual": False}]
    for tier in wholesale_pricing.tiers_for_json(group):
        marks.append(
            {
                "key": tier["key"],
                "label": tier["short"] or tier["label"],
                "percent": tier["percent"],
                "individual": tier["individual"],
            }
        )
    return marks


def _active_sections():
    return WholesaleSection.objects.filter(is_active=True).prefetch_related(
        "items", "items__variants", "items__photos"
    )


def _section_items(section: WholesaleSection):
    return section.items.filter(is_active=True).prefetch_related("variants", "photos")


def opt_index(request: HttpRequest) -> HttpResponse:
    """GET /opt/ - витрина: разделы плана продаж и акцентные позиции."""
    sections = []
    for section in _active_sections():
        items = list(_section_items(section))
        if not items:
            continue
        sections.append({"section": section, "items": items, "count": len(items)})

    highlighted = [
        item
        for block in sections
        for item in block["items"]
        if item.is_highlighted
    ][:8]

    ctx = _base_context(request)
    ctx.update(
        {
            "seo_title": f"{OPT_TITLE} · {OPT_BRAND}",
            "meta_description": OPT_INTRO,
            "opt_title": OPT_TITLE,
            "opt_intro": OPT_INTRO,
            "hero_image": OPT_HERO_IMAGE,
            "hero_kicker": OPT_HERO_KICKER,
            "hero_title": hero_title(),
            "hero_lead": OPT_HERO_LEAD,
            "sections": sections,
            "highlighted": highlighted,
            "breadcrumbs": [],
        }
    )
    return render(request, "pages/opt/index.html", ctx)


def opt_section(request: HttpRequest, section_slug: str) -> HttpResponse:
    """GET /opt/<раздел>/ - позиции раздела."""
    try:
        section = WholesaleSection.objects.get(slug=section_slug, is_active=True)
    except WholesaleSection.DoesNotExist:
        raise Http404("Раздел оптового каталога не найден")

    items = list(_section_items(section))
    ctx = _base_context(request, wholesale_pricing.group_key_for_section(section.slug))
    ctx.update(
        {
            "seo_title": f"{section.title} оптом · {OPT_BRAND}",
            "meta_description": section.intro or OPT_INTRO,
            "opt_title": section.title,
            "opt_intro": section.intro,
            "section": section,
            "items": items,
            "breadcrumbs": [(OPT_TITLE, "/opt/")],
        }
    )
    return render(request, "pages/opt/section.html", ctx)


def opt_item(request: HttpRequest, section_slug: str, item_slug: str) -> HttpResponse:
    """GET /opt/<раздел>/<позиция>/ - карточка позиции с кнопкой «В корзину»."""
    try:
        item = WholesaleItem.objects.select_related("section").prefetch_related("photos").get(
            slug=item_slug,
            section__slug=section_slug,
            is_active=True,
            section__is_active=True,
        )
    except WholesaleItem.DoesNotExist:
        raise Http404("Позиция оптового каталога не найдена")

    same_section = [
        other
        for other in _section_items(item.section)
        if other.pk != item.pk
    ][:6]

    ctx = _base_context(request, item.discount_group)
    ctx.update(
        {
            "seo_title": f"{item.title} оптом · {OPT_BRAND}",
            "meta_description": (item.short_description or OPT_INTRO)[:300],
            "item": item,
            "price_ladder": item.price_ladder(),
            "variants": item.active_variants(),
            "section": item.section,
            "same_section": same_section,
            "breadcrumbs": [(OPT_TITLE, "/opt/"), (item.section.title, item.section.get_absolute_url())],
        }
    )
    return render(request, "pages/opt/item.html", ctx)
