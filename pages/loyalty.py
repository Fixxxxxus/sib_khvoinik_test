"""Оформление цифровой карты лояльности садовых центров (задача Б24 #1231).

Форма на странице СЦ шлёт сюда ФИО + телефон. Мы кладём данные на КОНТАКТ в
Битрикс24 (а не лид): лояльность - про человека, и штатный коннектор 1С-Битрикс24
синхронит именно контакты в 1С:УНФ 3.0. На кассе СЦ скидка применяется по телефону.

Дедуп по телефону: один телефон = один контакт = одна карта. Повторная заявка не
плодит дубль, а лишь дозаполняет поля карты, если они ещё пустые, и НЕ затирает
номер/процент, которые УНФ мог уже записать обратно (УНФ - источник истины).

Любой сбой Б24 не глушим тихо для пользователя: вьюха возвращает ok=false, а фронт
падает на старый прямой crm.lead.add (как у Службы заботы), чтобы заявка не потерялась.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from care_notifications.bitrix24 import Bitrix24Client, Bitrix24Error

from .data import (
    B24_CONTACT_PRODUCT_DIR_FIELD,
    B24_LOYALTY_CARD_NO_FIELD,
    B24_LOYALTY_DATE_FIELD,
    B24_LOYALTY_DISCOUNT_FIELD,
    B24_LOYALTY_SOURCE_ID,
    B24_LOYALTY_START_DISCOUNT,
    B24_LOYALTY_STATUS_FIELD,
    B24_LOYALTY_STATUS_NEW_ID,
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
    """Создаёт или обновляет контакт под карту лояльности. Возвращает (contact_id, created)."""
    client = Bitrix24Client()
    today = timezone.localdate().isoformat()
    contact_id = client.find_contact_id_by_phone(phone)

    if contact_id:
        existing = client.get_contact(contact_id)
        fields: dict[str, object] = {}
        # Стартовые поля карты - только если контакт ещё не в программе. Номер и
        # процент, записанные УНФ, не трогаем.
        if not existing.get(B24_LOYALTY_STATUS_FIELD):
            fields[B24_LOYALTY_STATUS_FIELD] = B24_LOYALTY_STATUS_NEW_ID
        if not existing.get(B24_LOYALTY_DISCOUNT_FIELD):
            fields[B24_LOYALTY_DISCOUNT_FIELD] = B24_LOYALTY_START_DISCOUNT
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
        B24_LOYALTY_STATUS_FIELD: B24_LOYALTY_STATUS_NEW_ID,
        B24_LOYALTY_DISCOUNT_FIELD: B24_LOYALTY_START_DISCOUNT,
        B24_LOYALTY_DATE_FIELD: today,
        B24_CONTACT_PRODUCT_DIR_FIELD: [str(B24_PRODUCT_DIR_LOYALTY_CARD_ID)],
    }
    fields.update(_split_full_name(name))
    contact_id = client.create_contact(fields)
    return contact_id, True


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

    try:
        contact_id, created = register_loyalty_card(name=name, phone=phone)
    except Bitrix24Error as e:
        logger.warning("loyalty_card: Bitrix24 error: %s", e)
        return JsonResponse({"ok": False, "error": "b24_unavailable"}, status=502)

    return JsonResponse({"ok": True, "contact_id": contact_id, "created": created})
