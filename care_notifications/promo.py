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
    """Промо недели для дайджеста: confirmed или уже sent.

    sent включаем сюда намеренно: send_weekly_digest переводит промо
    confirmed -> sent на первом хосте, который его залочит (email/MAX-крон).
    Telegram-дайджест собирается на отдельном хосте (Contabo) тем же кроном
    и читает промо через этот же гейт - если оставить только confirmed, он
    молча потеряет промо, если email-крон успел раньше. Для ЧТЕНИЯ sent -
    всё ещё "промо этой недели"; редактирование (promo_edit/promo_confirm)
    по-прежнему блокируется на sent отдельно, это не трогаем.
    """
    return WeeklyPromo.objects.filter(
        week_key=week_key,
        status__in=[WeeklyPromo.STATUS_CONFIRMED, WeeklyPromo.STATUS_SENT],
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
