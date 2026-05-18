from django.urls import path

from . import views


app_name = "care_notifications"

urlpatterns = [
    path("api/care/subscribe/", views.subscribe, name="subscribe"),
    path("care/manage/", views.manage, name="manage"),
    path("care/unsubscribe/", views.unsubscribe, name="unsubscribe"),
]
