from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from .catalog_context import get_catalog_page_for_template
from .catalog_nav import enrich_catalog_context
from .catalog_merge import find_merged_plant, get_merged_catalog_plants
from .catalog_products import plant_belongs_to_category, similar_plants_for_detail
from .catalog_subcategories import all_catalog_category_slugs, category_heading_for_slug
from .calendar_live import merge_calendar_base
from . import seo
from .data import (
    HOME_PAGE,
    GAZON_PAGE,
    ROLL_LAWN_PRICE_PAGE,
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
)


def home(request):
    return render(request, "pages/home.html", HOME_PAGE)


def gazon(request):
    ctx = dict(GAZON_PAGE)
    ctx["jsonld_blocks"] = [seo.faq_jsonld(GAZON_PAGE["faq"])]
    return render(request, "pages/gazon.html", ctx)


def roll_lawn_price(request):
    """Прайс рулонного газона — пункт «Рулонные газоны» в боковом меню каталога."""
    ctx = dict(ROLL_LAWN_PRICE_PAGE)
    ctx["active_catalog_nav_route"] = "roll_lawn_price"
    return render(request, "pages/roll-lawn-price.html", enrich_catalog_context(ctx))


def ozelenenie_b2c(request):
    return render(request, "pages/ozelenenie-b2c.html", OZELENENIE_B2C_PAGE)


def b2b(request):
    return render(request, "pages/b2b.html", B2B_PAGE)


def pitomnik(request):
    return render(request, "pages/pitomnik.html", PITOMNIK_PAGE)


def sadovye_centry(request):
    return render(request, "pages/sadovye-centry.html", SADOVYE_CENTRY_PAGE)


def catalog(request):
    return render(request, "pages/catalog.html", enrich_catalog_context(get_catalog_page_for_template()))


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
        ctx["og_title"] = f"{ctx['category_label']}: каталог питомника"
        ctx["meta_description"] = (
            f"{ctx['category_label']} в каталоге питомника «Сибирские газоны»: "
            "цены, наличие и описания растений, выращенных и адаптированных для Сибири."
        )
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
        ctx["og_title"] = plant_name
        description = (plant.get("description") or "").strip()
        if description:
            ctx["meta_description"] = (
                description[:157] + "…" if len(description) > 160 else description
            )
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
    return render(request, "pages/stati.html", dict(STATI_PAGE))


def stati_detail(request, article_slug):
    article = next(
        (a for a in STATI_PAGE["articles"] if a["slug"] == article_slug), None
    )
    if not article:
        raise Http404("Статья не найдена")
    canonical_path = f"/stati/{article_slug}/"
    ctx = dict(STATI_PAGE)
    ctx["active_article_slug"] = article_slug
    ctx["article"] = article
    ctx["seo_title"] = article["title"]
    ctx["og_title"] = article["title"]
    ctx["meta_description"] = article["excerpt"]
    ctx["canonical_path"] = canonical_path
    if article.get("image"):
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
