"""SEO/GEO-инфраструктура: robots.txt, sitemap.xml, llms.txt, JSON-LD хелперы.

Всё отдаётся через Django (конвенция проекта: SEO-файлы не живут в docs/).
JSON-LD собирается во view питоном (json.dumps) и попадает в шаблон готовой
строкой jsonld_blocks - шаблоны не строят JSON сами.
"""
from __future__ import annotations

import json
import re
from typing import Any

from django.http import HttpResponse
from django.urls import reverse

SITE_ORIGIN = "https://gazony.ru"

# Ключ IndexNow (Яндекс + Bing): файл /<key>.txt должен отдавать сам ключ.
INDEXNOW_KEY = "bfd2821af4b12e80d6195befb4466c04"

_PRICE_RE = re.compile(r"\d[\d\s ]*")


def absolute(path: str) -> str:
    return f"{SITE_ORIGIN}{path}"


def jsonld(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def price_number(price_str: str | None) -> str | None:
    """'1 590 ₽' -> '1590' (schema.org price - число строкой)."""
    m = _PRICE_RE.search(price_str or "")
    if not m:
        return None
    return re.sub(r"[\s ]", "", m.group(0))


# ---------------------------------------------------------------------------
# JSON-LD builders
# ---------------------------------------------------------------------------

def faq_jsonld(faq: list[dict[str, str]]) -> str:
    return jsonld({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in faq
        ],
    })


def breadcrumbs_jsonld(items: list[tuple[str, str]]) -> str:
    """items: [(название, путь), ...] - путь относительный, '/catalog/'."""
    return jsonld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": absolute(path),
            }
            for i, (name, path) in enumerate(items)
        ],
    })


def product_jsonld(plant: dict[str, Any], canonical_path: str) -> str | None:
    """Product + Offer/AggregateOffer из карточки растения каталога."""
    variants = plant.get("variants") or []
    prices = [p for p in (price_number(v.get("price")) for v in variants) if p]
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": plant.get("catalog_display_name") or plant.get("name") or "",
        "description": (plant.get("description") or "")[:500],
        "category": plant.get("category_slug") or "",
        "url": absolute(canonical_path),
        "brand": {"@id": f"{SITE_ORIGIN}/#organization"},
    }
    image = plant.get("image")
    if image:
        data["image"] = absolute(f"/static/{image}")
    if not prices:
        return jsonld(data)
    in_stock = any(v.get("in_stock") for v in variants)
    availability = (
        "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock"
    )
    nums = sorted(int(p) for p in prices)
    if len(nums) == 1:
        data["offers"] = {
            "@type": "Offer",
            "price": str(nums[0]),
            "priceCurrency": "RUB",
            "availability": availability,
            "url": absolute(canonical_path),
            "seller": {"@id": f"{SITE_ORIGIN}/#organization"},
        }
    else:
        data["offers"] = {
            "@type": "AggregateOffer",
            "lowPrice": str(nums[0]),
            "highPrice": str(nums[-1]),
            "offerCount": len(nums),
            "priceCurrency": "RUB",
            "availability": availability,
            "url": absolute(canonical_path),
            "seller": {"@id": f"{SITE_ORIGIN}/#organization"},
        }
    return jsonld(data)


def article_jsonld(article: dict[str, Any], canonical_path: str) -> str:
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.get("title") or "",
        "description": article.get("excerpt") or "",
        "inLanguage": "ru-RU",
        "mainEntityOfPage": absolute(canonical_path),
        "publisher": {"@id": f"{SITE_ORIGIN}/#organization"},
        "author": {
            "@type": "Organization",
            "name": "Агрономы компании «Сибирские газоны»",
            "url": absolute("/o-kompanii/"),
        },
    }
    if article.get("date_published"):
        data["datePublished"] = article["date_published"]
    if article.get("date_modified"):
        data["dateModified"] = article["date_modified"]
    if article.get("image"):
        data["image"] = absolute(f"/static/{article['image']}")
    return jsonld(data)


# ---------------------------------------------------------------------------
# robots.txt / sitemap.xml / llms.txt / IndexNow
# ---------------------------------------------------------------------------

ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /zayavka-direct/
Disallow: /direct-50/
Disallow: /discount/

# AI-краулеры: доступ открыт явно
User-agent: GPTBot
Disallow: /admin/

User-agent: OAI-SearchBot
Disallow: /admin/

User-agent: ChatGPT-User
Disallow: /admin/

User-agent: ClaudeBot
Disallow: /admin/

User-agent: anthropic-ai
Disallow: /admin/

User-agent: PerplexityBot
Disallow: /admin/

User-agent: YandexBot
Disallow: /admin/

