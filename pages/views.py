from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from .data import (
    HOME_PAGE,
    GAZON_PAGE,
    OZELENENIE_B2C_PAGE,
    B2B_PAGE,
    PITOMNIK_PAGE,
    SADOVYE_CENTRY_PAGE,
    SLUZHBA_ZABOTY_PAGE,
    KATALOG_PAGE,
    STATI_PAGE,
    KONTAKTY_PAGE,
    PRIVACY_PAGE,
    CONSENT_PAGE,
)


def home(request):
    return render(request, "pages/home.html", HOME_PAGE)


def gazon(request):
    return render(request, "pages/gazon.html", GAZON_PAGE)


def ozelenenie_b2c(request):
    return render(request, "pages/ozelenenie-b2c.html", OZELENENIE_B2C_PAGE)


def b2b(request):
    return render(request, "pages/b2b.html", B2B_PAGE)


def pitomnik(request):
    return render(request, "pages/pitomnik.html", PITOMNIK_PAGE)


def sadovye_centry(request):
    return render(request, "pages/sadovye-centry.html", SADOVYE_CENTRY_PAGE)


def katalog(request):
    return render(request, "pages/katalog.html", KATALOG_PAGE)


def katalog_item(request, slug):
    """Один URL /katalog/<slug>/: сначала категория, иначе карточка растения."""
    ctx_base = dict(KATALOG_PAGE)
    category_slugs = {c["slug"] for c in ctx_base.get("categories", [])}
    if slug in category_slugs:
        ctx = dict(ctx_base)
        ctx["active_category_slug"] = slug
        cat = next((c for c in ctx_base.get("categories", []) if c["slug"] == slug), None)
        ctx["category_label"] = cat["label"] if cat else slug
        ctx["plants"] = [
            p for p in ctx.get("plants", []) if p.get("category_slug") == slug
        ]
        return render(request, "pages/katalog-category.html", ctx)
    plant = next((p for p in ctx_base.get("plants", []) if p.get("slug") == slug), None)
    if plant:
        ctx = dict(ctx_base)
        ctx["active_plant_slug"] = slug
        ctx["active_plant"] = plant
        return render(request, "pages/plant-card.html", ctx)
    raise Http404("Категория или растение не найдены")


def sluzhba_zaboty(request):
    return render(request, "pages/sluzhba-zaboty.html", SLUZHBA_ZABOTY_PAGE)


def stati_list(request):
    return render(request, "pages/stati.html", STATI_PAGE)


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

