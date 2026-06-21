from django.urls import path, re_path
from django.views.generic import RedirectView

from . import loyalty, seo, views

urlpatterns = [
    path("api/loyalty/card/", loyalty.loyalty_card, name="loyalty_card"),
    # SEO/GEO-инфраструктура: всё через Django, не через docs/ (конвенция проекта).
    path("robots.txt", seo.robots_txt, name="robots_txt"),
    path("sitemap.xml", seo.sitemap_xml, name="sitemap_xml"),
    path("llms.txt", seo.llms_txt, name="llms_txt"),
    path(f"{seo.INDEXNOW_KEY}.txt", seo.indexnow_key, name="indexnow_key"),
    # 301 со структуры старого сайта: эти URL до сих пор в индексе и в выдаче AI.
    path("company/", RedirectView.as_view(url="/o-kompanii/", permanent=True)),
    path(
        "services/ustroystvo-gazonov/",
        RedirectView.as_view(url="/gazon/", permanent=True),
    ),
    re_path(
        r"^services/.*$",
        RedirectView.as_view(url="/ozelenenie-b2c/", permanent=True),
    ),
    re_path(r"^advice/.*$", RedirectView.as_view(url="/stati/", permanent=True)),
    path("", views.home, name="home"),
    path("gazon/", views.gazon, name="gazon"),
    path("prais-rulonnyy-gazon/", views.roll_lawn_price, name="roll_lawn_price"),
    path("ozelenenie-b2c/", views.ozelenenie_b2c, name="ozelenenie_b2c"),
    path("b2b/", views.b2b, name="b2b"),
    path("pitomnik/", views.pitomnik, name="pitomnik"),
    path("sadovye-centry/", views.sadovye_centry, name="sadovye_centry"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<slug:slug>/", views.catalog_item, name="catalog_item"),
    path("sluzhba-zaboty/", views.sluzhba_zaboty, name="sluzhba_zaboty"),
    path("sluzhba-zaboty/calendar/", views.calendar, name="calendar"),
    path("sluzhba-zaboty/calendar/<slug:category>/", views.calendar_category, name="calendar_category"),
    path("sluzhba-zaboty/calendar/<slug:category>/<slug:plant>/", views.calendar_plant, name="calendar_plant"),
    path("stati/", views.stati_list, name="stati_list"),
    path("stati/<slug:article_slug>/", views.stati_detail, name="stati_detail"),
    path("kontakty/", views.kontakty, name="kontakty"),
    path("o-kompanii/", views.o_kompanii, name="o_kompanii"),
    path("privacy/", views.privacy, name="privacy"),
    path("consent/", views.consent, name="consent"),
    path("discount/", views.discount, name="discount"),
    path("zayavka-direct/", views.zayavka_direct, name="zayavka_direct"),
    path("predzakaz/", views.predzakaz, name="predzakaz"),
]
