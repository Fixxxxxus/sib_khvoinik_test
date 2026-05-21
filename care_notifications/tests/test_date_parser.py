"""Тест парсера date_label.

Покрывает все 4 шаблона из corpus pages/calendar_data.py + опечатку без пробела
+ непарсимые строки. Год фиксированный (2026), чтобы тесты были детерминированными.
"""

from __future__ import annotations

import datetime as dt

from care_notifications.date_parser import (
    iso_week_range,
    overlaps,
    parse_date_label,
)


YEAR = 2026


def _d(month: int, day: int) -> dt.date:
    return dt.date(YEAR, month, day)


def test_single_day():
    assert parse_date_label("20 апреля", YEAR) == (_d(4, 20), _d(4, 20))
    assert parse_date_label("1 мая", YEAR) == (_d(5, 1), _d(5, 1))
    assert parse_date_label("31 декабря", YEAR) == (_d(12, 31), _d(12, 31))


def test_range_same_month_ascii_dash():
    assert parse_date_label("15 - 25 апреля", YEAR) == (_d(4, 15), _d(4, 25))


def test_range_same_month_en_dash():
    # en-dash U+2013, в corpus встречается чаще ASCII '-'
    assert parse_date_label("15 – 25 апреля", YEAR) == (_d(4, 15), _d(4, 25))


def test_range_cross_month():
    assert parse_date_label("20 апреля – 5 мая", YEAR) == (_d(4, 20), _d(5, 5))
    assert parse_date_label("25 апреля - 15 мая", YEAR) == (_d(4, 25), _d(5, 15))


def test_glued_typo():
    """В corpus встречается '25сентября - 15 октября' без пробела."""
    assert parse_date_label("25сентября – 15 октября", YEAR) == (_d(9, 25), _d(10, 15))


def test_case_insensitive():
    assert parse_date_label("20 АПРЕЛЯ", YEAR) == (_d(4, 20), _d(4, 20))


def test_unparseable_returns_none():
    assert parse_date_label("каждые 2 недели", YEAR) is None
    assert parse_date_label("в течение сезона", YEAR) is None
    assert parse_date_label("", YEAR) is None
    assert parse_date_label("32 апреля", YEAR) is None  # некорректная дата
    assert parse_date_label("20 фантября", YEAR) is None  # незнакомый месяц


def test_reversed_range_returns_none():
    # Конец раньше начала - значит парсер ошибся, возвращаем None
    assert parse_date_label("25 - 15 апреля", YEAR) is None


def test_iso_week_range():
    assert iso_week_range("2026-W21") == (dt.date(2026, 5, 18), dt.date(2026, 5, 24))
    assert iso_week_range("2026-W01") == (dt.date(2025, 12, 29), dt.date(2026, 1, 4))
    assert iso_week_range("garbage") is None
    assert iso_week_range("2026-W99") is None


def test_overlaps():
    week = (dt.date(2026, 5, 18), dt.date(2026, 5, 24))
    # точно в неделе
    assert overlaps((dt.date(2026, 5, 20), dt.date(2026, 5, 20)), week)
    # диапазон пересекает конец недели
    assert overlaps((dt.date(2026, 5, 22), dt.date(2026, 5, 30)), week)
    # диапазон полностью охватывает неделю
    assert overlaps((dt.date(2026, 5, 1), dt.date(2026, 6, 1)), week)
    # неделя левее периода
    assert not overlaps((dt.date(2026, 6, 1), dt.date(2026, 6, 7)), week)
    # неделя правее периода
    assert not overlaps((dt.date(2026, 4, 1), dt.date(2026, 4, 7)), week)


def test_corpus_smoke():
    """Smoke: все 268 уникальных date_label из current corpus парсятся.

    Если этот тест падает - в Yonote появился новый формат. Нужно расширить
    парсер либо попросить агронома привести запись к одному из поддерживаемых.
    """
    from pages.calendar_data import CALENDAR_PERIODS
    # Известные опечатки агронома в Yonote, которые парсер сознательно отвергает
    # (конец диапазона раньше начала - явная ошибка ввода, попадание в дайджест
    # такой записи дало бы непредсказуемое окно). Когда агроном поправит -
    # удалить отсюда.
    known_typos = {"25 июля – 15 июля"}
    unparsed = []
    for label in CALENDAR_PERIODS:
        if parse_date_label(label, YEAR) is None and label not in known_typos:
            unparsed.append(label)
    assert not unparsed, f"unparseable date_labels: {unparsed[:10]} (всего {len(unparsed)})"
