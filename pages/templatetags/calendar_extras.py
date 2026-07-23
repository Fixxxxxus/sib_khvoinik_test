"""Шаблонные фильтры календаря ухода."""

from __future__ import annotations

from django import template
from django.utils import timezone

from care_notifications.date_parser import parse_date_label

register = template.Library()


def _label_of(period) -> str:
    if isinstance(period, dict):
        return (period.get("date_label") or "").strip()
    return (getattr(period, "date_label", "") or "").strip()


@register.filter
def current_period(periods):
    """Период, в диапазон дат которого попадает сегодня (иначе None).

    Ожидает итерабельный список периодов (dict с ключом ``date_label`` или
    объект с атрибутом ``date_label``). Диапазоны, пересекающие границу года
    (напр. «25 декабря - 10 января»), считаются текущими, если сегодня после
    старта ИЛИ до конца. Первый подходящий период и возвращается.
    """
    if not periods:
        return None
    today = timezone.localdate()
    for per in periods:
        label = _label_of(per)
        if not label:
            continue
        rng = parse_date_label(label, year=today.year)
        if not rng:
            continue
        start, end = rng
        if start <= end:
            if start <= today <= end:
                return per
        elif today >= start or today <= end:  # диапазон через Новый год
            return per
    return None