Sitemap: https://gazony.ru/sitemap.xml
"""


def robots_txt(request):
    return HttpResponse(ROBOTS_TXT, content_type="text/plain; charset=utf-8")


def indexnow_key(request):
    return HttpResponse(INDEXNOW_KEY, content_type="text/plain; charset=utf-8")


# Подтверждение прав Яндекс.Вебмастера способом «HTML-файл»: Яндекс проверяет
# файл /yandex_<hash>.html и ждёт в теле строку «Verification: <hash>».
YANDEX_VERIFICATION_HASH = "89218f181b73f8a9"
YANDEX_VERIFICATION_HTML = (
    "<html>\n"
    "    <head>\n"
    '        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n'
    "    </head>\n"
    f"    <body>Verification: {YANDEX_VERIFICATION_HASH}</body>\n"
    "</html>"
)


def yandex_verification(request):
    return HttpResponse(YANDEX_VERIFICATION_HTML, content_type="text/html; charset=utf-8")


def _static_sitemap_paths() -> list[str]:
    names = [
        "home", "gazon", "roll_lawn_price", "ozelenenie_b2c", "b2b",
        "pitomnik", "sadovye_centry", "catalog", "sluzhba_zaboty",
        "calendar", "stati_list", "kontakty", "o_kompanii",
        "privacy", "consent", "predzakaz", "akciya_hvoynye_50",
    ]
    paths = []
    for name in names:
        try:
            paths.append(reverse(name))
        except Exception:
            continue
    return paths


def sitemap_xml(request):
    from .catalog_merge import get_merged_catalog_plants
    from .catalog_subcategories import all_catalog_category_slugs
    from .catalog_context import get_catalog_page_for_template
    from .calendar_live import merge_calendar_base
    from .data import CALENDAR_PAGE, STATI_PAGE

    paths: list[str] = list(_static_sitemap_paths())

    # Каталог: категории + карточки растений (на проде - из БД).
    try:
        ctx = get_catalog_page_for_template()
        for slug in all_catalog_category_slugs(ctx.get("categories") or []):
            paths.append(f"/catalog/{slug}/")
        merged, _ = get_merged_catalog_plants()
        for plant in merged:
            if plant.get("slug"):
                paths.append(f"/catalog/{plant['slug']}/")
    except Exception:
        pass

    # Статьи.
    for art in STATI_PAGE.get("articles", []):
        if art.get("slug"):
            paths.append(f"/stati/{art['slug']}/")

    # Календарь ухода: категории и растения.
    try:
        cal = merge_calendar_base(dict(CALENDAR_PAGE))
        for cat in cal.get("categories", []):
            paths.append(f"/sluzhba-zaboty/calendar/{cat['slug']}/")
        for plant in cal.get("plants", []):
            cat_slug = plant.get("category_slug")
            if cat_slug and plant.get("slug"):
                paths.append(f"/sluzhba-zaboty/calendar/{cat_slug}/{plant['slug']}/")
    except Exception:
        pass

    seen: set[str] = set()
    urls = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        urls.append(f"  <url><loc>{absolute(p)}</loc></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


LLMS_TXT = """# Сибирские газоны

> Производитель рулонного газона, питомник растений и компания технологичного
> озеленения в Новосибирске. Работаем с 1999 года. Собственные поля рулонного
> газона (около 200 га), питомник 22 га и тепличный комплекс 5000 м².
> Юрлицо: ООО «Сибирский хвойник», ИНН 5406843096.

Сайт на русском языке. Регион: Новосибирск и Сибирский федеральный округ.

## Основные разделы

- [Рулонный газон](https://gazony.ru/gazon/): производство, укладка, уход; FAQ по укладке и срокам
- [Прайс на рулонный газон](https://gazony.ru/prais-rulonnyy-gazon/): актуальные розничные цены за м², характеристики рулона
- [Питомник](https://gazony.ru/pitomnik/): выращивание деревьев и кустарников, адаптированных к климату Сибири
- [Каталог растений](https://gazony.ru/catalog/): около 900 позиций с ценами и наличием
- [Озеленение частных участков](https://gazony.ru/ozelenenie-b2c/): проектирование и реализация под ключ
- [B2B-проекты](https://gazony.ru/b2b/): поставки и благоустройство для девелоперов и подрядчиков
- [Садовые центры](https://gazony.ru/sadovye-centry/): Новосибирск (ТЦ МЕГА, ул. Ватутина, 107) и с. Новопичугово
- [Служба заботы](https://gazony.ru/sluzhba-zaboty/): сопровождение и сезонные рекомендации по уходу
- [Календарь ухода](https://gazony.ru/sluzhba-zaboty/calendar/): помесячные работы для 100+ растений
- [Статьи](https://gazony.ru/stati/): практические материалы об уходе за растениями в Сибири
- [О компании](https://gazony.ru/o-kompanii/): история, производство, реквизиты
- [Контакты](https://gazony.ru/kontakty/): телефоны, адреса, форма обратной связи

## Контакты

- Офис: Новосибирск, ул. Железнодорожная, 12/1, оф. 501, +7 (383) 201-06-00
- Отдел продаж: +7 (383) 375-15-22, price@gazony.ru
- Линия по газонам: rulony@gazony.ru
"""


def llms_txt(request):
    return HttpResponse(LLMS_TXT, content_type="text/plain; charset=utf-8")
