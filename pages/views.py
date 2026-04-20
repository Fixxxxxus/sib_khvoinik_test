from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from .catalog_nav import enrich_catalog_context
from .catalog_merge import find_merged_plant, get_merged_catalog_plants, resolve_catalog_plant_slug
from .catalog_products import plant_belongs_to_category, similar_plants_for_detail
from .catalog_subcategories import all_catalog_category_slugs, category_heading_for_slug
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
    CATALOG_PAGE,
    STATI_PAGE,
    KONTAKTY_PAGE,
    PRIVACY_PAGE,
    CONSENT_PAGE,
)


def home(request):
    return render(request, "pages/home.html", HOME_PAGE)


def gazon(request):
    return render(request, "pages/gazon.html", GAZON_PAGE)


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
    return render(request, "pages/catalog.html", enrich_catalog_context(dict(CATALOG_PAGE)))


def catalog_item(request, slug):
    """Один URL /catalog/<slug>/: сначала категория, иначе карточка растения."""
    ctx_base = dict(CATALOG_PAGE)
    merged_plants, _ = get_merged_catalog_plants()
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
        return render(request, "pages/catalog-category.html", enrich_catalog_context(ctx))
    canon = resolve_catalog_plant_slug(slug)
    plant = find_merged_plant(merged_plants, slug)
    if plant:
        ctx = dict(ctx_base)
        ctx["active_plant_slug"] = canon
        ctx["active_plant"] = plant
        ctx["similar_plants"] = similar_plants_for_detail(plant, merged_plants)
        return render(request, "pages/plant-card.html", enrich_catalog_context(ctx))
    raise Http404("Категория или растение не найдены")


def sluzhba_zaboty(request):
    return render(request, "pages/sluzhba-zaboty.html", SLUZHBA_ZABOTY_PAGE)


def calendar(request):
    return render(request, "pages/calendar.html", CALENDAR_PAGE)


def calendar_category(request, category):
    ctx = dict(CALENDAR_PAGE)
    cat = next((c for c in ctx["categories"] if c["slug"] == category), None)
    if not cat:
        raise Http404("Категория не найдена")
    ctx["active_category"] = cat
    ctx["category_plants"] = [
        p for p in ctx["plants"] if p["category_slug"] == category
    ]
    return render(request, "pages/calendar-category.html", ctx)


def calendar_plant(request, category, plant):
    ctx = dict(CALENDAR_PAGE)
    p = next((p for p in ctx["plants"] if p["slug"] == plant), None)
    if not p:
        raise Http404("Растение не найдено")
    cat = next((c for c in ctx["categories"] if c["slug"] == category), None)
    ctx["active_category"] = cat
    ctx["active_plant"] = p
    return render(request, "pages/calendar-plant.html", ctx)


def stati_list(request):
    return render(request, "pages/calendar.html", CALENDAR_PAGE)


def stati_detail(request, article_slug):
    ctx = dict(STATI_PAGE)
    ctx["active_article_slug"] = article_slug
    return render(request, "pages/stati-detail.html", ctx)


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
