"""HTTP-эндпоинты подписки на Службу заботы.

Все три эндпоинта работают через токен в URL (без авторизации):
- POST /api/care/subscribe/         приём формы, создание подписки + лида в Б24
- GET  /care/manage/?t=&s=          страница управления (показать текущие галочки)
- POST /care/manage/                сохранение изменений
- GET  /care/unsubscribe/?t=&s=     one-click отписка (для email List-Unsubscribe и подвалов)
"""

from __future__ import annotations

import hmac as _hmac
import json
import logging
import os
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

_TG_API_SECRET = os.environ.get("TG_API_SECRET", "")
_MAX_WEBHOOK_SECRET = os.environ.get("MAX_WEBHOOK_SECRET", "")

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

# SOURCE_ID лидов в Б24 для каждой подписки на Службу заботы. Значение из справочника
# crm.status.list?filter[ENTITY_ID]=SOURCE на портале sgpichugi.bitrix24.ru.
CARE_LEAD_SOURCE_ID = "UC_OCZ1RE"  # «Подписка Служба заботы»


def _send_welcome_email(sub: CareSubscription) -> None:
    """Сразу после создания подписки шлём первый дайджест по email и пишем DigestDelivery.

    Идемпотентность: если запись уже есть (например, при двойном POST за секунду),
    update_or_create предохранит от дубля. Дальше четверговая рассылка пропустит
    эту подписку для этой недели по unique (subscription, channel, week_key).
    """
    if not sub.email:
        return
    from django.db import IntegrityError, transaction
    from .digest import build_payload, get_current_week_key
    from .models import DigestDelivery
    from .unisender import UnisenderClient
    week_key = get_current_week_key()
    if DigestDelivery.objects.filter(
        subscription=sub, channel="email", week_key=week_key,
        status=DigestDelivery.STATUS_SENT,
    ).exists():
        return
    payload = build_payload(sub, week_key=week_key)
    if payload is None:
        logger.info("welcome email skipped sub=%s: no content for this week", sub.id)
        return
    try:
        res = UnisenderClient().send_digest_email(sub, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning("welcome email failed sub=%s: %s", sub.id, e)
        res = {"ok": False, "error": str(e)}
    status = DigestDelivery.STATUS_SENT if res.get("ok") else DigestDelivery.STATUS_FAILED
    try:
        with transaction.atomic():
            DigestDelivery.objects.update_or_create(
                subscription=sub, channel="email", week_key=week_key,
                defaults={
                    "status": status,
                    "external_id": str(res.get("email_id") or "")[:128],
                    "error": str(res.get("error") or "")[:500],
                },
            )
    except IntegrityError:
        logger.warning("welcome email: DigestDelivery integrity sub=%s wk=%s", sub.id, week_key)
    if status == DigestDelivery.STATUS_SENT:
        CareSubscription.objects.filter(pk=sub.id).update(last_digest_sent_at=timezone.now())


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
            source_id=CARE_LEAD_SOURCE_ID,
        )
        sub.b24_lead_id = lead_id
        sub.save(update_fields=["b24_lead_id", "updated_at"])
    except Bitrix24Error as e:
        # Подписка сохранена локально, лида в Б24 нет: фоновый ретрай-скрипт подберёт.
        logger.warning("subscribe: лид в Б24 не создан, подписка id=%s: %s", sub.id, e)

    # Первое сообщение - сразу письмом через Unisender (подстраховка), даже если основной
    # канал tg/max: api.telegram.org с прод-VDS недоступен, а email доходит всегда. Внутри
    # стоит guard на пустой email, и пишется DigestDelivery, чтобы четверговая рассылка
    # не дублировала. В Telegram/MAX дайджест дойдёт после opt-in (см. tg_optin / max_optin).
    _send_welcome_email(sub)

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

    # Deep-link на TG-бота для подключения, если opt-in ещё не пройден.
    care_tg_bot = os.environ.get("CARE_TELEGRAM_BOT_URL", "https://t.me/sg_customer_care_bot").rstrip("/")
    tg_deep_link = f"{care_tg_bot}?start={sub.token}"

    context = {
        "subscription": sub,
        "groups_meta": CARE_SUBSCRIPTION_GROUPS,
        "channels": CHANNEL_CHOICES,
        "selected_groups": set(sub.groups or []),
        "signature": sub.signed_token(),
        "tg_connected": bool(sub.telegram_chat_id),
        "max_connected": bool(sub.max_chat_id),
        "tg_deep_link": tg_deep_link,
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


# ---------------------------------------------------------------------------
# Telegram API (для GitHub Actions скриптов)
# Авторизация: заголовок X-Api-Secret должен совпадать с env TG_API_SECRET.
# ---------------------------------------------------------------------------

def _tg_auth(request: HttpRequest) -> bool:
    if not _TG_API_SECRET:
        return False
    secret = request.META.get("HTTP_X_API_SECRET", "")
    return _hmac.compare_digest(secret, _TG_API_SECRET)


@csrf_exempt
@require_POST
def tg_optin(request: HttpRequest) -> HttpResponse:
    """Polling-скрипт на Contabo сообщает: пользователь нажал /start <token> в боте.

    Дополнительно: если на этой неделе подписке ещё не отправляли TG-дайджест,
    в ответе возвращаем welcome-payload (text + клавиатура) - бот сразу его пошлёт,
    а через `tg_mark_digest_sent` запишем DigestDelivery.
    Также пишем @username в IM-поле лида в Б24.
    """
    if not _tg_auth(request):
        return HttpResponse("forbidden", status=403)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid JSON")
    token = str(data.get("token") or "").strip()
    chat_id = data.get("telegram_chat_id")
    username = str(data.get("telegram_username") or "").strip()[:64]
    if not token or not chat_id:
        return HttpResponseBadRequest("token and telegram_chat_id required")
    try:
        sub = CareSubscription.objects.get(token=token)
    except CareSubscription.DoesNotExist:
        return JsonResponse({"ok": False, "error": "subscription not found"}, status=404)
    sub.telegram_chat_id = chat_id
    sub.telegram_opted_in_at = timezone.now()
    if not sub.active:
        sub.active = True
        sub.unsubscribed_at = None
    sub.save(update_fields=["telegram_chat_id", "telegram_opted_in_at", "active", "unsubscribed_at", "updated_at"])

    # IM-поле лида в Б24: пишем @username, если он у пользователя задан.
    if username and sub.b24_lead_id:
        try:
            Bitrix24Client().update_lead_messengers(sub.b24_lead_id, telegram=username)
        except Bitrix24Error as e:
            logger.warning("tg_optin: не записал IM в лид %s: %s", sub.b24_lead_id, e)

    # Welcome digest: если на этой неделе ещё не было успешной TG-доставки - собираем payload.
    welcome = None
    from .digest import build_payload, get_current_week_key, render_telegram
    from .models import DigestDelivery
    week_key = get_current_week_key()
    already_sent = DigestDelivery.objects.filter(
        subscription=sub, channel="telegram", week_key=week_key,
        status=DigestDelivery.STATUS_SENT,
    ).exists()
    if not already_sent:
        payload = build_payload(sub, week_key=week_key)
        if payload is not None:
            welcome = {
                "tg_text": render_telegram(payload),
                "manage_url": payload.footer.manage_url,
                "unsub_url": payload.footer.unsubscribe_url,
                "site_url": payload.footer.site_url,
                "week_key": week_key,
            }

    return JsonResponse({
        "ok": True,
        "subscription_id": sub.id,
        "name": sub.name,
        "welcome": welcome,
    })


@csrf_exempt
@require_POST
def tg_unsubscribe(request: HttpRequest) -> HttpResponse:
    """GitHub Actions сообщает: пользователь отписался через бота."""
    if not _tg_auth(request):
        return HttpResponse("forbidden", status=403)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid JSON")
    chat_id = data.get("telegram_chat_id")
    token = str(data.get("token") or "").strip()
    if chat_id:
        sub = CareSubscription.objects.filter(telegram_chat_id=chat_id).first()
    elif token:
        sub = CareSubscription.objects.filter(token=token).first()
    else:
        return HttpResponseBadRequest("telegram_chat_id or token required")
    if not sub:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)
    sub.active = False
    sub.unsubscribed_at = timezone.now()
    sub.save(update_fields=["active", "unsubscribed_at", "updated_at"])
    return JsonResponse({"ok": True, "subscription_id": sub.id})


