import re

from django.conf import settings
from django.http import Http404, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render

from .articles import find_article, merged_articles
from .catalog_context import get_catalog_page_for_template
from .catalog_nav import enrich_catalog_context
from .catalog_merge import find_merged_plant, get_merged_catalog_plants
from .catalog_products import plant_belongs_to_category, similar_plants_for_detail
from .catalog_subcategories import all_catalog_category_slugs, category_heading_for_slug
from .calendar_live import merge_calendar_base
from . import seo
from .models import PreorderGroup, PreorderSettings
from .data import (
    HOME_PAGE,
    GAZON_PAGE,
    ROLL_LAWN_PRICE_PAGE,
    UKLADKA_PAGE,
    UKLADKA_PRICE_FROM,
    OZELENENIE_B2C_PAGE,
    B2B_PAGE,
    PITOMNIK_PAGE,
    SADOVYE_CENTRY_PAGE,
    SLUZHBA_ZABOTY_PAGE,
    CALENDAR_PAGE,
    STATI_PAGE,
    KONTAKTY_PAGE,
    O_KOMPANII_PAGE,
    PRIVACY_PAGE,
    CONSENT_PAGE,
    DISCOUNT_LANDING_PAGE,
    DIRECT_LANDING_PAGE,
    PROMO_SALE50_SITE_PAGE,
    PROMO_SALE50_DIRECT_PAGE,
    KOTTEDZHI_DIRECT_PAGE,
    OZELENENIE_SEASON_END_PAGE,
    REVIEWS_DATA,
)


BRAND_SUFFIX = "Сибирские газоны"
CITY_SUFFIX = "купить в Новосибирске"


def _plant_display_name(plant: dict) -> str:
    return (plant.get("catalog_display_name") or plant.get("name") or "").strip()


def _plant_min_price_line(plant: dict) -> str | None:
    """Минимальная цена карточки строкой '590 ₽' или None, если цены нет."""
    line = (plant.get("catalog_price_line") or "").strip()
    if line and line.lower() != "уточняйте":
        return line
    nums = []
    for v in plant.get("variants") or []:
        digits = re.sub(r"\D", "", str(v.get("price") or ""))
        if digits:
            nums.append(int(digits))
    if not nums:
        return None
    return f"{min(nums):,}".replace(",", " ") + " ₽"


