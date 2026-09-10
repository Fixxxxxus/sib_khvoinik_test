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
