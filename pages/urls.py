from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("gazon/", views.gazon, name="gazon"),
    path("ozelenenie-b2c/", views.ozelenenie_b2c, name="ozelenenie_b2c"),
    path("b2b/", views.b2b, name="b2b"),
    path("pitomnik/", views.pitomnik, name="pitomnik"),
    path("sadovye-centry/", views.sadovye_centry, name="sadovye_centry"),
    path("katalog/", views.katalog, name="katalog"),
    path("katalog/<slug:category_slug>/", views.katalog_category, name="katalog_category"),
    path("katalog/<slug:plant_slug>/", views.plant_card, name="plant_card"),
    path("sluzhba-zaboty/", views.sluzhba_zaboty, name="sluzhba_zaboty"),
    path("stati/", views.stati_list, name="stati_list"),
    path("stati/<slug:article_slug>/", views.stati_detail, name="stati_detail"),
    path("kontakty/", views.kontakty, name="kontakty"),
]

