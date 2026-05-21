"""Long-polling воркер Telegram-бота Службы заботы.

Запуск:
    python manage.py run_telegram_bot

Поддерживает:
- deep-link `/start <token>` для привязки telegram_chat_id к подписке;
- команду `/unsubscribe` (текстом) для отписки;
- inline-кнопку «Отписаться» с callback_data вида `unsub:<token>`.

Webhook'и не используем: на проде нет отдельного HTTPS-эндпоинта под бота,
а long polling работает поверх любого исходящего соединения. При желании
поверх можно потом включить webhook без переписывания клиента.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from care_notifications.models import CareSubscription
from care_notifications.telegram_bot import TelegramBotClient, TelegramBotError


logger = logging.getLogger(__name__)


WELCOME_OK = (
    "Готово, подписка на дайджест Службы заботы активирована.\n"
    "Раз в неделю вы будете получать короткий разбор работ по выбранным группам.\n\n"
    "Чтобы отписаться, отправьте /unsubscribe."
)
WELCOME_BAD_TOKEN = (
    "Ссылка устарела или не распознана. Оформите подписку заново на сайте: https://gazony.ru/sluzhba-zaboty/"
)
WELCOME_NO_TOKEN = (
    "Привет! Я бот Службы заботы Сибирских Газонов.\n"
    "Чтобы подписаться на дайджест, оформите подписку на сайте: https://gazony.ru/sluzhba-zaboty/"
)
UNSUB_OK = "Вы отписались от дайджеста Службы заботы. Спасибо, что были с нами."
UNSUB_NOT_FOUND = "Активная подписка на этот чат не найдена. Возможно, вы уже отписались."


class Command(BaseCommand):
    help = "Long-polling Telegram-бот для дайджеста Службы заботы."

    def add_arguments(self, parser):
        parser.add_argument(
            "--poll-timeout",
            type=int,
            default=30,
            help="long-polling timeout в секундах (по умолчанию 30).",
        )

    def handle(self, *args, **opts):
        bot = TelegramBotClient()
        # Ранний фейл, если токена нет: без него цикл бессмысленен.
        try:
            me = bot._api_call("getMe")
            self.stdout.write(
                self.style.SUCCESS(f"[ok] connected as @{me.get('username')} id={me.get('id')}")
            )
        except TelegramBotError as e:
            self.stderr.write(self.style.ERROR(f"[fatal] {e}"))
            return

        poll_timeout = opts["poll_timeout"]
        offset = 0
        self.stdout.write(self.style.NOTICE("[run] entering long-polling loop, Ctrl+C to stop"))

        try:
            while True:
                try:
                    updates = bot._api_call(
                        "getUpdates",
                        {"offset": offset, "timeout": poll_timeout, "allowed_updates": ["message", "callback_query"]},
                    ) or []
                except TelegramBotError as e:
                    logger.warning("getUpdates failed: %s", e)
                    time.sleep(3)
                    continue

                for u in updates:
                    offset = u["update_id"] + 1
                    try:
                        _handle_update(bot, u)
                    except Exception:
                        logger.exception("handle_update crashed on update_id=%s", u.get("update_id"))
        except KeyboardInterrupt:
            self.stdout.write(self.style.NOTICE("\n[stop] keyboard interrupt, bye"))


def _handle_update(bot: TelegramBotClient, u: dict[str, Any]) -> None:
    if "message" in u:
        _handle_message(bot, u["message"])
    elif "callback_query" in u:
        _handle_callback(bot, u["callback_query"])


def _handle_message(bot: TelegramBotClient, msg: dict[str, Any]) -> None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            bot.send_message(chat_id, WELCOME_NO_TOKEN)
            return
        token = parts[1].strip()
        sub = CareSubscription.objects.filter(token=token).first()
        if not sub:
            bot.send_message(chat_id, WELCOME_BAD_TOKEN)
            return
        sub.telegram_chat_id = chat_id
        sub.telegram_opted_in_at = timezone.now()
        # Если человек был отписан, реактивируем: deep-link это явное согласие.
        if not sub.active:
            sub.active = True
            sub.unsubscribed_at = None
            sub.save(update_fields=["telegram_chat_id", "telegram_opted_in_at", "active", "unsubscribed_at", "updated_at"])
        else:
            sub.save(update_fields=["telegram_chat_id", "telegram_opted_in_at", "updated_at"])
        logger.info("opt-in: sub=%s chat=%s", sub.id, chat_id)
        bot.send_message(chat_id, WELCOME_OK)
        return

    if text == "/unsubscribe":
        sub = CareSubscription.objects.filter(telegram_chat_id=chat_id, active=True).first()
        if not sub:
            bot.send_message(chat_id, UNSUB_NOT_FOUND)
            return
        sub.active = False
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["active", "unsubscribed_at", "updated_at"])
        logger.info("unsubscribe (cmd): sub=%s chat=%s", sub.id, chat_id)
        bot.send_message(chat_id, UNSUB_OK)
        return


def _handle_callback(bot: TelegramBotClient, cq: dict[str, Any]) -> None:
    cq_id = cq.get("id")
    data = cq.get("data") or ""
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")

    if data.startswith("unsub:") and chat_id:
        token = data[len("unsub:"):].strip()
        sub = CareSubscription.objects.filter(token=token).first()
        if sub and sub.active:
            sub.active = False
            sub.unsubscribed_at = timezone.now()
            sub.save(update_fields=["active", "unsubscribed_at", "updated_at"])
            logger.info("unsubscribe (cb): sub=%s chat=%s", sub.id, chat_id)
            bot.answer_callback_query(cq_id, text="Отписали")
            bot.send_message(chat_id, UNSUB_OK)
        else:
            bot.answer_callback_query(cq_id, text="Уже отписаны")
            bot.send_message(chat_id, UNSUB_NOT_FOUND)
        return

    # Неизвестный callback - просто подтверждаем, чтобы у пользователя не висел loader.
    if cq_id:
        bot.answer_callback_query(cq_id)
