"""Сетка скидок за объём для скрытого оптового каталога /opt/.

Единственное место, где живут пороги и проценты. Логика расчёта их не знает
в лицо: она берёт базу (сумма корзины или количество штук) и идёт по таблице
сверху вниз. Заказчику, чтобы поменять скидки, достаточно править DISCOUNT_TIERS
и DISCOUNT_BASIS - трогать views, API и фронт не нужно.

ВНИМАНИЕ: значения ниже - ЗАГЛУШКА, они НЕ утверждены заказчиком. Реальную
сетку он передаёт следующим слоем вместе со списком позиций и ценами. Пока
DISCOUNT_TIERS_APPROVED = False, в корзине и на витрине рядом со скидкой
показывается пометка «предварительно, требует утверждения».
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Как считаем объём для скидки:
#   "amount"   - по сумме корзины в рублях (порог = рубли);
#   "quantity" - по суммарному количеству штук (порог = штуки).
# Замена правила - это ровно одна строка здесь, формулы ниже общие.
DISCOUNT_BASIS = "amount"

# Утверждена ли сетка заказчиком. False = в интерфейсе висит дисклеймер.
DISCOUNT_TIERS_APPROVED = False

# Пороги: (порог включительно, процент скидки). Порядок любой, сортируем сами.
# ЗАГЛУШКА до утверждения заказчиком.
DISCOUNT_TIERS: tuple[tuple[int, int], ...] = (
    (100_000, 3),
    (300_000, 5),
    (500_000, 8),
)

DISCOUNT_DISCLAIMER = "Скидка предварительная, сетка требует утверждения."

# Минимальная сумма заказа в рублях. Считается всегда по деньгам, независимо от
# DISCOUNT_BASIS: «минимальный заказ от 100 штук» никто не формулирует.
# ЗАГЛУШКА до утверждения заказчиком: реальную цифру он называет вместе с сеткой.
MIN_ORDER_AMOUNT = 30_000

# Утверждена ли минимальная сумма. False = рядом висит та же пометка.
MIN_ORDER_APPROVED = False

MIN_ORDER_DISCLAIMER = "Минимальная сумма заказа предварительная, требует утверждения."

_CENTS = Decimal("0.01")


def _sorted_tiers() -> list[tuple[int, int]]:
    return sorted(DISCOUNT_TIERS, key=lambda tier: tier[0])


def discount_basis_value(subtotal: Decimal, total_quantity: int) -> Decimal:
    """База, по которой сравниваем с порогами: рубли или штуки."""
    if DISCOUNT_BASIS == "quantity":
        return Decimal(total_quantity)
    return Decimal(subtotal)


def discount_percent_for(subtotal: Decimal, total_quantity: int) -> int:
    """Процент скидки по текущей сетке. 0, если ни один порог не взят."""
    base = discount_basis_value(subtotal, total_quantity)
    percent = 0
    for threshold, tier_percent in _sorted_tiers():
        if base >= Decimal(threshold):
            percent = tier_percent
    return percent


def money(value: Decimal | int | float) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def calculate_totals(subtotal: Decimal, total_quantity: int) -> dict:
    """Сумма, процент, рубли скидки и итог. Единственный расчёт на весь проект."""
    subtotal = money(subtotal)
    percent = discount_percent_for(subtotal, total_quantity)
    discount_amount = money(subtotal * Decimal(percent) / Decimal(100))
    return {
        "subtotal": subtotal,
        "discount_percent": percent,
        "discount_amount": discount_amount,
        "total": money(subtotal - discount_amount),
        "basis": DISCOUNT_BASIS,
        "approved": DISCOUNT_TIERS_APPROVED,
    }


def tiers_for_frontend() -> dict:
    """Конфиг скидок для JS корзины: фронт считает по той же таблице, что сервер.

    Итог всё равно пересчитывается на сервере при отправке заказа - здесь только
    то, что нужно показать человеку, пока он набирает объём.
    """
    return {
        "basis": DISCOUNT_BASIS,
        "approved": DISCOUNT_TIERS_APPROVED,
        "disclaimer": DISCOUNT_DISCLAIMER,
        "min_order": MIN_ORDER_AMOUNT,
        "min_order_approved": MIN_ORDER_APPROVED,
        "min_order_disclaimer": MIN_ORDER_DISCLAIMER,
        "tiers": [
            {"threshold": threshold, "percent": percent}
            for threshold, percent in _sorted_tiers()
        ],
    }


def tiers_for_display() -> list[dict]:
    """Строки таблицы скидок для шаблона витрины."""
    unit = "₽" if DISCOUNT_BASIS == "amount" else "шт"
    return [
        {"threshold": threshold, "percent": percent, "unit": unit}
        for threshold, percent in _sorted_tiers()
    ]


def format_amount(value: Decimal | int | float) -> str:
    """«103000» -> «103 000»: разряды через пробел, как в прайсе."""
    whole = int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{whole:,}".replace(",", " ")


def format_base(value: Decimal | int | float) -> str:
    """База скидки словами: рубли или штуки, смотря что стоит в DISCOUNT_BASIS."""
    if DISCOUNT_BASIS == "quantity":
        return f"{format_amount(value)} шт"
    return f"{format_amount(value)} ₽"


def threshold_label(threshold: int) -> str:
    return f"от {format_base(threshold)}"


def price_ladder(retail_price: Decimal | int | float) -> list[dict]:
    """Ценовая лестница карточки: розница плюс ступени по текущей сетке скидок.

    Отдельного поля под каждую ступень в БД нет и быть не должно: ступень - это
    розничная цена минус процент из DISCOUNT_TIERS. Поменяли сетку - лестница
    поехала следом сама, разъехаться данным негде.
    """
    retail = money(retail_price)
    steps = [
        {
            "percent": 0,
            "threshold": 0,
            "price": retail,
            "price_text": f"{format_amount(retail)} ₽",
            "label": "Без скидки",
            "is_retail": True,
        }
    ]
    for threshold, percent in _sorted_tiers():
        price = money(retail * Decimal(100 - percent) / Decimal(100))
        steps.append(
            {
                "percent": percent,
                "threshold": threshold,
                "price": price,
                "price_text": f"{format_amount(price)} ₽",
                "label": threshold_label(threshold),
                "is_retail": False,
            }
        )
    return steps


def next_tier_for(subtotal: Decimal, total_quantity: int) -> dict | None:
    """Ближайшая невзятая ступень или None, если человек уже на максимуме."""
    base = discount_basis_value(subtotal, total_quantity)
    for threshold, percent in _sorted_tiers():
        if base < Decimal(threshold):
            return {
                "threshold": threshold,
                "percent": percent,
                "remaining": Decimal(threshold) - base,
            }
    return None


def progress_hint(subtotal: Decimal, total_quantity: int) -> str:
    """Строка под полосой прогресса: сколько добрать до следующей ступени."""
    tiers = _sorted_tiers()
    if not tiers:
        return ""
    percent = discount_percent_for(subtotal, total_quantity)
    nxt = next_tier_for(subtotal, total_quantity)
    if nxt is None:
        return f"Максимальная скидка {percent}%"
    remaining = format_base(nxt["remaining"])
    if percent == 0:
        return f"Добавьте товаров на {remaining}, чтобы получить первую скидку"
    return f"До скидки {nxt['percent']}% осталось {remaining}"


def min_order_remaining(subtotal: Decimal) -> Decimal:
    """Сколько не хватает до минимальной суммы заказа. 0, если хватает."""
    left = Decimal(MIN_ORDER_AMOUNT) - money(subtotal)
    return money(left) if left > 0 else money(0)


def min_order_reached(subtotal: Decimal) -> bool:
    return money(subtotal) >= Decimal(MIN_ORDER_AMOUNT)


def min_order_error(subtotal: Decimal) -> str:
    """Текст ошибки, если заказ меньше минимальной суммы."""
    return (
        f"Минимальный заказ от {format_amount(MIN_ORDER_AMOUNT)} ₽. "
        f"Добавьте товаров ещё на {format_amount(min_order_remaining(subtotal))} ₽."
    )


def progress_state(subtotal: Decimal, total_quantity: int) -> dict:
    """Всё, что нужно полосе прогресса: процент, подсказка, минимальный заказ."""
    subtotal = money(subtotal)
    nxt = next_tier_for(subtotal, total_quantity)
    return {
        "percent": discount_percent_for(subtotal, total_quantity),
        "base": discount_basis_value(subtotal, total_quantity),
        "next_tier": nxt,
        "is_max": nxt is None and bool(_sorted_tiers()),
        "hint": progress_hint(subtotal, total_quantity),
        "min_order": MIN_ORDER_AMOUNT,
        "min_order_reached": min_order_reached(subtotal),
        "min_order_remaining": min_order_remaining(subtotal),
    }


def min_order_for_display() -> dict:
    """Строка «Минимальный заказ от: N ₽» для шаблонов."""
    return {
        "amount": MIN_ORDER_AMOUNT,
        "text": f"Минимальный заказ от: {format_amount(MIN_ORDER_AMOUNT)} ₽",
        "approved": MIN_ORDER_APPROVED,
        "disclaimer": MIN_ORDER_DISCLAIMER,
    }