@require_GET
def tg_pending_digest(request: HttpRequest) -> HttpResponse:
    """GitHub Actions запрашивает список: кому отправить TG-дайджест на этой неделе."""
    if not _tg_auth(request):
        return HttpResponse("forbidden", status=403)
    from .digest import build_payload, get_current_week_key, render_telegram
    from .models import DigestDelivery
    week_key = request.GET.get("week") or get_current_week_key()
    sent_ids = set(
        DigestDelivery.objects.filter(
            channel="telegram", week_key=week_key, status=DigestDelivery.STATUS_SENT
        ).values_list("subscription_id", flat=True)
    )
    subs = CareSubscription.objects.filter(
        active=True, preferred_channel="telegram"
    ).exclude(telegram_chat_id=None).exclude(pk__in=sent_ids)
    items: list[dict] = []
    for sub in subs:
        payload = build_payload(sub, week_key=week_key)
        if payload is None:
            # Нет контента на эту неделю - подписку пропускаем. Запись об
            # этом пишет уже send_weekly_digest. Здесь просто исключаем
            # из списка polling-скрипту.
            continue
        items.append({
            "subscription_id": sub.id,
            "telegram_chat_id": sub.telegram_chat_id,
            "token": sub.token,
            "week_key": week_key,
            "tg_text": render_telegram(payload),
            "manage_url": payload.footer.manage_url,
            "unsub_url": payload.footer.unsubscribe_url,
            "site_url": payload.footer.site_url,
        })
    return JsonResponse({"ok": True, "week_key": week_key, "count": len(items), "items": items})


