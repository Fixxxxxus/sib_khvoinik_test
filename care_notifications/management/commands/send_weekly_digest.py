"""Оркестратор еженедельного дайджеста.

Использование на проде (через cron):
  docker compose exec -T web python manage.py send_weekly_digest

Флаги:
  --dry-run            ничего не шлёт, только печатает что бы отправилось
  --week 2026-W21      ISO-неделя выпуска (по умолчанию текущая)
  --channel email|telegram|max|all   фильтр канала (по умолчанию all)
  --subscription-id N  только одну подписку (для отладки)

Идемпотентность: на каждую тройку (подписка, канал, week_key) пишем DigestDelivery
с unique_together. Если запись с тем же ключом уже sent - пропускаем без повторной
отправки.
"""

from __future__ import annotations

import logging
import os
import time

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone

from care_notifications.digest import build_payload, get_current_week_key
from care_notifications.models import CareSubscription, DigestDelivery


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Рассылает еженедельный дайджест Службы заботы по подписчикам."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--week", type=str, default=None)
        parser.add_argument(
            "--channel",
            type=str,
            default="all",
            choices=["all", "email", "telegram", "max"],
        )
        parser.add_argument("--subscription-id", type=int, default=None)
        parser.add_argument(
            "--throttle-ms",
            type=int,
            default=120,
            help="Пауза между отправками, мс (антиспам).",
        )

    def handle(self, *args, **opts):
        week_key = opts["week"] or get_current_week_key()
        channel_filter = opts["channel"]
        dry_run = opts["dry_run"]
        throttle = max(0, int(opts["throttle_ms"])) / 1000.0

        qs = CareSubscription.objects.filter(active=True)
        if opts["subscription_id"]:
            qs = qs.filter(pk=opts["subscription_id"])
        if channel_filter != "all":
            qs = qs.filter(preferred_channel=channel_filter)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"[digest] week={week_key} channel={channel_filter} subs={total} dry_run={dry_run}"
        ))
        if total == 0:
            self.stdout.write("(нет активных подписчиков под фильтром, выходим)")
            return

        # Ленивая инициализация клиентов, чтобы при dry_run не падать из-за пустых env-ключей.
        tg_client = None
        un_client = None

        sent = failed = skipped = 0
        for sub in qs.iterator(chunk_size=200):
            payload = build_payload(sub, week_key=week_key)
            ch = sub.preferred_channel
            if not payload.blocks and not payload.hero_text:
                self.stdout.write(self.style.WARNING(f"  sub={sub.id} ch={ch} пустой payload, skip"))
                skipped += 1
                self._record(sub, ch, week_key, DigestDelivery.STATUS_SKIPPED, "empty payload", dry_run)
                continue

            if dry_run:
                self.stdout.write(
                    f"  [dry] sub={sub.id} ch={ch} subject={payload.subject!r} "
                    f"blocks={len(payload.blocks)} hero_img={'yes' if payload.hero_image_path else 'no'}"
                )
                continue

            already = (
                DigestDelivery.objects.filter(
                    subscription=sub, channel=ch, week_key=week_key,
                    status=DigestDelivery.STATUS_SENT,
                ).exists()
            )
            if already:
                self.stdout.write(f"  sub={sub.id} ch={ch} уже отправлено в эту неделю, skip")
                skipped += 1
                continue

            try:
                if ch == "email":
                    if un_client is None:
                        from care_notifications.unisender import UnisenderClient
                        un_client = UnisenderClient()
                    if not sub.email:
                        self._record(sub, ch, week_key, DigestDelivery.STATUS_SKIPPED, "no email on subscription", dry_run)
                        skipped += 1
                        continue
                    res = un_client.send_digest_email(sub, payload)
                elif ch == "telegram":
                    if tg_client is None:
                        from care_notifications.telegram_bot import TelegramBotClient
                        tg_client = TelegramBotClient()
                    if not sub.telegram_chat_id:
                        self._record(sub, ch, week_key, DigestDelivery.STATUS_SKIPPED, "no telegram_chat_id (opt-in не пройден)", dry_run)
                        skipped += 1
                        continue
                    res = tg_client.send_digest(sub, payload)
                elif ch == "max":
                    self._record(sub, ch, week_key, DigestDelivery.STATUS_SKIPPED, "MAX-канал ещё не подключён", dry_run)
                    skipped += 1
                    continue
                else:
                    self._record(sub, ch, week_key, DigestDelivery.STATUS_SKIPPED, f"unknown channel {ch}", dry_run)
                    skipped += 1
                    continue

                if res.get("ok"):
                    ext = str(res.get("email_id") or res.get("message_id") or "")
                    self._record(sub, ch, week_key, DigestDelivery.STATUS_SENT, "", dry_run, external_id=ext)
                    sub.last_digest_sent_at = timezone.now()
                    sub.save(update_fields=["last_digest_sent_at", "updated_at"])
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f"  sub={sub.id} ch={ch} sent (id={ext})"))
                else:
                    err = str(res.get("error") or "unknown")[:500]
                    self._record(sub, ch, week_key, DigestDelivery.STATUS_FAILED, err, dry_run)
                    failed += 1
                    self.stdout.write(self.style.ERROR(f"  sub={sub.id} ch={ch} FAILED: {err}"))
            except Exception as e:
                logger.exception("send_weekly_digest sub=%s ch=%s error", sub.id, ch)
                self._record(sub, ch, week_key, DigestDelivery.STATUS_FAILED, str(e)[:500], dry_run)
                failed += 1

            if throttle:
                time.sleep(throttle)

        self.stdout.write(self.style.SUCCESS(
            f"[digest] done week={week_key} sent={sent} failed={failed} skipped={skipped}"
        ))

    def _record(self, subscription, channel, week_key, status, error, dry_run, external_id=""):
        if dry_run:
            return
        try:
            with transaction.atomic():
                DigestDelivery.objects.update_or_create(
                    subscription=subscription,
                    channel=channel,
                    week_key=week_key,
                    defaults={"status": status, "error": error, "external_id": external_id},
                )
        except IntegrityError:
            logger.warning("DigestDelivery integrity conflict sub=%s ch=%s wk=%s", subscription.id, channel, week_key)
