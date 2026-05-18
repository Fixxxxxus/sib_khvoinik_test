from django.urls import path

from . import views


app_name = "care_notifications"

urlpatterns = [
    path("api/care/subscribe/", views.subscribe, name="subscribe"),
    path("care/manage/", views.manage, name="manage"),
    path("care/unsubscribe/", views.unsubscribe, name="unsubscribe"),
    # Telegram API для GitHub Actions (защищены X-Api-Secret)
    path("api/care/tg/optin/", views.tg_optin, name="tg_optin"),
    path("api/care/tg/unsubscribe/", views.tg_unsubscribe, name="tg_unsubscribe"),
    path("api/care/tg/pending-digest/", views.tg_pending_digest, name="tg_pending_digest"),
    path("api/care/tg/mark-digest-sent/", views.tg_mark_digest_sent, name="tg_mark_digest_sent"),
]
