"""Оформление цифровой карты лояльности садовых центров (задача Б24 #1231).

Форма на странице СЦ шлёт сюда ФИО + телефон. Мы кладём данные на КОНТАКТ в
Битрикс24 (а не лид): лояльность - про человека, и в Б24 их видят менеджеры.

Параллельно карту шлём НАПРЯМУЮ в 1С:УНФ через HTTP-сервис (care_notifications.onec):
штатный коннектор Б24↔1С требует профтарифа, поэтому связку Б24→1С заменили прямым
коннектом сайт→1С. Отправка best-effort: создаём журнальную запись OneCCardSync,
пробуем отправить сразу, при сбое 1С запись остаётся pending и её добивает крон-
команда sync_onec_cards. Недоступность 1С НЕ влияет на ответ пользователю - ok
зависит только от Б24.

Модель (согласована с 1С-ником 2026-06-01): клиент и дисконтная карта - разные
справочники УНФ. Контакт заводит типовой обмен; карту - допобмен УНФ при первом
приходе. Идентификатор карты = телефон (отдельного номера нет). Скидку считает УНФ
на кассе, обратной записи в Б24 нет. Поэтому из полей карты мы пишем только надёжный
булев флаг «участник программы» + источник + дату; процент/номер/статус НЕ пишем,
чтобы не зафиксировать в CRM устаревшее число, которое введёт менеджера в заблуждение.

Дедуп по телефону: один телефон = один контакт. Повторная заявка не плодит дубль,
а лишь проставляет флаг участника, если его ещё нет.

Любой сбой Б24 не глушим тихо для пользователя: вьюха возвращает ok=false, а фронт
падает на старый прямой crm.lead.add (как у Службы заботы), чтобы заявка не потерялась.
"""

from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from care_notifications.bitrix24 import Bitrix24Client, Bitrix24Error
from care_notifications.models import OneCCardSync
from care_notifications.onec import OneCClient, OneCError, canonicalize_phone, mask_phone

from .data import (
    B24_CONTACT_PRODUCT_DIR_FIELD,
    B24_LOYALTY_DATE_FIELD,
    B24_LOYALTY_FLAG_FIELD,
    B24_LOYALTY_SOURCE_ID,
    B24_PRODUCT_DIR_LOYALTY_CARD_ID,
)

logger = logging.getLogger(__name__)


def _split_full_name(full_name: str) -> dict[str, str]:
    """Разбивает ФИО «Фамилия Имя Отчество» на поля контакта Б24.

    Плейсхолдер формы задаёт именно такой порядок. Меньше трёх слов - кладём,
    что есть: одно слово -> имя, два -> фамилия + имя.
    """
    parts = (full_name or "").split()
    if not parts:
        return {}
    if len(parts) == 1:
        return {"NAME": parts[0]}
    if len(parts) == 2:
        return {"LAST_NAME": parts[0], "NAME": parts[1]}
    return {"LAST_NAME": parts[0], "NAME": parts[1], "SECOND_NAME": " ".join(parts[2:])}


def _merge_product_dir(existing: object) -> list:
    """Дополняет мультисписок «Товарное направление» тегом «Скидочная карта».

    Б24 при update полностью замещает значение multiple-поля, поэтому читаем текущее
    и дописываем ID тега, если его там ещё нет.
    """
    values: list = []
    if isinstance(existing, list):
        values = [str(v) for v in existing if str(v)]
    elif existing:
        values = [str(existing)]
    tag = str(B24_PRODUCT_DIR_LOYALTY_CARD_ID)
    if tag not in values:
        values.append(tag)
    return values


def register_loyalty_card(*, name: str, phone: str) -> tuple[int, bool]:
    """Создаёт или помечает контакт как участника программы. Возвращает (contact_id, created)."""
    client = Bitrix24Client()
    today = timezone.localdate().isoformat()
    contact_id = client.find_contact_id_by_phone(phone)

    if contact_id:
        existing = client.get_contact(contact_id)
        fields: dict[str, object] = {}
        # Флаг участника - надёжный маркер; ставим, если ещё не стоит.
        if str(existing.get(B24_LOYALTY_FLAG_FIELD) or "") not in ("1", "Y", "True"):
            fields[B24_LOYALTY_FLAG_FIELD] = 1
        if not existing.get(B24_LOYALTY_DATE_FIELD):
            fields[B24_LOYALTY_DATE_FIELD] = today
        fields[B24_CONTACT_PRODUCT_DIR_FIELD] = _merge_product_dir(
            existing.get(B24_CONTACT_PRODUCT_DIR_FIELD)
        )
        # ФИО дозаполняем, только если у контакта пусто (не перетираем оператора).
        if name and not (existing.get("NAME") or existing.get("LAST_NAME")):
            fields.update(_split_full_name(name))
        if fields:
            client.update_contact(contact_id, fields)
        return contact_id, False

    fields = {
        "SOURCE_ID": B24_LOYALTY_SOURCE_ID,
        "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"}],
        B24_LOYALTY_FLAG_FIELD: 1,
        B24_LOYALTY_DATE_FIELD: today,
        B24_CONTACT_PRODUCT_DIR_FIELD: [str(B24_PRODUCT_DIR_LOYALTY_CARD_ID)],
    }
    fields.update(_split_full_name(name))
    contact_id = client.create_contact(fields)
    return contact_id, True


