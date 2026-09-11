"""Сетка скидок за объём для скрытого оптового каталога /opt/.

Единственное место, где живут пороги и проценты. Логика расчёта их не знает
в лицо: она берёт корзину (сумма в рублях и количество единиц) и идёт по
таблице снизу вверх. Заказчику, чтобы поменять скидки, достаточно править
DISCOUNT_TIERS - трогать views, API и фронт не нужно.

Сетка гибридная: часть ступеней меряется штуками, часть чеком. Ступень
считается взятой, если выполнена ЛЮБАЯ из её осей, а применяется та ступень,
которая выгоднее клиенту. Одной оси (старая константа DISCOUNT_BASIS) больше
нет: у заказчика ступени смешанные.

Источник: файл заказчика top20.xlsx, лист «Лист2», блок «Уровни скидок», плюс
уточнения заказчика от 10.09.2026 (см. DISCOUNT_TIERS_SOURCE ниже). Ступени по
количеству меряются ШТУКАМИ, а не наименованиями: 30 кустов одной культуры уже
дают 25%, разнообразие не требуется.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# --- происхождение сетки ----------------------------------------------------

# Откуда взяты пороги и когда получены. Флаг нужен, чтобы через полгода никто
# не гадал, выдуманы ли цифры в коде.
DISCOUNT_TIERS_SOURCE = (
    "Файл заказчика top20.xlsx, лист «Лист2», блок «Уровни скидок», "
    "плюс уточнения заказчика от 10.09.2026"
)
DISCOUNT_TIERS_RECEIVED = "10.09.2026"

# Сетка подтверждена заказчиком 10.09.2026, а не выдумана каркасом.
DISCOUNT_TIERS_APPROVED = True

# Верхняя ступень - не процент, а индивидуальное предложение: цену на ней
# подтверждает менеджер руками. Никаких выдуманных процентов сверх 35%.
INDIVIDUAL_TIER_NEEDS_MANUAL_APPROVAL = True

# В исходном файле пятая ступень стояла как «От 50 позиций или выше чека 200 000»
# и пересекалась с третьей ступенью (30% тоже от 50). Заказчик 10.09.2026 признал
# это ошибкой и переопределил порог по количеству на 100 штук; порог по чеку
# остался прежним. Цена на этой ступени всё равно ручная.
INDIVIDUAL_TIER_MIN_QUANTITY: int | None = 100
INDIVIDUAL_TIER_SOURCE_LABEL = "От 50 позиций или выше чека 200 000 (исходная формулировка файла)"

# --- сама сетка -------------------------------------------------------------

# Ступень: подпись, процент (None = индивидуально) и пороги по двум осям.
# min_quantity - штуки в корзине, min_amount - рубли чека. Заполнена может быть
# одна ось или обе; ступень берётся, если выполнена любая из них.
DISCOUNT_TIERS: tuple[dict, ...] = (
    {
        "key": "entry",
        "label": "Входная скидка",
        "short": "старт",
        "percent": 20,
        # Входные 20% действуют с первой штуки: оптовая цена по умолчанию -
        # это розница минус 20%.
        "min_quantity": 1,
        "min_amount": None,
        "individual": False,
    },
    {
        "key": "q30",
        "label": "От 30 штук",
        "short": "30 шт",
        "percent": 25,
        "min_quantity": 30,
        "min_amount": None,
        "individual": False,
    },
    {
        "key": "q50",
        "label": "От 50 штук",
        "short": "50 шт",
        "percent": 30,
        "min_quantity": 50,
        "min_amount": None,
        "individual": False,
    },
    {
        "key": "a100k",
        "label": "Чек от 100 000 ₽",
        "short": "100к ₽",
        "percent": 35,
        "min_quantity": None,
        "min_amount": 100_000,
        "individual": False,
    },
    {
        "key": "individual",
        "label": "От 100 штук или чек от 200 000 ₽",
        "short": "инд.",
        "percent": None,
        "min_quantity": INDIVIDUAL_TIER_MIN_QUANTITY,
        "min_amount": 200_000,
        "individual": True,
    },
)

# Текст вместо процента на индивидуальной ступени.
INDIVIDUAL_TIER_TEXT = "Дальше считаем индивидуально, менеджер подтвердит цену"
INDIVIDUAL_TIER_PRICE_TEXT = "индивидуально"

DISCOUNT_DISCLAIMER = ""

# Строка для записи в заказ: одной оси больше нет.
DISCOUNT_BASIS = "hybrid"

# Минимальная сумма заказа в рублях. Подтверждена заказчиком 10.09.2026.
MIN_ORDER_AMOUNT = 15_000
MIN_ORDER_APPROVED = True
MIN_ORDER_DISCLAIMER = ""

_CENTS = Decimal("0.01")


# --- служебное --------------------------------------------------------------


def money(value: Decimal | int | float) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def format_amount(value: Decimal | int | float) -> str:
    """«103000» -> «103 000»: разряды через пробел, как в прайсе."""
    whole = int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{whole:,}".replace(",", " ")


def format_axis(axis: str, value: Decimal | int | float) -> str:
    """Остаток словами: по штукам или по рублям, смотря какая ось ступени."""
    if axis == "quantity":
        return f"{format_amount(value)} шт"
    return f"{format_amount(value)} ₽"


def _rank(tier: dict) -> tuple[int, int]:
    """Порядок ступеней: сначала проценты по возрастанию, индивидуальная - последней."""
    return (1 if tier.get("individual") else 0, tier.get("percent") or 0)


def _sorted_tiers() -> list[dict]:
    return sorted(DISCOUNT_TIERS, key=_rank)


def tier_axes(tier: dict) -> list[tuple[str, int]]:
    """Оси ступени: [("quantity", 30)] или [("amount", 100000)] или обе."""
    axes: list[tuple[str, int]] = []
    if tier.get("min_quantity"):
        axes.append(("quantity", int(tier["min_quantity"])))
    if tier.get("min_amount"):
        axes.append(("amount", int(tier["min_amount"])))
    return axes


def tier_reached(tier: dict, subtotal: Decimal, total_quantity: int) -> bool:
    """Ступень взята, если выполнена любая из её осей: штуки ИЛИ чек."""
    subtotal = money(subtotal)
    for axis, threshold in tier_axes(tier):
        value = Decimal(total_quantity) if axis == "quantity" else subtotal
        if value >= Decimal(threshold):
            return True
    return False


def tier_label(tier: dict) -> str:
    return tier.get("label", "")


# --- расчёт -----------------------------------------------------------------


def reached_tiers(subtotal: Decimal, total_quantity: int) -> list[dict]:
    return [
        tier
        for tier in _sorted_tiers()
        if tier_reached(tier, subtotal, total_quantity)
    ]


def current_tier(subtotal: Decimal, total_quantity: int) -> dict | None:
    """Самая выгодная взятая ступень: сравниваем обе оси, берём лучшее для клиента."""
    reached = reached_tiers(subtotal, total_quantity)
    return reached[-1] if reached else None


def discount_percent_for(subtotal: Decimal, total_quantity: int) -> int:
    """Процент скидки. Индивидуальная ступень процента не добавляет: там цена ручная."""
    percent = 0
    for tier in reached_tiers(subtotal, total_quantity):
        if tier.get("individual"):
            continue
        percent = max(percent, int(tier.get("percent") or 0))
    return percent


def is_individual(subtotal: Decimal, total_quantity: int) -> bool:
    """Дошли ли до ступени «индивидуально под вас»."""
    return any(tier.get("individual") for tier in reached_tiers(subtotal, total_quantity))


def calculate_totals(subtotal: Decimal, total_quantity: int) -> dict:
    """Сумма, процент, рубли скидки и итог. Единственный расчёт на весь проект."""
    subtotal = money(subtotal)
    percent = discount_percent_for(subtotal, total_quantity)
    individual = is_individual(subtotal, total_quantity)
    discount_amount = money(subtotal * Decimal(percent) / Decimal(100))
    return {
        "subtotal": subtotal,
        "discount_percent": percent,
        "discount_amount": discount_amount,
        "total": money(subtotal - discount_amount),
        "basis": DISCOUNT_BASIS,
        "approved": DISCOUNT_TIERS_APPROVED,
        # На индивидуальной ступени показанный итог - предварительный: финальную
        # цену подтверждает менеджер, придумывать процент за него нельзя.
        "individual": individual,
        "individual_note": INDIVIDUAL_TIER_TEXT if individual else "",
    }


# --- лестница, прогресс, подсказки ------------------------------------------


def price_ladder(retail_price: Decimal | int | float) -> list[dict]:
    """Ценовая лестница карточки: розница плюс ступени по текущей сетке скидок.

    Отдельного поля под каждую ступень в БД нет и быть не должно: ступень - это
    розничная цена минус процент из DISCOUNT_TIERS. Поменяли сетку - лестница
    поехала следом сама, разъехаться данным негде. У индивидуальной ступени
    цены нет: вместо цифры стоит текст.
    """
    retail = money(retail_price)
    steps = [
        {
            "key": "retail",
            "percent": 0,
            "price": retail,
            "price_text": f"{format_amount(retail)} ₽",
            "label": "Розница",
            "is_retail": True,
            "individual": False,
        }
    ]
    for tier in _sorted_tiers():
        if tier.get("individual"):
            steps.append(
                {
                    "key": tier["key"],
                    "percent": None,
                    "price": None,
                    "price_text": INDIVIDUAL_TIER_PRICE_TEXT,
                    "label": tier_label(tier),
                    "is_retail": False,
                    "individual": True,
                    "note": INDIVIDUAL_TIER_TEXT,
                }
            )
            continue
        percent = int(tier["percent"])
        price = money(retail * Decimal(100 - percent) / Decimal(100))
        steps.append(
            {
                "key": tier["key"],
                "percent": percent,
                "price": price,
                "price_text": f"{format_amount(price)} ₽",
                "label": tier_label(tier),
                "is_retail": False,
                "individual": False,
            }
        )
    return steps


def entry_percent() -> int:
    """Входная скидка: процент самой нижней ступени. От неё считается опт-цена."""
    for tier in _sorted_tiers():
        if not tier.get("individual"):
            return int(tier.get("percent") or 0)
    return 0


def wholesale_price(retail_price: Decimal | int | float) -> Decimal:
    """Оптовая цена по умолчанию: розница минус входная скидка."""
    return money(Decimal(retail_price) * Decimal(100 - entry_percent()) / Decimal(100))


def _tier_gap(tier: dict, subtotal: Decimal, total_quantity: int) -> dict | None:
    """Ближайшая ось ступени: по какой из них добрать меньше (в долях порога)."""
    subtotal = money(subtotal)
    best = None
    for axis, threshold in tier_axes(tier):
        value = Decimal(total_quantity) if axis == "quantity" else subtotal
        remaining = Decimal(threshold) - value
        if remaining <= 0:
            remaining = Decimal(0)
        relative = float(remaining) / float(threshold) if threshold else 0.0
        candidate = {
            "axis": axis,
            "threshold": threshold,
            "remaining": remaining,
            "remaining_text": format_axis(axis, remaining),
            "relative": relative,
        }
        if best is None or candidate["relative"] < best["relative"]:
            best = candidate
    return best


# Насколько «одинаково близкими» считаем две ступени по разным осям. Если до
# чека и до количества добирать примерно поровну, ведём к нижней ступени
# лестницы: её взять проще и понятнее.
HINT_TOLERANCE = 0.1


def next_tier_for(subtotal: Decimal, total_quantity: int) -> dict | None:
    """Ближайшая невзятая ступень по ОБЕИМ осям: что реально добрать быстрее.

    Не «следующая по списку», а именно ближайшая: если до чека 100 000 ₽ осталось
    10% суммы, а до 30 позиций - половина корзины, подсказка ведёт к чеку. Когда
    обе оси примерно одинаково далеко, выигрывает нижняя ступень лестницы.
    """
    percent = discount_percent_for(subtotal, total_quantity)
    individual = is_individual(subtotal, total_quantity)
    candidates = []
    for tier in _sorted_tiers():
        if tier_reached(tier, subtotal, total_quantity):
            continue
        if tier.get("individual"):
            if individual:
                continue
        elif int(tier.get("percent") or 0) <= percent:
            # Ступень не выгоднее текущей - вести к ней незачем.
            continue
        gap = _tier_gap(tier, subtotal, total_quantity)
        if gap is None:
            continue
        candidates.append(
            {
                "key": tier["key"],
                "label": tier_label(tier),
                "percent": tier.get("percent"),
                "individual": bool(tier.get("individual")),
                "axis": gap["axis"],
                "threshold": gap["threshold"],
                "remaining": gap["remaining"],
                "remaining_text": gap["remaining_text"],
                "relative": gap["relative"],
                "rank": _rank(tier),
            }
        )
    if not candidates:
        return None
    closest = min(candidate["relative"] for candidate in candidates)
    near = [c for c in candidates if c["relative"] <= closest + HINT_TOLERANCE]
    return min(near, key=lambda c: c["rank"])


def progress_hint(subtotal: Decimal, total_quantity: int) -> str:
    """Строка под полосой прогресса: сколько добрать до ближайшей ступени."""
    tiers = _sorted_tiers()
    if not tiers:
        return ""
    subtotal = money(subtotal)
    percent = discount_percent_for(subtotal, total_quantity)
    if is_individual(subtotal, total_quantity):
        return INDIVIDUAL_TIER_TEXT
    if total_quantity <= 0 and subtotal <= 0:
        return f"Оптовая скидка {entry_percent()}% включается с первой штуки"
    nxt = next_tier_for(subtotal, total_quantity)
    if nxt is None:
        return f"Максимальная скидка {percent}%"
    if nxt["individual"]:
        return f"До индивидуальных условий осталось {nxt['remaining_text']}"
    return f"До скидки {nxt['percent']}% осталось {nxt['remaining_text']}"


def tier_progress(subtotal: Decimal, total_quantity: int) -> list[dict]:
    """Заполнение делений полосы: по каждой ступени берём лучшую из её осей."""
    subtotal = money(subtotal)
    rows = []
    for tier in _sorted_tiers():
        if tier_reached(tier, subtotal, total_quantity):
            fill = 100.0
        else:
            gap = _tier_gap(tier, subtotal, total_quantity)
            fill = max(0.0, min(100.0, (1 - gap["relative"]) * 100)) if gap else 0.0
        rows.append(
            {
                "key": tier["key"],
                "label": tier_label(tier),
                "short": tier.get("short", ""),
                "percent": tier.get("percent"),
                "individual": bool(tier.get("individual")),
                "fill": round(fill, 2),
                "reached": tier_reached(tier, subtotal, total_quantity),
            }
        )
    return rows


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
        "individual": is_individual(subtotal, total_quantity),
        "individual_text": INDIVIDUAL_TIER_TEXT,
        "quantity": total_quantity,
        "subtotal": subtotal,
        "next_tier": nxt,
        "is_max": nxt is None,
        "hint": progress_hint(subtotal, total_quantity),
        "tiers": tier_progress(subtotal, total_quantity),
        "min_order": MIN_ORDER_AMOUNT,
        "min_order_reached": min_order_reached(subtotal),
        "min_order_remaining": min_order_remaining(subtotal),
    }


# --- конфиг наружу ----------------------------------------------------------


def tiers_for_frontend() -> dict:
    """Конфиг скидок для JS корзины: фронт считает по той же таблице, что сервер.

    Итог всё равно пересчитывается на сервере при отправке заказа - здесь только
    то, что нужно показать человеку, пока он набирает объём.
    """
    return {
        "basis": DISCOUNT_BASIS,
        "approved": DISCOUNT_TIERS_APPROVED,
        "disclaimer": DISCOUNT_DISCLAIMER,
        "entry_percent": entry_percent(),
        "individual_text": INDIVIDUAL_TIER_TEXT,
        "individual_price_text": INDIVIDUAL_TIER_PRICE_TEXT,
        "min_order": MIN_ORDER_AMOUNT,
        "min_order_approved": MIN_ORDER_APPROVED,
        "min_order_disclaimer": MIN_ORDER_DISCLAIMER,
        "tiers": [
            {
                "key": tier["key"],
                "label": tier_label(tier),
                "short": tier.get("short", ""),
                "percent": tier.get("percent"),
                "individual": bool(tier.get("individual")),
                "min_quantity": tier.get("min_quantity"),
                "min_amount": tier.get("min_amount"),
            }
            for tier in _sorted_tiers()
        ],
    }


def tiers_for_display() -> list[dict]:
    """Строки таблицы скидок для шаблона витрины."""
    rows = []
    for tier in _sorted_tiers():
        rows.append(
            {
                "key": tier["key"],
                "label": tier_label(tier),
                "percent": tier.get("percent"),
                "individual": bool(tier.get("individual")),
                "value_text": (
                    INDIVIDUAL_TIER_PRICE_TEXT
                    if tier.get("individual")
                    else f"минус {tier.get('percent')}%"
                ),
            }
        )
    return rows


def min_order_for_display() -> dict:
    """Строка «Минимальный заказ от: N ₽» для шаблонов."""
    return {
        "amount": MIN_ORDER_AMOUNT,
        "text": f"Минимальный заказ от: {format_amount(MIN_ORDER_AMOUNT)} ₽",
        "approved": MIN_ORDER_APPROVED,
        "disclaimer": MIN_ORDER_DISCLAIMER,
    }


def tier_chip_label(tier: dict) -> str:
    """Короткая подпись ступени для ленты чипов, собранная из её порогов.

    Подписи не хардкодятся в шаблоне: поменяли пороги в DISCOUNT_TIERS - чипы
    поехали следом. Нижняя ступень по количеству (берётся с первой штуки)
    называется входной, остальные читаются по осям.
    """
    quantity = tier.get("min_quantity")
    amount = tier.get("min_amount")
    if quantity and amount:
        return f"От {format_amount(quantity)} шт или чек {format_amount(amount)} ₽"
    if quantity:
        if int(quantity) <= 1:
            return "Входная"
        return f"От {format_amount(quantity)} шт"
    if amount:
        return f"Чек от {format_amount(amount)} ₽"
    return tier_label(tier)


def tiers_for_chips() -> list[dict]:
    """Лента чипов «ступени скидки» для витрины: подпись плюс значение."""
    rows = []
    for tier in _sorted_tiers():
        individual = bool(tier.get("individual"))
        rows.append(
            {
                "key": tier["key"],
                "label": tier_chip_label(tier),
                "individual": individual,
                # У индивидуальной ступени процента нет: в чип идёт её
                # короткая подпись из сетки, длинный текст сюда не влезает.
                "value_text": (
                    (tier.get("short") or INDIVIDUAL_TIER_PRICE_TEXT)
                    if individual
                    else f"-{int(tier.get('percent') or 0)}%"
                ),
            }
        )
    return rows