@csrf_exempt
@require_POST
def tg_mark_digest_sent(request: HttpRequest) -> HttpResponse:
    """GitHub Actions сообщает результаты отправки TG-дайджеста."""
    if not _tg_auth(request):
        return HttpResponse("forbidden", status=403)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid JSON")
    from .models import DigestDelivery
    from django.db import transaction
    results = data.get("results", [])
    created = 0
    for r in results:
        sub_id = r.get("subscription_id")
        week_key = r.get("week_key", "")
        status = r.get("status", DigestDelivery.STATUS_FAILED)
        external_id = str(r.get("external_id") or "")[:128]
        error = str(r.get("error") or "")[:500]
        if not sub_id or not week_key:
            continue
        with transaction.atomic():
            DigestDelivery.objects.update_or_create(
                subscription_id=sub_id, channel="telegram", week_key=week_key,
                defaults={"status": status, "external_id": external_id, "error": error},
            )
        if status == DigestDelivery.STATUS_SENT:
            CareSubscription.objects.filter(pk=sub_id).update(last_digest_sent_at=timezone.now())
        created += 1
    return JsonResponse({"ok": True, "processed": created})


# ---------------------------------------------------------------------------
# MAX Bot webhook (платформа dev.max.ru, прод-аналог Telegram-канала)
#
# В отличие от TG (там polling-скрипт на Contabo гоняет getUpdates), MAX
# сам шлёт нам POST на этот URL. Авторизация - через секретный сегмент в
# самом URL (`/api/care/max/webhook/<SECRET>/`), сверяется с env
# MAX_WEBHOOK_SECRET. Это рекомендованный паттерн MAX (как и Telegram
# secret_token, только в path, потому что у MAX свой формат заголовков).
#
# Поведение:
#   /start <token>          -> opt-in: пишем max_chat_id+max_opted_in_at,
#                              шлём welcome-дайджест если на эту неделю
#                              ещё не было успешной MAX-доставки.
#   /unsubscribe            -> отписка (active=False) + подтверждение.
#   callback `unsub:<tok>`  -> то же, что /unsubscribe.
#   всё остальное           -> вежливая отбивка со ссылкой на сайт.
# ---------------------------------------------------------------------------


