"""Рендер карточек Службы заботы за неделю в MEDIA/care_cards/<week>/."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from care_notifications.cards.builder import build_week_cards
from care_notifications.digest import get_current_week_key


class Command(BaseCommand):
    help = "Сгенерировать PNG-карточки Службы заботы за неделю."

    def add_arguments(self, parser):
        parser.add_argument("--week", default=None, help="ISO-неделя, напр. 2026-W27")
        parser.add_argument("--force", action="store_true", help="Перерисовать, игнорируя манифест")

    def handle(self, *args, **opts):
        week = opts["week"] or get_current_week_key()
        man = build_week_cards(week, force=opts["force"])
        cats = ", ".join(man["categories"]) or "(пусто)"
        promo = "есть" if man.get("promo") else "нет"
        self.stdout.write(self.style.SUCCESS(
            f"Неделя {week}, сезон {man['season']}: категории [{cats}], промо {promo}"))
