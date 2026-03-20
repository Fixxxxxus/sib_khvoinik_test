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


def katalog_category(request, category_slug):
    ctx = dict(KATALOG_PAGE)
    ctx["active_category_slug"] = category_slug
    # Filter plants for the selected category (stage 1: UI-only data)
    ctx["plants"] = [
        p for p in ctx.get("plants", []) if p.get("category_slug") == category_slug
    ]
    return render(request, "pages/katalog-category.html", ctx)


def plant_card(request, plant_slug):
    ctx = dict(KATALOG_PAGE)
    ctx["active_plant_slug"] = plant_slug
    ctx["active_plant"] = next(
        (p for p in ctx.get("plants", []) if p.get("slug") == plant_slug),
        None,
    )
    return render(request, "pages/plant-card.html", ctx)


def sluzhba_zaboty(request):
    return render(request, "pages/sluzhba-zaboty.html", SLUZHBA_ZABOTY_PAGE)


def stati_list(request):
    return render(request, "pages/stati.html", STATI_PAGE)


def stati_detail(request, article_slug):
    ctx = dict(STATI_PAGE)
    ctx["active_article_slug"] = article_slug
    return render(request, "pages/stati-detail.html", ctx)


def kontakty(request):
    return render(request, "pages/kontakty.html", KONTAKTY_PAGE)

