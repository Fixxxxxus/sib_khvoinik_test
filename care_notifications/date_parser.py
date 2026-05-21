"""Парсер строк CareCalendarPeriod.date_label в (start_date, end_date).

В Yonote агроном пишет даты как «20 апреля», «15 - 25 мая», «20 апреля - 5 мая».
Дайджесту нужны конкретные date-объекты, чтобы понять, пересекает ли период
данную ISO-неделю. Этот модуль чистый, без зависимостей от Django.

Контракт:
    parse_date_label("15 - 25 апреля", year=2026) -> (date(2026,4,15), date(2026,4,25))
    parse_date_label("20 апреля - 5 мая", year=2026) -> (date(2026,4,20), date(2026,5,5))
    parse_date_label("20 апреля", year=2026) -> (date(2026,4,20), date(2026,4,20))
    parse_date_label("25сентября - 15 октября", year=2026) -> (date(2026,9,25), date(2026,10,15))
    parse_date_label("каждые 2 недели", year=2026) -> None

Непарсимые строки возвращают None, чтобы вызывающий код мог их залогировать и
пропустить, а не упасть. Список поддерживаемых форматов покрывает все 268
уникальных date_label в текущей выгрузке из Yonote (см. test_date_parser.py).
"""

from __future__ import annotations

import datetime as dt
import re


_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

# Любой типографский дефис: ASCII '-', en-dash '–' (U+2013), em-dash '—' (U+2014).
_DASH = r"[-–—]"

# Опечатка вида «25сентября» (без пробела) - вставляем пробел перед месяцем.
_GLUED_DAY_MONTH = re.compile(r"(\d{1,2})([а-яё]+)", re.IGNORECASE)

# «20 апреля» либо «20 апреля,» - одиночная дата.
_SINGLE = re.compile(
    rf"^\s*(\d{{1,2}})\s+([а-яё]+)\s*$", re.IGNORECASE
)
# «15 - 25 апреля» - оба числа в одном месяце.
_RANGE_SAME_MONTH = re.compile(
    rf"^\s*(\d{{1,2}})\s*{_DASH}\s*(\d{{1,2}})\s+([а-яё]+)\s*$", re.IGNORECASE
)
# «20 апреля - 5 мая» - диапазон через месяцы.
_RANGE_CROSS_MONTH = re.compile(
    rf"^\s*(\d{{1,2}})\s+([а-яё]+)\s*{_DASH}\s*(\d{{1,2}})\s+([а-яё]+)\s*$",
    re.IGNORECASE,
)


def _normalize(label: str) -> str:
    """Чистим: вставляем пробел в «25сентября», убираем двойные пробелы."""
    s = (label or "").strip().lower()
    # Лечим опечатку «25сентября» - только если за числом сразу идёт известный месяц
    # без пробела. Не трогаем диапазоны, в которых дефис сразу за числом.
    def _fix(m: re.Match[str]) -> str:
        day, word = m.group(1), m.group(2)
        if word in _MONTHS:
            return f"{day} {word}"
        return m.group(0)
    s = _GLUED_DAY_MONTH.sub(_fix, s)
    s = re.sub(r"\s+", " ", s)
    return s


def _make_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_date_label(label: str, year: int) -> tuple[dt.date, dt.date] | None:
    """Парсит подпись даты в (start, end) для указанного года.

    Возвращает None, если строка не соответствует ни одному поддерживаемому
    формату. Год нужен потому, что в Yonote даты пишутся без года - календарь
    работает в режиме «фенологический», повторяясь каждый сезон.
    """
    if not label:
        return None
    s = _normalize(label)

    m = _RANGE_CROSS_MONTH.match(s)
    if m:
        d1, mo1, d2, mo2 = m.group(1), m.group(2), m.group(3), m.group(4)
        if mo1 in _MONTHS and mo2 in _MONTHS:
            start = _make_date(year, _MONTHS[mo1], int(d1))
            end = _make_date(year, _MONTHS[mo2], int(d2))
            if start and end and end >= start:
                return start, end
        return None

    m = _RANGE_SAME_MONTH.match(s)
    if m:
        d1, d2, mo = m.group(1), m.group(2), m.group(3)
        if mo in _MONTHS:
            start = _make_date(year, _MONTHS[mo], int(d1))
            end = _make_date(year, _MONTHS[mo], int(d2))
            if start and end and end >= start:
                return start, end
        return None

    m = _SINGLE.match(s)
    if m:
        d, mo = m.group(1), m.group(2)
        if mo in _MONTHS:
            day = _make_date(year, _MONTHS[mo], int(d))
            if day:
                return day, day
        return None

    return None


def iso_week_range(week_key: str) -> tuple[dt.date, dt.date] | None:
    """ISO-неделя вида '2026-W21' -> (понедельник, воскресенье) этой недели."""
    if not week_key or "-W" not in week_key:
        return None
    year_str, _, num_str = week_key.partition("-W")
    if not (year_str.isdigit() and num_str.isdigit()):
        return None
    try:
        monday = dt.date.fromisocalendar(int(year_str), int(num_str), 1)
    except ValueError:
        return None
    sunday = monday + dt.timedelta(days=6)
    return monday, sunday


def overlaps(period: tuple[dt.date, dt.date], window: tuple[dt.date, dt.date]) -> bool:
    """Период и окно недели пересекаются по дате."""
    p_start, p_end = period
    w_start, w_end = window
    return p_start <= w_end and p_end >= w_start