def _max_send_welcome_digest(sub: CareSubscription) -> None:
    """Если на этой неделе ещё не было успешной MAX-доставки, шлём дайджест.

    По аналогии с _send_welcome_email и tg_optin.welcome - чтобы пользователь
    сразу после /start получил первый выпуск, а не ждал четверга.
    """
    from django.db import IntegrityError, transaction
    from .digest import build_payload, get_current_week_key
    from .max_bot import MaxBotClient
    from .models import DigestDelivery

    week_key = get_current_week_key()
    if DigestDelivery.objects.filter(
        subscription=sub, channel="max", week_key=week_key,
        status=DigestDelivery.STATUS_SENT,
    ).exists():
        return
    payload = build_payload(sub, week_key=week_key)
    if payload is None:
        logger.info("max welcome skipped sub=%s: no content for this week", sub.id)
        return
    try:
        res = MaxBotClient().send_digest(sub, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning("max welcome failed sub=%s: %s", sub.id, e)
        res = {"ok": False, "error": str(e)}
    status = DigestDelivery.STATUS_SENT if res.get("ok") else DigestDelivery.STATUS_FAILED
    try:
        with transaction.atomic():
            DigestDelivery.objects.update_or_create(
                subscription=sub, channel="max", week_key=week_key,
                defaults={
                    "status": status,
                    "external_id": str(res.get("message_id") or "")[:128],
                    "error": str(res.get("error") or "")[:500],
                },
            )
    except IntegrityError:
        logger.warning("max welcome: DigestDelivery integrity sub=%s wk=%s", sub.id, week_key)
    if status == DigestDelivery.STATUS_SENT:
        CareSubscription.objects.filter(pk=sub.id).update(last_digest_sent_at=timezone.now())


def _max_handle_start(text: str, chat_id: int | str) -> tuple[CareSubscription | None, str]:
    """Парсит `/start <token>`, делает opt-in. Возвращает (subscription, reply_text)."""
    parts = (text or "").split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    if not token:
        return None, (
            "Привет! Чтобы подписаться на дайджест Сибирских Газонов, "
            "вернитесь на сайт и нажмите «Открыть бот в MAX» после оформления подписки."
        )
    try:
        sub = CareSubscription.objects.get(token=token)
    except CareSubscription.DoesNotExist:
        return None, (
            "Не удалось найти вашу подписку по этой ссылке. "
            "Попробуйте оформить её заново на сайте gazony.ru."
        )
    sub.max_chat_id = int(chat_id) if str(chat_id).lstrip("-").isdigit() else None
    if sub.max_chat_id is None:
        # MAX может присылать строковые chat_id (UUID-подобные): храним в отдельной
        # колонке нельзя - схема BigInt. Если не парсится - сохранять смысла нет.
        logger.warning("max optin: chat_id=%r не приводится к int, sub=%s", chat_id, sub.id)
        return sub, (
            "Подписка найдена, но MAX вернул нестандартный идентификатор чата. "
            "Мы уже разбираемся, скоро напишем."
        )
    sub.max_opted_in_at = timezone.now()
    if not sub.active:
        sub.active = True
        sub.unsubscribed_at = None
    sub.save(update_fields=[
        "max_chat_id", "max_opted_in_at", "active", "unsubscribed_at", "updated_at",
    ])
    return sub, (
        f"Привет, {sub.name or 'друг'}! Подписка на дайджест Службы заботы подключена. "
        "Каждый четверг здесь будут краткие задачи сезона. Чтобы отписаться - "
        "команда /unsubscribe."
    )


def _max_deactivate(sub: CareSubscription) -> str:
    if sub.active:
        sub.active = False
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["active", "unsubscribed_at", "updated_at"])
    return (
        "Подписка отключена. Если передумаете - оформите её заново на gazony.ru "
        "в разделе «Служба заботы»."
    )


