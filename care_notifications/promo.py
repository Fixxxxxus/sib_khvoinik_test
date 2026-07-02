"""Гейтинг промо-акции недели для дайджеста.

Промо от СММ (модель WeeklyPromo) подмешивается в дайджест ТОЛЬКО когда:
1) специалист подтвердил акцию (status == confirmed), и
2) подписчик согласен на блок «новинки и акции» (promo_subscribed).

Живёт отдельным модулем, чтобы build_payload оставался читаемым и чтобы гейт
легко тестировался в изоляции.
"""

from __future__ import annotations

from .models import CareSubscription, WeeklyPromo


def active_promo_for_week(week_key: str) -> "WeeklyPromo | None":
    """Подтверждённое промо недели или None."""
    return WeeklyPromo.objects.filter(
        week_key=week_key, status=WeeklyPromo.STATUS_CONFIRMED
    ).first()


def promo_for_payload(
    subscription: CareSubscription, week_key: str, site_url: str
) -> tuple[str | None, str | None]:
    """(text, absolute_image_url) для дайджеста, если подписчик согласен и промо подтверждено.

    Абсолютный URL картинки нужен всем каналам одинаково: Telegram (Contabo)
    качает его с gazony.ru, email/MAX ссылаются на него в теле сообщения.
    """
    if not subscription.promo_subscribed:
        return None, None
    promo = active_promo_for_week(week_key)
    if promo is None:
        return None, None
    image_url = None
    if promo.image:
        image_url = site_url.rstrip("/") + promo.image.url
    return (promo.text or None), image_url
