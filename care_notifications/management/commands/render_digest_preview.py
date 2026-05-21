"""Отрисовать дайджест в консоль для отладки.

Использование:
  python manage.py render_digest_preview --groups seasonal,roses,perennials --channel email
  python manage.py render_digest_preview --subscription-id 1 --channel telegram
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from care_notifications.digest import (
    build_payload,
    render_email,
    render_max,
    render_telegram,
)
from care_notifications.models import CareSubscription


class Command(BaseCommand):
    help = "Печатает рендер дайджеста для отладки шаблонов."

    def add_arguments(self, parser):
        parser.add_argument("--subscription-id", type=int, default=None)
        parser.add_argument(
            "--groups",
            type=str,
            default="seasonal,roses,perennials",
            help="csv slug'ов, используется если --subscription-id не задан",
        )
        parser.add_argument(
            "--channel",
            type=str,
            default="email",
            choices=["email", "telegram", "max", "all"],
        )
        parser.add_argument("--week", type=str, default=None, help="ISO неделя, например 2026-W21")

    def handle(self, *args, **opts):
        if opts["subscription_id"]:
            try:
                sub = CareSubscription.objects.get(pk=opts["subscription_id"])
            except CareSubscription.DoesNotExist as e:
                raise CommandError(f"Подписка id={opts['subscription_id']} не найдена") from e
        else:
            slugs = [s.strip() for s in opts["groups"].split(",") if s.strip()]
            sub = CareSubscription(
                name="Preview",
                phone="+70000000000",
                email="preview@example.com",
                preferred_channel="email",
                groups=slugs,
                source="web",
            )
            sub.save()
            self.stdout.write(self.style.NOTICE(f"created temp subscription id={sub.id}"))

        payload = build_payload(sub, week_key=opts["week"])
        if payload is None:
            self.stdout.write(self.style.WARNING("[skip] нет контента на эту неделю для выбранных групп"))
            if not opts["subscription_id"]:
                sub.delete()
            return
        ch = opts["channel"]
        if ch in ("email", "all"):
            self.stdout.write(self.style.MIGRATE_HEADING("\n========= EMAIL HTML =========\n"))
            self.stdout.write(render_email(payload))
        if ch in ("telegram", "all"):
            self.stdout.write(self.style.MIGRATE_HEADING("\n========= TELEGRAM =========\n"))
            self.stdout.write(render_telegram(payload))
        if ch in ("max", "all"):
            self.stdout.write(self.style.MIGRATE_HEADING("\n========= MAX =========\n"))
            self.stdout.write(render_max(payload))

        self.stdout.write(self.style.SUCCESS(f"\n[ok] week={payload.week_key} season={payload.season_label} blocks={len(payload.blocks)}"))

        if not opts["subscription_id"]:
            sub.delete()
            self.stdout.write(self.style.NOTICE("temp subscription deleted"))
