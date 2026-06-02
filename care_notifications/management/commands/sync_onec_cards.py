"""Дослыка цифровых карт в 1С:УНФ (задача Б24 #1231).

Берёт записи OneCCardSync в статусе pending и пробует отправить их в 1С повторно.
Нужна потому, что прямая отправка из формы best-effort: если в момент оформления
1С была недоступна, запись осталась pending - эта команда добивает её по крону.

Использование на проде (через cron):
  docker compose exec -T web python manage.py sync_onec_cards

Флаги:
  --dry-run            ничего не шлёт, только печатает что бы отправилось
  --limit N            максимум записей за прогон (по умолчанию 200)
  --max-attempts N     после стольких неудачных попыток помечаем failed (по умолчанию 5)

1С делает upsert по телефону, поэтому повторная отправка дубля не плодит - ретраи
безопасны.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from care_notifications.models import OneCCardSync
from care_notifications.onec import OneCClient, OneCError, mask_phone


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Дослыка pending-карт лояльности в 1С:УНФ."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--max-attempts", type=int, default=5)

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        limit = opts["limit"]
        max_attempts = opts["max_attempts"]

        client = OneCClient()
        if not client.is_configured():
            self.stderr.write("ONEC_GETCARD_URL/USER/PASSWORD не заданы - 1С-синхронизация выключена, выходим.")
            return

        jobs = list(
            OneCCardSync.objects.filter(status=OneCCardSync.STATUS_PENDING).order_by("created_at")[:limit]
        )
        if not jobs:
            self.stdout.write("Нет pending-карт для отправки в 1С.")
            return

        sent = failed = retried = 0
        for job in jobs:
            # В логах только pk + маскированный телефон, без ФИО и без str(e)
            # (текст ошибки содержит URL с ПДн; детали - в job.last_error/админке).
            label = f"#{job.pk} {mask_phone(job.phone)}"
            if dry_run:
                self.stdout.write(f"[dry-run] отправил бы {label} (попыток уже {job.attempts})")
                continue
            try:
                client.register_card(
                    phone=job.phone,
                    first_name=job.first_name,
                    last_name=job.last_name,
                    middle_name=job.middle_name,
                )
            except OneCError as e:
                job.attempts += 1
                job.last_error = str(e)[:2000]
                if job.attempts >= max_attempts:
                    job.status = OneCCardSync.STATUS_FAILED
                    failed += 1
                    logger.error("sync_onec_cards: %s исчерпала попытки (%s)", label, job.attempts)
                else:
                    retried += 1
                    logger.warning("sync_onec_cards: %s попытка %s не удалась", label, job.attempts)
                job.save(update_fields=["status", "attempts", "last_error", "updated_at"])
                continue
            job.status = OneCCardSync.STATUS_SENT
            job.attempts += 1
            job.sent_at = timezone.now()
            job.save(update_fields=["status", "attempts", "sent_at", "updated_at"])
            sent += 1

        self.stdout.write(
            f"1С-дослыка: отправлено {sent}, повторим позже {retried}, провалено окончательно {failed} "
            f"(всего обработано {len(jobs)})."
        )
