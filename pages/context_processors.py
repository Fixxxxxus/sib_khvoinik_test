"""Глобальный контекст шаблонов."""

from __future__ import annotations

from django.utils import timezone

from pages.data import MEGA_SEASON


def garden_centers(request) -> dict:
    """Сезонный статус садового центра у ТЦ МЕГА (см. MEGA_SEASON в data.py)."""
    closed_from = MEGA_SEASON.get("closed_from")
    today = timezone.localdate()
    closed = bool(closed_from and today >= closed_from)
    return {
        "mega_season": {
            "closed": closed,
            "closing": bool(closed_from and not closed),
            "last_day": MEGA_SEASON.get("last_day", ""),
        }
    }
