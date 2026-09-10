"""Приём оптовых заказов из корзины /opt/: POST /api/opt/order/.

Механика повторяет приём лидов с посадочных (pages/landing_leads.py): пишем
заказ в БД, дальше best-effort уведомляем менеджера в Битрикс24 и Telegram.
Сбой уведомления не меняет ответ - заказ уже сохранён.

Ключевое отличие от лида: в теле запроса приходят только слаги позиций и
количества. Цены, скидка и итог считаются на сервере по данным из БД - цене
из браузера доверять нельзя, её правит кто угодно через консоль.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from uuid import uuid4

from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from care_notifications.bitrix24 import Bitrix24Client, Bitrix24Error
from care_notifications.telegram_bot import TelegramBotClient

from . import wholesale_pricing
from .landing_leads import UTM_KEYS, format_phone, normalize_phone
from .loyalty import _client_ip, _is_rate_limited
from .models import WholesaleItem, WholesaleItemVariant, WholesaleOrder, WholesaleOrderLine

logger = logging.getLogger(__name__)

# Куда уведомлять менеджера опта. Отдельная переменная, чтобы оптовые заказы не
# смешивались с заявками посадочных; если не задана, падаем на канал лидов, а
# если и его нет - просто молчим (заказ всё равно в БД и в админке).
TG_CHAT_ID_ENV = "WHOLESALE_ORDER_TG_CHAT_ID"
TG_CHAT_ID_FALLBACK_ENVS = ("LANDING_LEAD_TG_CHAT_ID", "CARE_PROMO_ADMIN_CHAT_ID")

B24_TITLE = "Опт: заказ из каталога /opt/"

MAX_LINES = 100  # строк в одном заказе
MAX_QUANTITY = 100_000  # единиц в одной строке


def _tg_chat_id() -> str:
    for env_name in (TG_CHAT_ID_ENV, *TG_CHAT_ID_FALLBACK_ENVS):
        chat_id = os.environ.get(env_name, "").strip()
        if chat_id:
            return chat_id
    return ""


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


def _parse_quantity(raw) -> int:
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        return 0
    if qty < 1:
        return 0
    return min(qty, MAX_QUANTITY)


def _parse_variant_id(raw) -> int | None:
    try:
        variant_id = int(raw)
    except (TypeError, ValueError):
        return None
    return variant_id if variant_id > 0 else None


def build_order_lines(raw_items) -> tuple[list[dict], Decimal, int]:
    """Строки заказа по данным из БД. Возвращает (строки, сумма, всего единиц).

    Из запроса берём только слаг позиции, id варианта и количество. Всё
    остальное - название, размер, единицу, остаток и цену - читаем из БД:
    клиент цену не задаёт. Количество сверху ограничено остатком варианта.
    """
    if not isinstance(raw_items, list):
        return [], Decimal(0), 0

    wanted: list[tuple[str, str, int | None, int]] = []
    for raw in raw_items[:MAX_LINES]:
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get("slug") or "").strip()[:250]
        section_slug = str(raw.get("section") or "").strip()[:200]
        variant_id = _parse_variant_id(raw.get("variant") or raw.get("variant_id"))
        qty = _parse_quantity(raw.get("qty") or raw.get("quantity"))
        if slug and qty:
            wanted.append((section_slug, slug, variant_id, qty))
    if not wanted:
        return [], Decimal(0), 0

    items = {
        (item.section.slug, item.slug): item
        for item in WholesaleItem.objects.select_related("section")
        .prefetch_related("variants")
        .filter(
            slug__in=[slug for _, slug, _, _ in wanted],
            is_active=True,
            section__is_active=True,
        )
    }
    variant_ids = [vid for _, _, vid, _ in wanted if vid]
    variants = {
        variant.pk: variant
        for variant in WholesaleItemVariant.objects.select_related("item").filter(
            pk__in=variant_ids, is_active=True
        )
    }

    lines: list[dict] = []
    subtotal = Decimal(0)
    total_quantity = 0
    seen: set[tuple[str, str, int | None]] = set()
    for section_slug, slug, variant_id, qty in wanted:
        item = items.get((section_slug, slug))
        if item is None:
            # Раздел мог не приехать или приехать неверным: ищем по слагу позиции,
            # если он однозначен. Иначе строку молча пропускаем.
            candidates = [i for (s, sl), i in items.items() if sl == slug]
            if len(candidates) != 1:
                logger.info("opt order: позиция %r/%r не найдена, строка пропущена", section_slug, slug)
                continue
            item = candidates[0]

        item_variants = [v for v in item.variants.all() if v.is_active]
        variant = None
        if variant_id is not None:
            variant = variants.get(variant_id)
            if variant is None or variant.item_id != item.pk:
                logger.info("opt order: вариант %r у позиции %r не найден, строка пропущена", variant_id, slug)
                continue
        elif item_variants:
            # У позиции есть варианты, а браузер не сказал какой: остаток и цена
            # неоднозначны, угадывать за клиента нельзя.
            logger.info("opt order: позиция %r требует выбора варианта, строка пропущена", slug)
            continue

        key = (item.section.slug, item.slug, variant.pk if variant else None)
        if key in seen:
            continue
        seen.add(key)

        price = wholesale_pricing.money(variant.effective_price if variant else item.price)
        if variant is not None:
            if variant.stock <= 0:
                logger.info("opt order: вариант %r распродан, строка пропущена", variant.pk)
                continue
            qty = min(qty, variant.stock)

        line_total = wholesale_pricing.money(price * qty)
        subtotal += line_total
        total_quantity += qty
        lines.append(
            {
                "item": item,
                "variant": variant,
                "title": item.title,
                "variant_title": variant.title if variant else "",
                "size": item.size,
                "unit": item.unit,
                "price": price,
                "quantity": qty,
                "line_total": line_total,
            }
        )
    return lines, wholesale_pricing.money(subtotal), total_quantity


def build_order_text(order: WholesaleOrder, lines: list[dict], utm: dict) -> str:
    """Текст уведомления менеджеру: состав заказа, скидка, итог, контакты."""
    rows = [
        f"- {line['title']}"
        + (f", {line['variant_title']}" if line.get("variant_title") else "")
        + (f" ({line['size']})" if line["size"] else "")
        + f": {line['quantity']} {line['unit']} x {line['price']} ₽ = {line['line_total']} ₽"
        for line in lines
    ]
    parts = [
        "Оптовый заказ из каталога /opt/",
        f"order_id: {order.order_id}",
        f"Имя: {order.name}",
    ]
    if order.company:
        parts.append(f"Компания: {order.company}")
    parts.append(f"Телефон: {format_phone(order.phone)}")
    if order.email:
        parts.append(f"Email: {order.email}")
    parts.append("Состав:")
    parts.extend(rows)
    parts.append(f"Сумма: {order.subtotal} ₽")
    parts.append(f"Скидка: {order.discount_percent}% ({order.discount_amount} ₽)")
    if not wholesale_pricing.DISCOUNT_TIERS_APPROVED:
        parts.append(f"Внимание: {wholesale_pricing.DISCOUNT_DISCLAIMER}")
    # Верхняя ступень сетки - не процент, а индивидуальное предложение: менеджер
    # должен подтвердить цену руками, показанный итог предварительный.
    if wholesale_pricing.is_individual(order.subtotal, order.total_quantity):
        parts.append(f"Внимание: {wholesale_pricing.INDIVIDUAL_TIER_TEXT}")
    parts.append(f"Итого: {order.total} ₽")
    if order.comment:
        parts.append(f"Комментарий: {order.comment}")
    parts.append(f"UTM: {_utm_line(utm)}")
    return "\n".join(parts)


def _send_to_bitrix(order: WholesaleOrder, lines: list[dict], utm: dict) -> None:
    """Лид в Б24 составом заказа. Ошибки только логируем: заказ уже в БД."""
    try:
        b24_id = Bitrix24Client().create_lead(
            title=f"{B24_TITLE} {order.order_id}",
            name=order.company or order.name,
            phone=format_phone(order.phone),
            email=order.email,
            comments=build_order_text(order, lines, utm),
            source_id="WEB",
            extra_fields={"SOURCE_DESCRIPTION": f"opt-catalog | {_utm_line(utm)}"[:255]},
        )
    except Bitrix24Error as e:
        logger.warning("opt order %s: Bitrix24 недоступен: %s", order.order_id, e)
        return
    except Exception:  # noqa: BLE001 - Б24 не должен ронять приём заказа
        logger.exception("opt order %s: неожиданная ошибка Bitrix24", order.order_id)
        return
    WholesaleOrder.objects.filter(pk=order.pk).update(b24_lead_id=b24_id)
    order.b24_lead_id = b24_id


def _notify_telegram(order: WholesaleOrder, lines: list[dict], utm: dict) -> None:
    """Best-effort алерт менеджеру: без chat id или токена просто молчим."""
    chat_id = _tg_chat_id()
    if not chat_id:
        logger.info("opt order %s: %s не задан, Telegram-алерт пропущен", order.order_id, TG_CHAT_ID_ENV)
        return
    bot = TelegramBotClient()
    if not bot.token:
        logger.info("opt order %s: TELEGRAM_BOT_TOKEN не задан, алерт пропущен", order.order_id)
        return
    try:
        res = bot.send_message(int(chat_id), build_order_text(order, lines, utm), parse_mode="")
    except (ValueError, TypeError):
        logger.warning("opt order %s: некорректный chat id %r", order.order_id, chat_id)
        return
    except Exception:  # noqa: BLE001 - Telegram не должен ронять приём заказа
        logger.exception("opt order %s: неожиданная ошибка Telegram", order.order_id)
        return
    if not res.get("ok"):
        logger.warning("opt order %s: Telegram не принял алерт: %s", order.order_id, res.get("error"))


@csrf_exempt
@require_POST
def opt_order(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """POST /api/opt/order/ - оформление заказа из корзины оптового каталога."""
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid json")
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("invalid json")

    # Honeypot: поле спрятано от людей, заполняют его только боты. Отвечаем ok,
    # чтобы бот не искал обход, но ничего не сохраняем и никого не будим.
    if str(payload.get("company_site") or "").strip():
        logger.info("opt order: honeypot сработал, IP %s", _client_ip(request))
        return JsonResponse({"ok": True, "order_id": uuid4().hex[:16]})

    name = str(payload.get("name") or "").strip()
    phone = normalize_phone(payload.get("phone"))

    if len(name) < 2:
        return JsonResponse(
            {"ok": False, "error": "Укажите имя или название компании.", "field": "name"},
            status=400,
        )
    if not phone:
        return JsonResponse(
            {"ok": False, "error": "Проверьте номер телефона: нужен российский номер из 11 цифр.", "field": "phone"},
            status=400,
        )

    lines, subtotal, total_quantity = build_order_lines(payload.get("items"))
    if not lines:
        return JsonResponse(
            {"ok": False, "error": "Корзина пуста или позиции больше не доступны.", "field": "items"},
            status=400,
        )

    # Минимальную сумму заказа проверяем на сервере: на фронте кнопка заблокирована,
    # но запрос отправляют и мимо неё.
    if not wholesale_pricing.min_order_reached(subtotal):
        return JsonResponse(
            {
                "ok": False,
                "error": wholesale_pricing.min_order_error(subtotal),
                "field": "items",
                "min_order": wholesale_pricing.MIN_ORDER_AMOUNT,
            },
            status=400,
        )

    if _is_rate_limited(request):
        logger.warning("opt order: rate limit для IP %s", _client_ip(request))
        return JsonResponse(
            {"ok": False, "error": "Слишком много заказов с одного адреса. Попробуйте позже или позвоните нам."},
            status=429,
        )

    totals = wholesale_pricing.calculate_totals(subtotal, total_quantity)
    utm = _utm_from_payload(payload)

    order = WholesaleOrder.objects.create(
        order_id=uuid4().hex[:16],
        name=name[:200],
        company=str(payload.get("company") or "").strip()[:200],
        phone=phone,
        email=str(payload.get("email") or "").strip()[:254],
        comment=str(payload.get("comment") or "").strip()[:2000],
        subtotal=totals["subtotal"],
        discount_percent=totals["discount_percent"],
        discount_amount=totals["discount_amount"],
        total=totals["total"],
        total_quantity=total_quantity,
        discount_basis=totals["basis"],
        source=str(payload.get("source") or "").strip()[:100],
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
    WholesaleOrderLine.objects.bulk_create(
        [
            WholesaleOrderLine(
                order=order,
                item=line["item"],
                variant=line.get("variant"),
                title=line["title"],
                variant_title=line.get("variant_title", ""),
                size=line["size"],
                unit=line["unit"],
                price=line["price"],
                quantity=line["quantity"],
                line_total=line["line_total"],
            )
            for line in lines
        ]
    )

    _send_to_bitrix(order, lines, utm)
    _notify_telegram(order, lines, utm)

    return JsonResponse(
        {
            "ok": True,
            "order_id": order.order_id,
            "subtotal": str(order.subtotal),
            "discount_percent": order.discount_percent,
            "discount_amount": str(order.discount_amount),
            "total": str(order.total),
            "message": "Заказ принят, свяжемся с вами.",
        }
    )
