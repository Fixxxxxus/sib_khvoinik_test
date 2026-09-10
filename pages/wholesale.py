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


def _base_context(request: HttpRequest) -> dict:
    """Общая обвязка страниц каталога: скрытость, корзина, конфиг скидок."""
    return {
        "brand": OPT_BRAND,
        "opt_phone": OPT_PHONE,
        "opt_phone_href": OPT_PHONE_HREF,
        # noindex + отсутствие навбара и футера сайта: рекламный контур не должен
        # ни индексироваться, ни утекать в общую навигацию.
        "noindex": True,
        "landing_mode": True,
        "hide_footer": True,
        "skip_schema_org": True,
        "discount_config_json": json.dumps(
            wholesale_pricing.tiers_for_frontend(), ensure_ascii=False
        ),
        "discount_tiers": wholesale_pricing.tiers_for_display(),
        "discount_approved": wholesale_pricing.DISCOUNT_TIERS_APPROVED,
        "discount_disclaimer": wholesale_pricing.DISCOUNT_DISCLAIMER,
        "discount_basis": wholesale_pricing.DISCOUNT_BASIS,
        # Деления полосы прогресса: ноль плюс пороги сетки. Заполнение считает JS,
        # разметку делений отдаём сразу, чтобы полоса не прыгала после загрузки.
        "progress_marks": _progress_marks(),
        "progress_hint_default": wholesale_pricing.progress_hint(Decimal(0), 0),
        "min_order": wholesale_pricing.min_order_for_display(),
    }


def _short_mark(value: int) -> str:
    """Подпись деления: 4000 -> «4к», 1500000 -> «1,5 млн». Как на референсе."""
    if value >= 1_000_000:
        millions = value / 1_000_000
        text = f"{millions:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} млн"
    if value >= 1000:
        thousands = value / 1000
        text = f"{thousands:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text}к"
    return str(value)


def _progress_marks() -> list[dict]:
    marks = [{"value": 0, "label": "0", "percent": 0}]
    for tier in wholesale_pricing.tiers_for_frontend()["tiers"]:
        marks.append(
            {
                "value": tier["threshold"],
                "label": _short_mark(tier["threshold"]),
                "percent": tier["percent"],
            }
        )
    return marks


def _active_sections():
    return WholesaleSection.objects.filter(is_active=True).prefetch_related(
        "items", "items__variants"
    )


def _section_items(section: WholesaleSection):
    return section.items.filter(is_active=True).prefetch_related("variants")


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
    ctx = _base_context(request)
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
        item = WholesaleItem.objects.select_related("section").get(
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

    ctx = _base_context(request)
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