@csrf_exempt
@require_POST
def max_webhook(request: HttpRequest, secret: str) -> HttpResponse:
    """Webhook MAX Bot API. URL: /api/care/max/webhook/<MAX_WEBHOOK_SECRET>/."""
    if not _MAX_WEBHOOK_SECRET or not _hmac.compare_digest(secret, _MAX_WEBHOOK_SECRET):
        return HttpResponse("forbidden", status=403)
    try:
        update = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest("invalid JSON")
    if not isinstance(update, dict):
        return HttpResponseBadRequest("update must be object")

    # MAX-обновление приходит с полем update_type. Поддерживаем три типа:
    # - message_created / bot_started (текст /start, /unsubscribe, прочее)
    # - message_callback (нажатие inline-кнопки)
    # В документации формат немного плавающий, поэтому достаём поля защитно.
    from .max_bot import MaxBotClient

    update_type = update.get("update_type") or update.get("type") or ""
    bot = MaxBotClient()

    if update_type == "message_callback" or "callback" in update:
        cb = update.get("callback") or {}
        callback_id = cb.get("callback_id") or cb.get("id") or ""
        payload_str = cb.get("payload") or ""
        user = cb.get("user") or {}
        chat_id = (
            cb.get("chat_id")
            or (update.get("message") or {}).get("recipient", {}).get("chat_id")
            or user.get("user_id")
        )
        if payload_str.startswith("unsub:"):
            token = payload_str.split(":", 1)[1].strip()
            sub = CareSubscription.objects.filter(token=token).first()
            if sub:
                reply = _max_deactivate(sub)
            else:
                reply = "Не нашли подписку по этой ссылке."
            if chat_id:
                bot.send_message(chat_id=chat_id, text=reply)
            if callback_id:
                bot.answer_callback(callback_id=callback_id, text="Готово")
        else:
            if callback_id:
                bot.answer_callback(callback_id=callback_id)
        return JsonResponse({"ok": True})

    # message_created / bot_started: текст из message.body.text
    msg = update.get("message") or {}
    body = msg.get("body") or {}
    text = (body.get("text") or msg.get("text") or "").strip()
    sender = msg.get("sender") or update.get("user") or {}
    recipient = msg.get("recipient") or {}
    chat_id = (
        recipient.get("chat_id")
        or msg.get("chat_id")
        or sender.get("user_id")
        or update.get("chat_id")
    )

    if not chat_id:
        # MAX иногда шлёт служебные апдейты без чата - подтверждаем приём, но
        # ничего не делаем.
        return JsonResponse({"ok": True, "skipped": "no chat_id"})

    low = text.lower()
    if low.startswith("/start"):
        sub, reply = _max_handle_start(text, chat_id)
        bot.send_message(chat_id=chat_id, text=reply)
        if sub and sub.max_chat_id and sub.active:
            _max_send_welcome_digest(sub)
        return JsonResponse({"ok": True})
    if low.startswith("/unsubscribe"):
        sub = CareSubscription.objects.filter(max_chat_id=chat_id).first()
        if sub:
            reply = _max_deactivate(sub)
        else:
            reply = (
                "Не нашли активной подписки на этот чат. Если оформляли подписку, "
                "сначала нажмите /start с вашей персональной ссылкой с сайта."
            )
        bot.send_message(chat_id=chat_id, text=reply)
        return JsonResponse({"ok": True})

    # Любой другой ввод - подсказка вернуться на сайт.
    bot.send_message(
        chat_id=chat_id,
        text=(
            "Чтобы подписаться или изменить настройки, перейдите на сайт gazony.ru "
            "и оформите подписку в разделе «Служба заботы»."
        ),
    )
    return JsonResponse({"ok": True})
