"""Тесты селектора контента: выборка периодов на ISO-неделю + fallback."""

from __future__ import annotations

import datetime as dt

import pytest

from care_notifications.content import (
    _make_summary,
    select_entries_for_week,
)


pytestmark = pytest.mark.django_db


def _make_plant(category, name, slug, periods):
    """Фабрика: создать CareCalendarPlant с набором CareCalendarPeriod."""
    from pages.models import CareCalendarPlant, CareCalendarPeriod
    plant = CareCalendarPlant.objects.create(
        name=name,
        slug=slug,
        primary_category=category,
        is_published=True,
    )
    plant.categories.add(category)
    for i, (date_label, theme, content_text) in enumerate(periods):
        CareCalendarPeriod.objects.create(
            plant=plant,
            sort_order=i,
            date_label=date_label,
            theme=theme,
            content_text=content_text,
        )
    return plant


@pytest.fixture
def rozy_category(db):
    from pages.models import CareCalendarCategory
    return CareCalendarCategory.objects.create(slug="rozy", label="Розы")


def test_summary_uses_theme_if_present():
    assert _make_summary("Формирующая обрезка", "Полный текст работ.", "") == "Формирующая обрезка"


def test_summary_falls_back_to_content_first_sentence():
    summary = _make_summary("", "Первое предложение. Второе.", "")
    assert summary == "Первое предложение"


def test_summary_truncates_long_text():
    long_text = "А" * 200
    summary = _make_summary("", long_text, "")
    assert len(summary) <= 145  # 140 + многоточие
    assert summary.endswith("…")


def test_summary_strips_html():
    summary = _make_summary("", "", "<p>HTML <b>текст</b> работ.</p>")
    assert "<" not in summary
    assert "HTML" in summary


def test_pick_period_in_week(rozy_category):
    _make_plant(rozy_category, "Брук Бэйли", "bruk-beili", [
        ("20 мая", "Обрезка", "Полная инструкция по обрезке"),
        ("10 июня", "Подкормка", "Полная инструкция по подкормке"),
    ])
    # ISO-неделя 2026-W21 = 18-24 мая
    result = select_entries_for_week(["roses"], "2026-W21")
    assert len(result) == 1
    cat = result[0]
    assert cat.category_slug == "rozy"
    assert len(cat.plants) == 1
    assert cat.plants[0].name == "Брук Бэйли"
    assert cat.plants[0].is_upcoming is False
    assert cat.plants[0].summary == "Обрезка"


def test_fallback_to_upcoming_when_week_empty(rozy_category):
    _make_plant(rozy_category, "Голден", "golden", [
        ("5 июня", "Будущая работа", "Текст"),
    ])
    # 2026-W21 = 18-24 мая, ближайшая будущая работа 5 июня (через ~2 недели)
    result = select_entries_for_week(["roses"], "2026-W21")
    assert len(result) == 1
    assert result[0].plants[0].is_upcoming is True
    assert result[0].plants[0].date_label == "5 июня"


def test_no_result_when_only_past(rozy_category):
    _make_plant(rozy_category, "Прошлогодний", "past", [
        ("10 апреля", "Прошлая работа", "Текст"),
    ])
    # На W21 (май) этого нет ни в этой неделе, ни в 4-недельном горизонте.
    result = select_entries_for_week(["roses"], "2026-W21")
    assert result == []


def test_seasonal_group_ignored(rozy_category):
    # seasonal не имеет category_slugs - блока не должно быть
    result = select_entries_for_week(["seasonal"], "2026-W21")
    assert result == []


def test_unknown_group_silently_skipped(rozy_category):
    result = select_entries_for_week(["unknown_group"], "2026-W21")
    assert result == []


def test_multiple_plants_in_same_week(rozy_category):
    _make_plant(rozy_category, "Сорт A", "sort-a", [("20 мая", "Обрезка A", "")])
    _make_plant(rozy_category, "Сорт B", "sort-b", [("22 мая", "Обрезка B", "")])
    _make_plant(rozy_category, "Сорт C", "sort-c", [("10 июня", "Подкормка C", "")])
    result = select_entries_for_week(["roses"], "2026-W21")
    assert len(result) == 1
    names = {p.name for p in result[0].plants}
    assert names == {"Сорт A", "Сорт B"}
    assert all(p.is_upcoming is False for p in result[0].plants)


def test_unpublished_plants_skipped(rozy_category):
    from pages.models import CareCalendarPlant, CareCalendarPeriod
    plant = CareCalendarPlant.objects.create(
        name="Черновик", slug="cher", primary_category=rozy_category, is_published=False,
    )
    plant.categories.add(rozy_category)
    CareCalendarPeriod.objects.create(plant=plant, date_label="20 мая", theme="Скрытый")
    result = select_entries_for_week(["roses"], "2026-W21")
    assert result == []


def test_unparseable_date_label_skipped(rozy_category):
    """Период с невалидным date_label попадает в лог warning и игнорируется."""
    plant = _make_plant(rozy_category, "Сорт", "sort", [
        ("какая-то ерунда", "Тема", ""),
        ("20 мая", "Нормальная тема", ""),
    ])
    result = select_entries_for_week(["roses"], "2026-W21")
    # Один период с валидной датой проходит
    assert len(result) == 1
    assert len(result[0].plants) == 1
    assert result[0].plants[0].summary == "Нормальная тема"


def test_week_key_uses_local_monday_boundary():
    """Граница недели - по локальному времени UTC+7 (Новосибирск/Красноярск),
    а не по UTC. Момент, который в UTC ещё воскресенье, но по Новосибирску уже
    понедельник, должен попадать в НОВУЮ ISO-неделю."""
    from care_notifications.digest import get_current_week_key

    # Вс 2026-05-24 20:00 UTC = Пн 2026-05-25 03:00 по UTC+7
    utc_instant = dt.datetime(2026, 5, 24, 20, 0, tzinfo=dt.timezone.utc)
    local_monday = dt.date(2026, 5, 25).isocalendar()  # понедельник по локали
    utc_sunday = dt.date(2026, 5, 24).isocalendar()     # воскресенье по UTC
    assert utc_sunday.week != local_monday.week         # разные ISO-недели
    assert get_current_week_key(utc_instant) == f"{local_monday.year}-W{local_monday.week:02d}"