def sync_card_to_1c(*, name: str, phone: str, contact_id: int | None) -> None:
    """Шлёт карту в 1С best-effort: журналируем + пробуем отправить сразу.

    Никогда не кидает наружу - сбой 1С не должен ломать ответ пользователю (карта
    уже в Б24). При неуспехе запись остаётся pending, её добьёт sync_onec_cards.
    """
    canonical = canonicalize_phone(phone)
    if not canonical:
        logger.warning("sync_card_to_1c: телефон %s не приводится к +7XXXXXXXXXX, в 1С не шлём", mask_phone(phone))
        return

    parts = _split_full_name(name)
    job = OneCCardSync.objects.create(
        phone=canonical,
        first_name=parts.get("NAME", ""),
        last_name=parts.get("LAST_NAME", ""),
        middle_name=parts.get("SECOND_NAME", ""),
        b24_contact_id=contact_id,
    )

    client = OneCClient()
    if not client.is_configured():
        # 1С не настроена в окружении: запись осталась pending - аудит + ручной разбор.
        return
    try:
        client.register_card(
            phone=job.phone,
            first_name=job.first_name,
            last_name=job.last_name,
            middle_name=job.middle_name,
        )
    except OneCError as e:
        job.attempts = 1
        job.last_error = str(e)[:2000]
        job.save(update_fields=["attempts", "last_error", "updated_at"])
        # В лог не кладём str(e) - оно содержит URL с телефоном и ФИО (ПДн);
        # подробности лежат в OneCCardSync.last_error / админке.
        logger.warning("sync_card_to_1c: 1С недоступна, заявка #%s (%s) осталась pending", job.pk, mask_phone(job.phone))
        return
    job.status = OneCCardSync.STATUS_SENT
    job.attempts = 1
    job.sent_at = timezone.now()
    job.save(update_fields=["status", "attempts", "sent_at", "updated_at"])


# Антиспам публичной формы карты. Кэш по умолчанию LocMemCache (per-process), при
# нескольких gunicorn-воркерах лимит срабатывает мягче (фактически ~лимит×воркеры),
# но это всё равно поднимает порог против ботов. Точный общий лимит потребовал бы
# отдельного кэша (Redis) - заводить инфру под это не стали.
RATE_IP_MAX = 10  # заявок с одного IP
RATE_IP_WINDOW = 600  # за 10 минут


def _client_ip(request: HttpRequest) -> str:
    """Реальный IP клиента: за Caddy он в X-Forwarded-For, первый адрес слева."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def _is_rate_limited(request: HttpRequest) -> bool:
    """Грубый лимит по IP, чтобы бот не набивал фейковые заявки в Б24/1С."""
    key = f"loyalty:rl:ip:{_client_ip(request)}"
    if cache.add(key, 1, RATE_IP_WINDOW):  # первый запрос в окне - ключа ещё нет
        return False
    try:
        count = cache.incr(key)  # incr НЕ сбрасывает TTL - окно считается от первого
    except ValueError:
        cache.add(key, 1, RATE_IP_WINDOW)
        return False
    return count > RATE_IP_MAX


@csrf_exempt
@require_POST
def loyalty_card(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """POST /api/loyalty/card/ - приём формы цифровой карты, upsert контакта в Б24."""
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid json")

    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    consent = payload.get("consent")

    if not phone or len("".join(ch for ch in phone if ch.isdigit())) < 10:
        return JsonResponse({"ok": False, "error": "phone_required"}, status=400)
    if not consent:
        return JsonResponse({"ok": False, "error": "consent_required"}, status=400)

    if _is_rate_limited(request):
        logger.warning("loyalty_card: rate limit для IP %s", _client_ip(request))
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)

    try:
        contact_id, created = register_loyalty_card(name=name, phone=phone)
    except Bitrix24Error as e:
        logger.warning("loyalty_card: Bitrix24 error: %s", e)
        return JsonResponse({"ok": False, "error": "b24_unavailable"}, status=502)

    # Прямая отправка в 1С - best-effort, любой сбой не влияет на ответ пользователю.
    try:
        sync_card_to_1c(name=name, phone=phone, contact_id=contact_id)
    except Exception:  # noqa: BLE001 - 1С не должна ронять оформление карты
        logger.exception("loyalty_card: неожиданная ошибка sync_card_to_1c")

    return JsonResponse({"ok": True, "contact_id": contact_id, "created": created})