def _plant_in_stock(plant: dict) -> bool:
    return any(v.get("in_stock") for v in (plant.get("variants") or []))


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение числительных: 1 сорт, 2 сорта, 5 сортов."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _clean_sentence(text: str) -> str:
    """Убирает следы пустых подстановок: двойные пробелы, «( )», висячие знаки."""
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+([,.:;])", r"\1", text)
    text = re.sub(r"([,:;])\1+", r"\1", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,;:").strip()


# Значения-заглушки в данных каталога: в мету их пускать нельзя.
_SIZE_PLACEHOLDERS = ("выберите", "уточня", "формат")


def _seo_category_label(label: str) -> str:
    """«Деревья → Черёмуха» -> «Черёмуха (деревья)».

    Стрелка из видимой навигации в title смотрится мусором, а голого листа
    мало: «Лапчатка» есть и в кустарниках, и в многолетниках, а нам нужны
    непохожие title у разных категорий.
    """
    parts = [p.strip() for p in label.split("→") if p.strip()]
    if len(parts) < 2:
        return label.strip()
    return f"{parts[-1]} ({parts[0].lower()})"


def _sentences_within(parts: list[str], limit: int) -> str:
    """Собирает описание по целым предложениям, не обрезая на полуслове."""
    text = parts[0]
    for part in parts[1:]:
        candidate = f"{text} {part}"
        if len(candidate) > limit:
            break
        text = candidate
    return text


def _category_commercial_seo(label: str, plants_count: int) -> dict:
    """title / description категории каталога по формуле SEO-ТЗ (A2).

    Число сортов подставляется только когда оно реально есть: пустая категория
    не должна получить в описание «0 сортов».
    """
    name = _seo_category_label(label)
    seo_title = _clean_sentence(
        f"{name} купить в Новосибирске: цена и наличие | {BRAND_SUFFIX}"
    )
    if plants_count > 0:
        count_part = (
            f"{plants_count} "
            f"{_plural_ru(plants_count, 'сорт', 'сорта', 'сортов')} в наличии, "
        )
    else:
        count_part = ""
    meta = _sentences_within(
        [
            _clean_sentence(
                f"{name} из собственного питомника под Новосибирском: {count_part}"
                "адаптированы к сибирской зиме."
            ),
            "Цены, фото, самовывоз и доставка.",
            "Питомник 200 га, с 1999 года.",
        ],
        220,
    )
    return {"seo_title": seo_title, "meta_description": meta}


def _plant_size_line(plant: dict) -> str:
    """«h 40-60, контейнер C5/7» из вариантов карточки; пусто, если данных нет."""
    def usable(value: str) -> str:
        value = (value or "").strip()
        low = value.lower()
        if not value or any(bad in low for bad in _SIZE_PLACEHOLDERS):
            return ""
        return value

    variants = plant.get("variants") or []
    height = usable(plant.get("height"))
    if not height:
        height = next((h for h in (usable(v.get("height")) for v in variants) if h), "")
    container = usable(plant.get("catalog_container_line"))
    if not container:
        container = next(
            (c for c in (usable(v.get("container")) for v in variants) if c), ""
        )
    parts = [p for p in (height, f"контейнер {container}" if container else "") if p]
    return ", ".join(parts)


def _plant_commercial_seo(plant: dict) -> dict:
    """title / h1_suffix / meta_description карточки товара (коммерческий интент)."""
    # Формула A2: название + латынь в title, размер/контейнер в описании.
    # Пустая подстановка (нет латыни, нет высоты) даёт пустую строку, а не «0».
    name = (plant.get("title_ru") or "").strip() or _plant_display_name(plant)
    latin = (plant.get("title_latin") or "").strip()
    latin_part = f" ({latin})" if latin else ""
    seo_title = _clean_sentence(
        f"{name}{latin_part} {CITY_SUFFIX} - саженцы из питомника | {BRAND_SUFFIX}"
    )
    # Гео-суффикс держим только в title / og / мете: в видимом H1 он смотрится
    # навязчиво для живого посетителя, на ранжирование по гео это не влияет.
    h1_suffix = ""

    size_line = _plant_size_line(plant)
    size_part = f"{size_line}, " if size_line else ""
    price_line = _plant_min_price_line(plant)
    price_part = f"цена от {price_line}" if price_line else "цена по запросу"
    stock_part = "Есть в наличии" if _plant_in_stock(plant) else "Поставка под заказ"
    # В описании берём витринное имя целиком (с сортом): у одного вида бывает
    # два десятка сортов, и по короткому имени описания склеились бы в дубли.
    full_name = _plant_display_name(plant) or name
    meta = _sentences_within(
        [
            _clean_sentence(
                f"Саженцы {full_name} в Новосибирске: {size_part}зимостойкость, {price_part}."
            ),
            f"{stock_part}, самовывоз в Кольцово.",
            "Выращены в нашем питомнике, не привозной импорт.",
        ],
        220,
    )
    return {
        "seo_title": seo_title,
        "plant_h1_suffix": h1_suffix,
        "meta_description": meta,
    }


def _norm_legacy_path(path: str) -> str:
    p = "/" + str(path or "").strip().strip("/")
    return p + "/" if p != "/" else p


def _build_legacy_redirect_map() -> dict:
    """{старый /product/...-путь -> актуальный /catalog/<slug>/} из категорий и растений."""
    mapping: dict[str, str] = {}
    ctx = get_catalog_page_for_template()
    for cat in ctx.get("categories") or []:
        slug = cat.get("slug")
        if not slug:
            continue
        for lp in cat.get("legacy_paths") or []:
            mapping[_norm_legacy_path(lp)] = f"/catalog/{slug}/"
    merged, _ = get_merged_catalog_plants()
    for plant in merged:
        slug = plant.get("slug")
        if not slug:
            continue
        for lp in plant.get("legacy_paths") or []:
            mapping.setdefault(_norm_legacy_path(lp), f"/catalog/{slug}/")
    return mapping


def legacy_product_redirect(request):
    """301 со старых URL каталога (/product/...) на актуальные страницы каталога.

    Точное совпадение ведёт на конкретную карточку или раздел. Всё остальное под
    retired-деревом /product/ (категорийные URL, дрейф слагов БД vs data.py,
    любые старые адреса из индекса) отправляем на корень каталога, чтобы ни один
    старый URL не упирался в 404 и не терял ссылочный вес.
    """
    mapping = _build_legacy_redirect_map()
    target = mapping.get(_norm_legacy_path(request.path))
    if target:
        return HttpResponsePermanentRedirect(target)
    return HttpResponsePermanentRedirect("/catalog/")


_RU_MONTHS_GENITIVE = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

# Общая шкала для отрисовки звёзд (1..5) в видимом блоке отзывов.
STAR_SCALE = [1, 2, 3, 4, 5]


def _review_date_display(iso: str) -> str:
    """ISO-дату '2024-10-14' -> '14 октября 2024' (для видимого блока отзывов)."""
    try:
        y, m, d = (int(x) for x in str(iso).split("-"))
        return f"{d} {_RU_MONTHS_GENITIVE[m]} {y}"
    except (ValueError, IndexError):
        return str(iso or "")


def _reviews_items(centers=None):
    """Список отзывов с человекочитаемой датой; при centers - фильтр по центрам."""
    items = []
    for it in REVIEWS_DATA["items"]:
        if centers is not None and it["center"] not in centers:
            continue
        item = dict(it)
        item["date_display"] = _review_date_display(it.get("date"))
        items.append(item)
    return items


def _catalog_positions_note(default: str = "1000+ растений") -> str:
    """Подпись карточки каталога на главной из реального размера каталога.

    Округляем вниз до сотни: обещать точное число позиций нельзя, оно меняется
    с каждой выгрузкой, а «700+» остаётся правдой между обновлениями.
    """
    try:
        plants, _ = get_merged_catalog_plants()
        count = len(plants)
    except Exception:
        return default
    if count < 100:
        return default
    return f"{count // 100 * 100}+ позиций"


def _home_main_directions() -> list[dict]:
    items = [dict(item) for item in HOME_PAGE.get("main_directions") or []]
    for item in items:
        if item.get("href") == "/catalog/":
            item["note"] = _catalog_positions_note(item.get("note") or "")
    return items


def home(request):
    ctx = dict(HOME_PAGE)
    ctx["main_directions"] = _home_main_directions()
    ctx["reviews_aggregate"] = REVIEWS_DATA["aggregate"]
    # Компактный блок на главной: 6 отзывов (брендовые запросы + rich-сниппет).
    ctx["reviews_items"] = _reviews_items()[:6]
    ctx["star_scale"] = STAR_SCALE
    return render(request, "pages/home.html", ctx)


def gazon(request):
    ctx = dict(GAZON_PAGE)
    # Product + Offer с ценой рулонного газона (цена в сниппет). Цены из прайса.
    roll_product = {
        "name": "Рулонный газон",
        "description": GAZON_PAGE["meta_description"],
        "category_slug": "Рулонный газон",
        "variants": [
            {"price": row["price"], "in_stock": True}
            for row in ROLL_LAWN_PRICE_PAGE["price_rows"]
        ],
    }
    blocks = [seo.faq_jsonld(GAZON_PAGE["faq"])]
    product = seo.product_jsonld(roll_product, "/gazon/")
    if product:
        blocks.append(product)
    ctx["jsonld_blocks"] = blocks
    return render(request, "pages/gazon.html", ctx)


def roll_lawn_price(request):
    """Прайс рулонного газона: пункт «Рулонные газоны» в боковом меню каталога."""
    ctx = dict(ROLL_LAWN_PRICE_PAGE)
    ctx["active_catalog_nav_route"] = "roll_lawn_price"
    blocks = []
    offer = seo.roll_lawn_offer_jsonld(
        ROLL_LAWN_PRICE_PAGE["price_rows"], "/prais-rulonnyy-gazon/"
    )
    if offer:
        blocks.append(offer)
    blocks.append(
        seo.breadcrumbs_jsonld([
            ("Главная", "/"),
            ("Рулонный газон", "/gazon/"),
            ("Прайс на рулонный газон", "/prais-rulonnyy-gazon/"),
        ])
    )
    ctx["jsonld_blocks"] = blocks
    return render(request, "pages/roll-lawn-price.html", enrich_catalog_context(ctx))


def ukladka(request):
    """Лендинг «Укладка рулонного газона»: отдельная посадочная под кластер «укладка».

    Цена укладки живёт в UKLADKA_PRICE_FROM (pages/data.py). Пока она None,
    в Service-разметке блока offers нет: цену в микроразметку не выдумываем.
    """
    ctx = dict(UKLADKA_PAGE)
    canonical = UKLADKA_PAGE["canonical_path"]
    ctx["jsonld_blocks"] = [
        seo.service_jsonld(
            name="Укладка рулонного газона",
            description=UKLADKA_PAGE["meta_description"],
            canonical_path=canonical,
            service_type="Укладка рулонного газона",
            price_from=UKLADKA_PRICE_FROM,
        ),
        seo.faq_jsonld(UKLADKA_PAGE["faq"]),
        seo.breadcrumbs_jsonld([
            ("Главная", "/"),
            ("Рулонный газон", "/gazon/"),
            ("Укладка рулонного газона", canonical),
        ]),
    ]
    return render(request, "pages/ukladka.html", ctx)


def ozelenenie_b2c(request):
    return render(request, "pages/ozelenenie-b2c.html", OZELENENIE_B2C_PAGE)


def b2b(request):
    return render(request, "pages/b2b.html", B2B_PAGE)


def pitomnik(request):
    return render(request, "pages/pitomnik.html", PITOMNIK_PAGE)


def sadovye_centry(request):
    ctx = dict(SADOVYE_CENTRY_PAGE)
    ctx["reviews_aggregate"] = REVIEWS_DATA["aggregate"]
    ctx["reviews_center_mega"] = REVIEWS_DATA["centers"]["МЕГА"]
    ctx["reviews_center_novopichugovo"] = REVIEWS_DATA["centers"]["Новопичугово"]
    # На странице центров показываем отзывы про конкретные точки (МЕГА / Новопичугово).
    ctx["reviews_mega"] = _reviews_items(centers=["МЕГА"])
    ctx["reviews_novopichugovo"] = _reviews_items(centers=["Новопичугово"])
    ctx["star_scale"] = STAR_SCALE
    return render(request, "pages/sadovye-centry.html", ctx)


def catalog(request):
    return render(request, "pages/catalog.html", enrich_catalog_context(get_catalog_page_for_template()))


def catalog_search_index(request):
    """JSON-индекс каталога для живого поиска из шапки (кнопка-лупа).

    Скрытые категории (сезонная рассада вне сезона) в индекс не попадают:
    поиск не должен рекламировать то, что убрано из меню.
    """
    from pages.templatetags.catalog_media import plant_image_thumb_url

    ctx = get_catalog_page_for_template()
    hidden_slugs = {c.get("slug") for c in (ctx.get("categories") or []) if c.get("hidden")}
    plants, _ = get_merged_catalog_plants()
    items = [
        {
            "n": (p.get("title_ru") or p.get("name") or "").strip(),
            "l": (p.get("title_latin") or "").strip(),
            "s": p["slug"],
            "t": (p.get("catalog_teaser") or "").strip(),
            "i": plant_image_thumb_url(p),
        }
        for p in plants
        if p.get("slug") and p.get("category_slug") not in hidden_slugs
    ]
    resp = JsonResponse({"items": items})
    resp["Cache-Control"] = "public, max-age=1800"
    return resp


def catalog_item(request, slug):
    """Один URL /catalog/<slug>/: сначала категория, иначе карточка растения."""
    ctx_base = get_catalog_page_for_template()
    merged_plants, redirects = get_merged_catalog_plants()
    ctx_base["plants"] = merged_plants
    categories = ctx_base.get("categories") or []
    category_slugs = all_catalog_category_slugs(categories)
    if slug in category_slugs:
        ctx = dict(ctx_base)
        ctx["active_category_slug"] = slug
        cat = next((c for c in categories if c.get("slug") == slug), None)
        ctx["category_label"] = category_heading_for_slug(slug, categories)
        ctx["category_hub_links"] = (cat or {}).get("category_hub_links")
        ctx["plants"] = [p for p in merged_plants if plant_belongs_to_category(p, slug)]
        ctx["canonical_path"] = f"/catalog/{slug}/"
        label = ctx["category_label"]
        category_seo = _category_commercial_seo(label, len(ctx["plants"]))
        ctx["seo_title"] = category_seo["seo_title"]
        ctx["og_title"] = f"{label} {CITY_SUFFIX}"
        ctx["meta_description"] = category_seo["meta_description"]
        ctx["jsonld_blocks"] = [
            seo.breadcrumbs_jsonld([
                ("Главная", "/"),
                ("Каталог растений", "/catalog/"),
                (ctx["category_label"], f"/catalog/{slug}/"),
            ])
        ]
        return render(request, "pages/catalog-category.html", enrich_catalog_context(ctx))
    # redirects уже получены выше: не собираем каталог второй раз через resolve_catalog_plant_slug.
    canon = redirects.get(slug, slug)
    plant = find_merged_plant(merged_plants, slug)
    if plant:
        ctx = dict(ctx_base)
        ctx["active_plant_slug"] = canon
        ctx["active_plant"] = plant
        ctx["similar_plants"] = similar_plants_for_detail(plant, merged_plants)
        canonical_path = f"/catalog/{canon}/"
        plant_name = plant.get("catalog_display_name") or plant.get("name") or ""
        ctx["canonical_path"] = canonical_path
        commercial = _plant_commercial_seo(plant)
        ctx["seo_title"] = commercial["seo_title"]
        ctx["plant_h1_suffix"] = commercial["plant_h1_suffix"]
        ctx["og_title"] = f"{plant_name} {CITY_SUFFIX}"
        ctx["meta_description"] = commercial["meta_description"]
        jsonld_blocks = [
            seo.breadcrumbs_jsonld([
                ("Главная", "/"),
                ("Каталог растений", "/catalog/"),
                (plant_name, canonical_path),
            ])
        ]
        product = seo.product_jsonld(plant, canonical_path)
        if product:
            jsonld_blocks.append(product)
        ctx["jsonld_blocks"] = jsonld_blocks
        return render(request, "pages/plant-card.html", enrich_catalog_context(ctx))
    raise Http404("Категория или растение не найдены")


def sluzhba_zaboty(request):
    return render(request, "pages/sluzhba-zaboty.html", SLUZHBA_ZABOTY_PAGE)


def calendar(request):
    ctx = merge_calendar_base(dict(CALENDAR_PAGE))
    ctx["canonical_path"] = "/sluzhba-zaboty/calendar/"
    return render(request, "pages/calendar.html", ctx)


def _calendar_plant_in_category(plant: dict, category_slug: str) -> bool:
    extra = plant.get("category_slugs_all")
    if isinstance(extra, list) and category_slug in extra:
        return True
    return (plant.get("category_slug") or "") == category_slug


def calendar_category(request, category):
    ctx = merge_calendar_base(dict(CALENDAR_PAGE))
    cat = next((c for c in ctx["categories"] if c["slug"] == category), None)
    if not cat:
        raise Http404("Категория не найдена")
    ctx["active_category"] = cat
    ctx["category_plants"] = [p for p in ctx["plants"] if _calendar_plant_in_category(p, category)]
    ctx["canonical_path"] = f"/sluzhba-zaboty/calendar/{category}/"
    ctx["og_title"] = f"Календарь ухода: {cat['label']}"
    return render(request, "pages/calendar-category.html", ctx)


def calendar_plant(request, category, plant):
    ctx = merge_calendar_base(dict(CALENDAR_PAGE))
    p = next((x for x in ctx["plants"] if x["slug"] == plant), None)
    if not p:
        raise Http404("Растение не найдено")
    if not _calendar_plant_in_category(p, category):
        raise Http404("Растение не найдено в этой категории")
    cat = next((c for c in ctx["categories"] if c["slug"] == category), None)
    ctx["active_category"] = cat
    ctx["active_plant"] = p
    ctx["canonical_path"] = f"/sluzhba-zaboty/calendar/{category}/{plant}/"
    ctx["og_title"] = f"Календарь ухода: {p['name']}"
    return render(request, "pages/calendar-plant.html", ctx)


def stati_list(request):
    ctx = dict(STATI_PAGE)
    ctx["articles"] = merged_articles()
    return render(request, "pages/stati.html", ctx)


def stati_detail(request, article_slug):
    # Черновик и запланированная статья доступны только по preview-токену (noindex).
    article, is_preview = find_article(article_slug, request.GET.get("preview", ""))
    if not article:
        raise Http404("Статья не найдена")
    canonical_path = f"/stati/{article_slug}/"
    ctx = dict(STATI_PAGE)
    ctx["articles"] = merged_articles()
    if is_preview:
        ctx["noindex"] = True
    ctx["active_article_slug"] = article_slug
    ctx["article"] = article
    ctx["seo_title"] = article.get("seo_title") or article["title"]
    ctx["og_title"] = article["title"]
    ctx["meta_description"] = article.get("meta_description") or article["excerpt"]
    ctx["canonical_path"] = canonical_path
    if article.get("image_url"):
        ctx["og_image_url"] = article["image_url"]
    elif article.get("image"):
        ctx["og_image"] = article["image"]
    jsonld_blocks = [
        seo.article_jsonld(article, canonical_path),
        seo.breadcrumbs_jsonld([
            ("Главная", "/"),
            ("Статьи", "/stati/"),
            (article["title"], canonical_path),
        ]),
    ]
    if article.get("faq"):
        jsonld_blocks.append(seo.faq_jsonld(article["faq"]))
    ctx["jsonld_blocks"] = jsonld_blocks
    return render(request, "pages/stati-detail.html", ctx)


def o_kompanii(request):
    return render(request, "pages/o-kompanii.html", O_KOMPANII_PAGE)


def kontakty(request):
    ctx = {
        **KONTAKTY_PAGE,
        "yandex_maps_api_key": getattr(settings, "YANDEX_MAPS_API_KEY", ""),
    }
    return render(request, "pages/kontakty.html", ctx)


def privacy(request):
    return render(request, "pages/privacy.html", PRIVACY_PAGE)


def consent(request):
    return render(request, "pages/consent.html", CONSENT_PAGE)


def discount(request):
    return render(request, "pages/discount.html", DISCOUNT_LANDING_PAGE)


def zayavka_direct(request):
    return render(request, "pages/zayavka_direct.html", DIRECT_LANDING_PAGE)


def akciya_hvoynye_50(request):
    """Открытая посадочная акции -50% (промокод САЙТ50), индексируется."""
    return render(request, "pages/promo_sale50.html", PROMO_SALE50_SITE_PAGE)


def direct_50(request):
    """Скрытая посадочная акции -50% (промокод ДИРЕКТ50) для Яндекс.Директа, noindex."""
    return render(request, "pages/promo_sale50.html", PROMO_SALE50_DIRECT_PAGE)


def kottedzhi_direct(request):
    """Скрытая посадочная «Коттеджи директ» для Яндекс.Директа, noindex.

    Доступна только по прямой ссылке из объявления: ссылок с сайта нет,
    в sitemap.xml не попадает, в robots.txt закрыта.
    """
    return render(request, "pages/kottedzhi_direct.html", KOTTEDZHI_DIRECT_PAGE)


def ozelenenie_season_end(request):
    """Скрытая посадочная «Озеленение · финал сезона» под Яндекс.Директ, noindex.

    Живёт только на платном трафике: ссылок с сайта нет, в sitemap.xml не попадает,
    в robots.txt закрыта. Заявка уходит в POST /api/lead/ (pages/landing_leads.py),
    чтобы вместе с контактом сохранились landing_id, UTM и yclid.
    """
    return render(request, "pages/ozelenenie_season_end.html", OZELENENIE_SEASON_END_PAGE)


def predzakaz(request):
    """Лендинг осеннего предзаказа растений (для Яндекс.Директа). Индексируется.

    Контент (тексты и список растений) редактируется из админки:
    модели PreorderSettings / PreorderGroup / PreorderPlant.
    """
    cfg = PreorderSettings.load()

    # Единый список наличия: все активные позиции из всех групп, без разделения
    # на Кирза/Пермь (по просьбе маркетинга, задача Б24 #1323).
    plants = []
    for group in PreorderGroup.objects.filter(is_active=True).prefetch_related("plants"):
        plants.extend(p for p in group.plants.all() if p.is_active)

    canonical = "/predzakaz/"

    # JSON-LD: хлебные крошки + FAQ + каталог предложений (для SEO/GEO).
    faq = [
        {
            "q": "Что такое предзаказ деревьев на осень?",
            "a": "Это бронирование деревьев до начала осенней посадки. "
            "Вы заранее закрепляете нужные позиции и размеры, а поставку получаете осенью - "
            "в лучший срок для приживаемости.",
        },
        {
            "q": "Откуда деревья?",
            "a": "Из питомника «Сибирских газонов» в Новосибирске и проверенных питомников-партнёров. "
            "Хвойные и лиственные крупномеры поставляются с комом и сеткой.",
        },
        {
            "q": "Как оформить заявку?",
            "a": "Отметьте нужные деревья в каталоге, заполните имя и телефон и отправьте заявку. "
            "Менеджер свяжется, уточнит размеры, цену и сроки и подтвердит заказ.",
        },
        {
            "q": "Почему количество ограничено?",
            "a": "Крупномеры в наличии поштучно. На популярные позиции объёмы ограничены, "
            "поэтому бронь работает по принципу «кто раньше оформил заявку».",
        },
    ]

    list_items = []
    for position, p in enumerate(plants, start=1):
        item = {
            "@type": "Product",
            "name": p.name,
            "category": "Деревья",
            "url": seo.absolute(canonical),
            "brand": {"@id": "https://gazony.ru/#organization"},
        }
        if p.size:
            item["description"] = f"{p.name}. {p.size}".strip(". ")
        if p.price:
            item["offers"] = {
                "@type": "Offer",
                "price": str(p.price),
                "priceCurrency": "RUB",
                "availability": "https://schema.org/PreOrder",
                "url": seo.absolute(canonical),
            }
        list_items.append({"@type": "ListItem", "position": position, "item": item})

    offer_catalog = seo.jsonld({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Предзаказ деревьев на осень 2026",
        "numberOfItems": len(list_items),
        "itemListElement": list_items,
    })

    ctx = {
        "brand": "Сибирские газоны",
        "title": cfg.hero_title,
        "seo_title": "Предзаказ деревьев на осень 2026: ели, сосны, берёзы - Сибирские газоны",
        "meta_description": (
            "Предзаказ деревьев на осеннюю посадку 2026: ели, сосны, берёза, липа, рябина, "
            "черёмуха, клён. Крупномеры с комом и сеткой из питомника «Сибирских газонов» "
            "и партнёров в Новосибирске. Количество ограничено, бронируйте заранее."
        ),
        "canonical_path": canonical,
        "og_image": "media/images/pitomnik-product-hvoynye.jpg",
        "form_tag": "predzakaz",
        "cfg": cfg,
        "plants": plants,
        "faq": faq,
        "jsonld_blocks": [
            seo.breadcrumbs_jsonld([
                ("Главная", "/"),
                ("Предзаказ деревьев на осень 2026", canonical),
            ]),
            seo.faq_jsonld(faq),
            offer_catalog,
        ],
    }
    return render(request, "pages/predzakaz.html", ctx)
