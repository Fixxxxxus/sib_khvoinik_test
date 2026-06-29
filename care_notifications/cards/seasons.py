"""Определение сезона по дате в TZ Asia/Krasnoyarsk (сибирский сдвиг)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Krasnoyarsk")

MONTH_TO_SEASON = {
    1: "winter", 2: "winter", 3: "winter",
    4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn",
    11: "winter", 12: "winter",
}


def season_for_date(d: dt.date | None = None) -> str:
    """Сезон для даты (по умолчанию - сегодня в TZ Asia/Krasnoyarsk)."""
    if d is None:
        d = dt.datetime.now(TZ).date()
    return MONTH_TO_SEASON[d.month]
