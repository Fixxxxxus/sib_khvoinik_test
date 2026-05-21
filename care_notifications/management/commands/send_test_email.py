"""Отправить тестовый email-дайджест через Unisender.

Использование:
  python manage.py send_test_email --to drtloki@gmail.com
  python manage.py send_test_email --to drtloki@gmail.com --groups seasonal,roses
  python manage.py send_test_email --to test@example.com --dry-run

Создаёт временную CareSubscription (нужна для генерации manage/unsubscribe
ссылок и для контракта build_payload), отправляет письмо и удаляет подписку.
В --dry-run режиме письмо не уходит, печатается только HTML.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from care_notifications.digest import build_payload, render_email
from care_notifications.models import CareSubscription
from care_notifications.unisender import UnisenderClient, UnisenderError


class Command(BaseCommand):
    help = "Шлёт тестовый email-дайджест через Unisender (или печатает HTML в --dry-run)."

    def add_arguments(self, parser):
        parser.add_argument("--to", type=str, required=True, help="Email получателя.")
        parser.add_argument(
            "--groups",
            type=str,
            default="seasonal,roses,perennials",
            help="csv slug'ов групп подписки, например seasonal,roses,perennials.",
        )
        parser.add_argument(
            "--week",
            type=str,
            default=None,
            help="ISO неделя, например 2026-W21. По умолчанию текущая.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не отправлять, только напечатать HTML.",
        )

    def handle(self, *args, **opts):
        to_email: str = opts["to"]
        slugs = [s.strip() for s in opts["groups"].split(",") if s.strip()]
        dry_run: bool = opts["dry_run"]

        sub = CareSubscription(
            name="Тестовый получатель",
            email=to_email,
            preferred_channel="email",
            groups=slugs,
            source="web",
        )
        sub.save()
        self.stdout.write(self.style.NOTICE(f"создана временная подписка id={sub.id} email={to_email} groups={slugs}"))

        try:
            payload = build_payload(sub, week_key=opts["week"])
            if payload is None:
                self.stdout.write(self.style.WARNING("[skip] нет контента на эту неделю"))
                return

            if dry_run:
                self.stdout.write(self.style.MIGRATE_HEADING("\n===== DRY RUN: HTML письма =====\n"))
                self.stdout.write(render_email(payload))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n[dry-run] subject={payload.subject!r} blocks={len(payload.blocks)} week={payload.week_key}"
                    )
                )
                return

            client = UnisenderClient()
            try:
                result = client.send_digest_email(sub, payload)
            except UnisenderError as exc:
                self.stderr.write(self.style.ERROR(f"UnisenderError: {exc}"))
                return

            if result.get("ok"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ok] отправлено в {to_email}, email_id={result.get('email_id')}, subject={payload.subject!r}"
                    )
                )
            else:
                self.stderr.write(self.style.ERROR(f"[fail] {result.get('error')}"))
        finally:
            sub.delete()
            self.stdout.write(self.style.NOTICE("временная подписка удалена"))
