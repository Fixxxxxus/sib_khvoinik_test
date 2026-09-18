"""Офлайн-конверсии в Яндекс.Метрику по yclid.

Зачем. Счётчик на сайте поднимается только после согласия на cookie, поэтому
часть рекламных заявок Метрика не видит вовсе. Но yclid из ссылки объявления мы
сохраняем в БД всегда, а Метрика умеет принимать конверсии задним числом по
этому же yclid. Команда раз в час досылает то, что счётчик пропустил.

Что шлём:
  LandingLead     -> цель lead_submit (без цены);
  WholesaleOrder  -> цель opt_order, цена - итог заказа, валюта RUB.

API: POST https://api-metrika.yandex.net/management/v1/counter/<id>/
     offline_conversions/upload?client_id_type=YCLID
Тело - multipart, поле file, CSV с заголовком Yclid,Target,DateTime,Price,Currency.
DateTime - unix timestamp. Авторизация - заголовок Authorization: OAuth <токен>.

Запуск:
    python manage.py push_metrika_conversions [--since-hours 48] [--dry-run]

Без токена команда печатает причину и выходит с кодом 0: на проде токен
появляется отдельно, и отсутствие токена не должно ронять почасовой cron.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from pages.models import LandingLead, WholesaleOrder

logger = logging.getLogger(__name__)

UPLOAD_URL = "https://api-metrika.yandex.net/management/v1/counter/{counter_id}/offline_conversions/upload"
CSV_HEADER = ["Yclid", "Target", "DateTime", "Price", "Currency"]
LEAD_GOAL = "lead_submit"
ORDER_GOAL = "opt_order"
CURRENCY = "RUB"
TIMEOUT = 20


def _rows_for(leads, orders) -> list[list[str]]:
    """Строки CSV в том же порядке, в каком их отдали выборки."""
    rows: list[list[str]] = []
    for lead in leads:
        rows.append([
            lead.yclid,
            LEAD_GOAL,
            str(int(lead.created_at.timestamp())),
            "",
            "",
        ])
    for order in orders:
        rows.append([
            order.yclid,
            ORDER_GOAL,
            str(int(order.created_at.timestamp())),
            f"{order.total:.2f}",
            CURRENCY,
        ])
    return rows


def build_csv(leads, orders) -> str:
    """CSV для API офлайн-конверсий. Пустая выборка даёт пустую строку."""
    rows = _rows_for(leads, orders)
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    writer.writerows(rows)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Досылает заявки и оптовые заказы с yclid в Метрику как офлайн-конверсии."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since-hours",
            type=int,
            default=48,
            help="За сколько часов назад брать записи (по умолчанию 48).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Напечатать CSV и выйти: ничего не отправлять и не отмечать.",
        )

    def handle(self, *args, **options):
        since_hours = options["since_hours"]
        dry_run = options["dry_run"]

        token = (getattr(settings, "YANDEX_METRIKA_ACCESS_TOKEN", "") or "").strip()
        counter_id = (getattr(settings, "YANDEX_METRIKA_COUNTER_ID", "") or "").strip()

        if not token and not dry_run:
            self.stdout.write(
                "YANDEX_METRIKA_ACCESS_TOKEN не задан: офлайн-конверсии не отправляются. "
                "Положите OAuth-токен в .env и перезапустите контейнеры."
            )
            return

        since = timezone.now() - timedelta(hours=since_hours)
        leads = list(
            LandingLead.objects.filter(
                created_at__gte=since, metrika_uploaded_at__isnull=True
            ).exclude(yclid="").order_by("created_at", "pk")
        )
        orders = list(
            WholesaleOrder.objects.filter(
                created_at__gte=since, metrika_uploaded_at__isnull=True
            ).exclude(yclid="").order_by("created_at", "pk")
        )

        payload = build_csv(leads, orders)
        if not payload:
            self.stdout.write(f"Нечего отправлять: за последние {since_hours} ч нет записей с yclid.")
            return

        if dry_run:
            self.stdout.write(payload)
            self.stdout.write(
                f"dry-run: {len(leads)} заявок и {len(orders)} заказов, ничего не отправлено."
            )
            return

        url = UPLOAD_URL.format(counter_id=counter_id)
        try:
            response = requests.post(
                url,
                params={"client_id_type": "YCLID"},
                headers={"Authorization": f"OAuth {token}"},
                files={"file": ("conversions.csv", payload.encode("utf-8"), "text/csv")},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("push_metrika_conversions: сеть недоступна: %s", exc)
            self.stderr.write(f"Метрика недоступна, отметку не ставим: {exc}")
            return

        if response.status_code >= 400:
            logger.warning(
                "push_metrika_conversions: Метрика ответила %s: %s",
                response.status_code,
                response.text[:500],
            )
            self.stderr.write(
                f"Метрика ответила {response.status_code}, отметку не ставим: {response.text[:300]}"
            )
            return

        try:
            uploading = (response.json() or {}).get("uploading") or {}
        except ValueError:
            uploading = {}
        logger.info(
            "push_metrika_conversions: загрузка id=%s status=%s, строк %s",
            uploading.get("id"),
            uploading.get("status"),
            len(leads) + len(orders),
        )

        now = timezone.now()
        if leads:
            LandingLead.objects.filter(pk__in=[x.pk for x in leads]).update(metrika_uploaded_at=now)
        if orders:
            WholesaleOrder.objects.filter(pk__in=[x.pk for x in orders]).update(metrika_uploaded_at=now)

        self.stdout.write(
            f"Отправлено в Метрику: {len(leads)} заявок, {len(orders)} заказов. "
            f"Загрузка id={uploading.get('id')} status={uploading.get('status')}."
        )
