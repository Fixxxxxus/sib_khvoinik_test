"""Приём заявок с рекламных посадочных: POST /api/lead/ и GET /api/health/.

Отдельный эндпоинт (а не общая система форм сайта) нужен посадочным под Яндекс.Директ:
вместе с именем и телефоном мы обязаны сохранить landing_id, UTM-метки и yclid, иначе
медиабайер не сведёт заявки с кампаниями и объявлениями.

Порядок работы:
1. Валидируем тело по ТЗ (согласие, телефон к 11 цифрам с 7, имя от 2 символов).
2. Пишем лид в БД (модель LandingLead) - это основное хранилище.
3. Best-effort отправляем лид в Битрикс24 и уведомление менеджеру в Telegram.
   Сбой любого из этих шагов не меняет ответ: заявка уже сохранена, теряем
   оплаченный клик только если соврать пользователю про ошибку.
"""

from __future__ import annotations

import json
import logging
import os
from uuid import uuid4

from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from care_notifications.bitrix24 import Bitrix24Client, Bitrix24Error
from care_notifications.telegram_bot import TelegramBotClient

from .data import LANDING_OZELENENIE_SEASON_END_ID
from .loyalty import _client_ip, _is_rate_limited
from .models import LandingLead

logger = logging.getLogger(__name__)

# Единственная посадочная на этом эндпоинте. Список, а не одна строка: следующие
# лендинги добавляются сюда и сразу получают отдельную воронку по landing_id.
LANDING_TITLES = {
    LANDING_OZELENENIE_SEASON_END_ID: "Директ: Озеленение · финал сезона",
}
DEFAULT_LANDING_ID = LANDING_OZELENENIE_SEASON_END_ID

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# Chat id менеджера для алертов о заявках. Отдельная переменная, чтобы заявки
# с рекламы не смешивались с промо-модерацией Службы заботы; если её не задали,
# падаем обратно на chat id администратора промо.
TG_CHAT_ID_ENV = "LANDING_LEAD_TG_CHAT_ID"
TG_CHAT_ID_FALLBACK_ENV = "CARE_PROMO_ADMIN_CHAT_ID"


def _tg_chat_id() -> str:
    chat_id = os.environ.get(TG_CHAT_ID_ENV, "").strip()
    if chat_id:
        return chat_id
    return os.environ.get(TG_CHAT_ID_FALLBACK_ENV, "").strip()


def normalize_phone(raw: str) -> str:
    """Приводит телефон к 11 цифрам, начинающимся с 7. Пустая строка - не вышло.

    Принимаем то, что реально набирают в форме: +7..., 8..., 9... и любой мусор
    из скобок, пробелов и дефисов.
    """
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "7" + digits
    return ""


def format_phone(normalized: str) -> str:
    """7XXXXXXXXXX -> +7 (XXX) XXX-XX-XX для человеко-читаемых сообщений."""
    if len(normalized) != 11:
        return normalized
    return (
        f"+7 ({normalized[1:4]}) {normalized[4:7]}-"
        f"{normalized[7:9]}-{normalized[9:11]}"
    )


def _utm_from_payload(payload: dict) -> dict:
    utm = payload.get("utm")
    if not isinstance(utm, dict):
        utm = {}
    values = {key: str(utm.get(key) or "").strip()[:300] for key in UTM_KEYS}
    values["yclid"] = str(utm.get("yclid") or payload.get("yclid") or "").strip()[:100]
    return values


def _utm_line(utm: dict) -> str:
    parts = [f"{key}={utm[key]}" for key in (*UTM_KEYS, "yclid") if utm.get(key)]
    return "; ".join(parts) if parts else "нет меток"


def _b24_comments(lead: LandingLead, utm: dict) -> str:
    lines = [
        f"Заявка с посадочной: {lead.landing_id}",
        f"Услуга: {lead.service_label}",
        f"Объём: {lead.area_label}",
        f"lead_id: {lead.lead_id}",
        f"Источник: {lead.source}",
        f"UTM: {_utm_line(utm)}",
        f"landing_url: {lead.landing_url or lead.page_path}",
        f"referrer: {lead.referrer or 'нет'}",
    ]
    if lead.comment:
        lines.append(f"Комментарий: {lead.comment}")
    return "\n".join(lines)


def _send_to_bitrix(lead: LandingLead, utm: dict) -> None:
    """Создаёт лид в Б24. Ошибки только логируем: заявка уже в БД."""
    title = LANDING_TITLES.get(lead.landing_id, f"Директ: {lead.landing_id}")
    try:
        b24_id = Bitrix24Client().create_lead(
            title=title,
            name=lead.name,
            phone=format_phone(lead.phone),
            comments=_b24_comments(lead, utm),
            source_id="WEB",
            extra_fields={"SOURCE_DESCRIPTION": f"{lead.landing_id} | {_utm_line(utm)}"[:255]},
        )
    except Bitrix24Error as e:
        logger.warning("landing_lead %s: Bitrix24 недоступен: %s", lead.lead_id, e)
        return
    except Exception:  # noqa: BLE001 - Б24 не должен ронять приём заявки
        logger.exception("landing_lead %s: неожиданная ошибка Bitrix24", lead.lead_id)
        return
    LandingLead.objects.filter(pk=lead.pk).update(b24_lead_id=b24_id)
    lead.b24_lead_id = b24_id


