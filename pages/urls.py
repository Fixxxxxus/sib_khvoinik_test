from django.urls import path

from . import views

urlpatterns = [
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
    path("privacy/", views.privacy, name="privacy"),
    path("consent/", views.consent, name="consent"),
    path("discount/", views.discount, name="discount"),
    path("zayavka-direct/", views.zayavka_direct, name="zayavka_direct"),
    path(
        "zen_jDi0ZH49k0vmHeorZ1xcU5gIWQNlXwyyxsQUHxOSy1nVFiG9WoWTbkJ9i53sk1KV.html",
        views.zen_verification,
        name="zen_verification",
    ),
]
