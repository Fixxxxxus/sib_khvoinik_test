"""HTTP-эндпоинты подписки на Службу заботы.

Все три эндпоинта работают через токен в URL (без авторизации):
- POST /api/care/subscribe/         приём формы, создание подписки + лида в Б24
- GET  /care/manage/?t=&s=          страница управления (показать текущие галочки)
- POST /care/manage/                сохранение изменений
- GET  /care/unsubscribe/?t=&s=     one-click отписка (для email List-Unsubscribe и подвалов)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from pages.data import (
    B24_CARE_SUBSCRIPTIONS_LEAD_FIELD,
    CARE_SUBSCRIPTION_GROUPS,
)

from .bitrix24 import Bitrix24Client, Bitrix24Error
from .models import CHANNEL_CHOICES, SOURCE_CHOICES, CareSubscription


logger = logging.getLogger(__name__)


_VALID_CHANNELS = {code for code, _ in CHANNEL_CHOICES}
_VALID_SOURCES = {code for code, _ in SOURCE_CHOICES}
_GROUP_SLUGS = {g["slug"] for g in CARE_SUBSCRIPTION_GROUPS}
_FORM_FIELD_TO_SLUG = {g["form_field"]: g["slug"] for g in CARE_SUBSCRIPTION_GROUPS}
_SLUG_TO_B24_LABEL = {g["slug"]: g["b24_label"] for g in CARE_SUBSCRIPTION_GROUPS}


def _origin_allowed(request: HttpRequest) -> bool:
    """Простая защита от CSRF без токенов: принимаем только same-origin POST.

    На проде ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS уже задают круг доменов; мы
    дополнительно сверяем Origin/Referer запроса. Этого достаточно для MVP.
    """
    if settings.DEBUG:
        return True
    origin = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER") or ""
    allowed = set(settings.CSRF_TRUSTED_ORIGINS or [])
    return any(origin.startswith(o) for o in allowed)


def _extract_groups_from_payload(payload: dict[str, Any]) -> list[str]:
    """Из {'care_seasonal': '1', 'care_roses': '1', ...} в ['seasonal','roses']."""
    out: list[str] = []
    for form_field, slug in _FORM_FIELD_TO_SLUG.items():
        v = payload.get(form_field)
        if str(v).strip() in ("1", "true", "True", "on"):
            out.append(slug)
    return out


def _slug_list_to_b24_labels(slugs: list[str]) -> list[str]:
    return [_SLUG_TO_B24_LABEL[s] for s in slugs if s in _SLUG_TO_B24_LABEL]


@csrf_exempt
@require_POST
def subscribe(request: HttpRequest) -> HttpResponse:
    if not _origin_allowed(request):
        return HttpResponseBadRequest("origin not allowed")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest("invalid JSON body")
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("payload must be an object")

    name = (payload.get("name") or "").strip()[:200]
    phone = (payload.get("phone") or "").strip()[:32]
    email = (payload.get("email") or "").strip()[:200]
    channel = (payload.get("preferred_messenger") or payload.get("preferred_channel") or "email").strip()
    if channel not in _VALID_CHANNELS:
        channel = "email"
    if not name or not phone:
        return HttpResponseBadRequest("name and phone are required")

    groups = _extract_groups_from_payload(payload)
    promo = str(payload.get("promo") or "").strip() in ("1", "true", "True", "on")

    source = (payload.get("source") or "unknown").strip()
    if source not in _VALID_SOURCES:
        source = "unknown"
    page_path = (payload.get("pagePath") or payload.get("page_path") or "")[:512]
    utm = payload.get("utm") if isinstance(payload.get("utm"), dict) else {}

    sub = CareSubscription.objects.create(
        name=name,
        phone=phone,
        email=email,
        preferred_channel=channel,
        groups=groups,
        promo_subscribed=promo,
        source=source,
        page_path=page_path,
        utm=utm,
    )

    b24_labels = _slug_list_to_b24_labels(groups)
    lead_title = "Подписка на Службу заботы"
    comments_lines = [f"Канал связи: {channel}"]
    if groups:
        comments_lines.append("Подписка на: " + ", ".join(b24_labels))
    if promo:
        comments_lines.append("Согласие на новинки и акции: да")
    if page_path:
        comments_lines.append(f"Страница: {page_path}")
    comments = "\n".join(comments_lines)

    extra_fields: dict[str, Any] = {}
    client = Bitrix24Client()
    try:
        ids = client.get_multiselect_value_ids(
            B24_CARE_SUBSCRIPTIONS_LEAD_FIELD, b24_labels, entity="lead"
        )
        if ids:
            extra_fields[B24_CARE_SUBSCRIPTIONS_LEAD_FIELD] = ids
        lead_id = client.create_lead(
            title=lead_title,
            name=name,
            phone=phone,
            email=email,
            comments=comments,
            extra_fields=extra_fields,
        )
        sub.b24_lead_id = lead_id
        sub.save(update_fields=["b24_lead_id", "updated_at"])
    except Bitrix24Error as e:
        # Подписка сохранена локально, лида в Б24 нет: фоновый ретрай-скрипт подберёт.
        logger.warning("subscribe: лид в Б24 не создан, подписка id=%s: %s", sub.id, e)

    return JsonResponse(
        {
            "ok": True,
            "id": sub.id,
            "token": sub.token,
            "signature": sub.signed_token(),
            "b24_lead_id": sub.b24_lead_id,
        },
        status=201,
    )


def _load_subscription_by_signed_token(request: HttpRequest) -> CareSubscription | None:
    token = request.GET.get("t") or request.POST.get("t") or ""
    signature = request.GET.get("s") or request.POST.get("s") or ""
    if not token or not signature:
        return None
    return CareSubscription.verify_signed_token(token, signature)


@require_http_methods(["GET", "POST"])
def manage(request: HttpRequest) -> HttpResponse:
    sub = _load_subscription_by_signed_token(request)
    if sub is None:
        return render(request, "care_notifications/manage_invalid.html", status=404)

    if request.method == "POST":
        groups = [
            s for s in _GROUP_SLUGS
            if str(request.POST.get(f"care_{s}", "")) in ("1", "true", "on")
        ]
        sub.groups = sorted(groups)
        sub.promo_subscribed = str(request.POST.get("promo", "")) in ("1", "true", "on")
        new_channel = request.POST.get("preferred_channel", sub.preferred_channel)
        if new_channel in _VALID_CHANNELS:
            sub.preferred_channel = new_channel
        sub.save(
            update_fields=[
                "groups",
                "promo_subscribed",
                "preferred_channel",
                "updated_at",
            ]
        )

    context = {
        "subscription": sub,
        "groups_meta": CARE_SUBSCRIPTION_GROUPS,
        "channels": CHANNEL_CHOICES,
        "selected_groups": set(sub.groups or []),
        "signature": sub.signed_token(),
    }
    return render(request, "care_notifications/manage.html", context)


@require_http_methods(["GET", "POST"])
def unsubscribe(request: HttpRequest) -> HttpResponse:
    sub = _load_subscription_by_signed_token(request)
    if sub is None:
        return render(request, "care_notifications/manage_invalid.html", status=404)

    if sub.active:
        sub.active = False
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["active", "unsubscribed_at", "updated_at"])

    return render(
        request,
        "care_notifications/unsubscribed.html",
        {"subscription": sub},
    )