def build_telegram_text(lead: LandingLead, utm: dict) -> str:
    """Текст алерта менеджеру. Формат строк зафиксирован в ТЗ (§6.6)."""
    return "\n".join(
        [
            f"Заявка: {lead.landing_id}",
            f"Имя: {lead.name}",
            f"Телефон: {format_phone(lead.phone)}",
            f"Услуга: {lead.service_label}",
            f"Объём: {lead.area_label}",
            f"lead_id: {lead.lead_id}",
            f"landing_url: {lead.landing_url or lead.page_path}",
            f"UTM: {_utm_line(utm)}",
        ]
    )


def _notify_telegram(lead: LandingLead, utm: dict) -> None:
    """Best-effort уведомление менеджеру: без токена или chat id просто молчим."""
    chat_id = _tg_chat_id()
    if not chat_id:
        logger.info("landing_lead %s: %s не задан, Telegram-алерт пропущен", lead.lead_id, TG_CHAT_ID_ENV)
        return
    bot = TelegramBotClient()
    if not bot.token:
        logger.info("landing_lead %s: TELEGRAM_BOT_TOKEN не задан, алерт пропущен", lead.lead_id)
        return
    try:
        res = bot.send_message(int(chat_id), build_telegram_text(lead, utm), parse_mode="")
    except (ValueError, TypeError):
        logger.warning("landing_lead %s: некорректный chat id %r", lead.lead_id, chat_id)
        return
    except Exception:  # noqa: BLE001 - Telegram не должен ронять приём заявки
        logger.exception("landing_lead %s: неожиданная ошибка Telegram", lead.lead_id)
        return
    if not res.get("ok"):
        logger.warning("landing_lead %s: Telegram не принял алерт: %s", lead.lead_id, res.get("error"))


@csrf_exempt
@require_POST
def landing_lead(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """POST /api/lead/ - приём заявки с рекламной посадочной."""
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid json")
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("invalid json")

    # Honeypot: поле скрыто от людей, заполняют его только боты. Отвечаем ok,
    # чтобы бот не подбирал обход, но ничего не сохраняем и никого не будим.
    if str(payload.get("company_site") or "").strip():
        logger.info("landing_lead: honeypot сработал, IP %s", _client_ip(request))
        return JsonResponse({"ok": True, "lead_id": uuid4().hex[:16]})

    name = str(payload.get("name") or "").strip()
    phone = normalize_phone(payload.get("phone"))

    if payload.get("consent") is not True:
        return JsonResponse(
            {"ok": False, "error": "Нужно согласие на обработку персональных данных.", "field": "consent"},
            status=400,
        )
    if len(name) < 2:
        return JsonResponse(
            {"ok": False, "error": "Укажите имя, минимум 2 символа.", "field": "name"},
            status=400,
        )
    if not phone:
        return JsonResponse(
            {"ok": False, "error": "Проверьте номер телефона: нужен российский номер из 11 цифр.", "field": "phone"},
            status=400,
        )

    if _is_rate_limited(request):
        logger.warning("landing_lead: rate limit для IP %s", _client_ip(request))
        return JsonResponse(
            {"ok": False, "error": "Слишком много заявок с одного адреса. Попробуйте позже или позвоните нам."},
            status=429,
        )

    landing_id = str(payload.get("landing_id") or "").strip() or DEFAULT_LANDING_ID
    utm = _utm_from_payload(payload)

    lead = LandingLead.objects.create(
        lead_id=uuid4().hex[:16],
        landing_id=landing_id[:100],
        name=name[:200],
        phone=phone,
        comment=str(payload.get("comment") or "").strip()[:2000],
        consent=True,
        source=str(payload.get("source") or "").strip()[:100],
        service_label=str(payload.get("service_label") or "").strip()[:200],
        area_label=str(payload.get("area_label") or "").strip()[:100],
        landing_url=str(payload.get("landing_url") or "").strip()[:500],
        page_path=str(payload.get("page_path") or "").strip()[:300],
        referrer=str(payload.get("referrer") or "").strip()[:500],
        utm_source=utm["utm_source"],
        utm_medium=utm["utm_medium"],
        utm_campaign=utm["utm_campaign"],
        utm_content=utm["utm_content"],
        utm_term=utm["utm_term"],
        yclid=utm["yclid"],
        ip=_client_ip(request)[:64],
    )

    _send_to_bitrix(lead, utm)
    _notify_telegram(lead, utm)

    return JsonResponse({"ok": True, "lead_id": lead.lead_id})


@require_GET
def landing_health(request: HttpRequest) -> JsonResponse:
    """GET /api/health/ - живость приёма заявок и готовность Telegram-алертов."""
    return JsonResponse(
        {
            "ok": True,
            "landing_id": DEFAULT_LANDING_ID,
            "telegram_notify": bool(_tg_chat_id() and TelegramBotClient().token),
        }
    )
