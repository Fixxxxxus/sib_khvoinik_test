"""Приём формы акции «-50% на отдельные хвойные и многолетники» (июль 2026).

Форма посадочных страниц /akciya-hvoynye-50/ (source=site) и /direct-50/ (source=direct)
работает как цифровая карта лояльности: upsert КОНТАКТА в Б24 (дедуп по телефону),
плюс пометка источника акции в мультиполе «Товарное направление» и отдельный SOURCE_ID
для новых контактов. Лиды НЕ создаём. 1С-синк - тот же best-effort, что у карты.

Промокод фронт показывает В ЛЮБОМ СЛУЧАЕ (даже при ok=false), код не секретный, так что
конверсию из-за сбоя Б24 не теряем. Fallback в прямой лид для этой формы не делаем.
"""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from care_notifications.bitrix24 import Bitrix24Error

from .data import (
    B24_PRODUCT_DIR_PROMO50_DIRECT_ID,
    B24_PRODUCT_DIR_PROMO50_SITE_ID,
    B24_PROMO50_SOURCE_DIRECT,
    B24_PROMO50_SOURCE_SITE,
)
from .loyalty import (
    _client_ip,
    _is_rate_limited,
    register_loyalty_card,
    sync_card_to_1c,
)

logger = logging.getLogger(__name__)

# source -> (пункт мультиполя «Товарное направление», SOURCE_ID для нового контакта).
_SOURCE_MAP = {
    "direct": (B24_PRODUCT_DIR_PROMO50_DIRECT_ID, B24_PROMO50_SOURCE_DIRECT),
    "site": (B24_PRODUCT_DIR_PROMO50_SITE_ID, B24_PROMO50_SOURCE_SITE),
}


def _build_comment(payload: dict) -> str:
    """Собирает COMMENTS из UTM-меток и адреса страницы (пишется только новым контактам)."""
    utm = payload.get("utm") or {}
    lines = ["Заявка на промокод акции -50% (хвойные и многолетники)."]
    if isinstance(utm, dict) and utm:
        utm_str = ", ".join(f"{k}={v}" for k, v in utm.items() if v)
        if utm_str:
            lines.append(f"UTM: {utm_str}")
    page_path = str(payload.get("pagePath") or "").strip()
    if page_path:
        lines.append(f"Страница: {page_path}")
    return "\n".join(lines)


@csrf_exempt
@require_POST
def promo_sale50(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """POST /api/promo/sale50/ - приём формы акции, upsert контакта в Б24 с пометкой источника."""
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid json")

    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    consent = payload.get("consent")
    source = str(payload.get("source") or "").strip().lower()
    if source not in _SOURCE_MAP:
        source = "site"

    if not phone or len("".join(ch for ch in phone if ch.isdigit())) < 10:
        return JsonResponse({"ok": False, "error": "phone_required"}, status=400)
    if not consent:
        return JsonResponse({"ok": False, "error": "consent_required"}, status=400)

    if _is_rate_limited(request):
        logger.warning("promo_sale50: rate limit для IP %s", _client_ip(request))
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)

    dir_tag, source_id = _SOURCE_MAP[source]

    try:
        contact_id, created = register_loyalty_card(
            name=name,
            phone=phone,
            extra_dir_tags=[dir_tag],
            source_id=source_id,
            comments=_build_comment(payload),
        )
    except Bitrix24Error as e:
        logger.warning("promo_sale50: Bitrix24 error: %s", e)
        return JsonResponse({"ok": False, "error": "b24_unavailable"}, status=502)

    # 1С-синк best-effort (человек заодно получает цифровую карту), сбой не влияет на ответ.
    try:
        sync_card_to_1c(name=name, phone=phone, contact_id=contact_id)
    except Exception:  # noqa: BLE001 - 1С не должна ронять оформление
        logger.exception("promo_sale50: неожиданная ошибка sync_card_to_1c")

    return JsonResponse({"ok": True, "contact_id": contact_id, "created": created})
