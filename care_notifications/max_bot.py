"""Клиент MAX Bot API (dev.max.ru) для рассылки дайджеста Службы заботы.

Тонкая обёртка над `https://platform-api.max.ru`. Используем только requests,
без сторонних SDK. Контракт повторяет `telegram_bot.py`:

    bot = MaxBotClient()                  # token берётся из env MAX_BOT_TOKEN
    payload = build_payload(subscription)
    res = bot.send_digest(subscription, payload)
    # res = {'ok': bool, 'message_id': int | None, 'error': str}

Если токен не задан в env - конструктор не падает: класс импортируется и
существует, но любой вызов сетевого метода возвращает {'ok': False, 'error':
'MAX_BOT_TOKEN не задан'}. Это нужно, чтобы Django мог импортировать модуль
до получения токена от MAX (бот ещё не создан на 2026-05-21).

Документация: https://dev.max.ru/docs/chatbots/

Различия с Telegram Bot API:
- Auth: заголовок `Authorization: <token>` (без префикса Bearer/bot).
- sendMessage: `POST /messages`, body JSON `{chat_id, text, format, attachments}`.
- inline-кнопки идут не в reply_markup, а как attachment типа `inline_keyboard`.
  Кнопки бывают `link` (внешний URL) и `callback` (payload приходит в webhook).
- parse_mode называется `format`, значения: `markdown` или `html`.
- deep-link: `https://max.ru/<botName>?start=<payload>` (не t.me).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .digest import DigestPayload, render_max
from .models import CareSubscription


logger = logging.getLogger(__name__)


MAX_API_BASE = "https://platform-api.max.ru"
DEFAULT_TIMEOUT = 8


class MaxBotError(Exception):
    """Ошибка обращения к MAX Bot API."""


class MaxBotClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("MAX_BOT_TOKEN", "") or ""

    def _require_token(self) -> str:
        if not self.token:
            raise MaxBotError(
                "MAX_BOT_TOKEN не задан: выставь переменную окружения или передай token в конструктор."
            )
        return self.token

    def _api_call(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> Any:
        token = self._require_token()
        url = f"{MAX_API_BASE}{path}"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        try:
            resp = requests.request(
                method.upper(),
                url,
                json=payload or {},
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise MaxBotError(f"HTTP error on {method} {path}: {e}") from e

        # MAX отдаёт JSON и на 2xx, и на 4xx; на 5xx может прилететь текст.
        try:
            data = resp.json()
        except ValueError as e:
            raise MaxBotError(
                f"Не JSON в ответе {method} {path} (status={resp.status_code}): {resp.text[:200]}"
            ) from e

        if resp.status_code >= 400:
            desc = data.get("message") or data.get("error") or f"status={resp.status_code}"
            raise MaxBotError(f"MAX API {method} {path} failed: {desc}")

        return data

    @staticmethod
    def _convert_reply_markup_to_attachments(reply_markup: dict | None) -> list[dict] | None:
        """Преобразует TG-подобный `inline_keyboard` в attachment MAX.

        Вход (наш внутренний формат, общий с TG):
            {"inline_keyboard": [
                [{"text": "Сайт", "url": "..."}],
                [{"text": "Управление", "url": "..."},
                 {"text": "Отписаться", "callback_data": "unsub:<token>"}],
            ]}

        Выход (формат MAX):
            [{"type": "inline_keyboard",
              "payload": {"buttons": [
                  [{"type": "link", "text": "Сайт", "url": "..."}],
                  [{"type": "link", "text": "Управление", "url": "..."},
                   {"type": "callback", "text": "Отписаться", "payload": "unsub:<token>"}],
              ]}}]
        """
        if not reply_markup:
            return None
        rows = reply_markup.get("inline_keyboard") or []
        if not rows:
            return None
        out_rows: list[list[dict]] = []
        for row in rows:
            out_row: list[dict] = []
            for btn in row:
                text = btn.get("text", "")
                if btn.get("url"):
                    out_row.append({"type": "link", "text": text, "url": btn["url"]})
                elif btn.get("callback_data") is not None:
                    out_row.append({
                        "type": "callback",
                        "text": text,
                        "payload": str(btn["callback_data"]),
                    })
            if out_row:
                out_rows.append(out_row)
        if not out_rows:
            return None
        return [{"type": "inline_keyboard", "payload": {"buttons": out_rows}}]

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        format: str = "markdown",
        reply_markup: dict | None = None,
    ) -> dict:
        """Шлёт сообщение в MAX. Возвращает {'ok', 'message_id', 'error'}.

        `format` - 'markdown' или 'html' (см. MAX Bot API). При пустом токене
        не падает, а возвращает {'ok': False, 'error': '...'}, чтобы код на
        проде мог продолжать работать до получения токена от MAX.
        """
        if not self.token:
            return {"ok": False, "message_id": None, "error": "MAX_BOT_TOKEN не задан"}
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text,
        }
        if format:
            payload["format"] = format
        attachments = self._convert_reply_markup_to_attachments(reply_markup)
        if attachments:
            payload["attachments"] = attachments
        try:
            result = self._api_call("POST", "/messages", payload)
        except MaxBotError as e:
            return {"ok": False, "message_id": None, "error": str(e)}
        # MAX отдаёт `{"message": {"id": "...", ...}}` или `{"message_id": "..."}`.
        msg_id = (
            result.get("message_id")
            or (result.get("message") or {}).get("id")
            or (result.get("message") or {}).get("mid")
        )
        return {"ok": True, "message_id": msg_id, "error": ""}

    def answer_callback(self, callback_id: str, text: str | None = None) -> dict:
        """Подтверждение callback-кнопки. Best-effort: при ошибке не падаем.

        MAX-документация про /answers скудная, поэтому реализация осторожная:
        отправляем минимальный payload и игнорируем тело ответа. Это нужно
        только для красивого `loading`-индикатора у пользователя - если не
        отработает, callback всё равно уже обработан вебхуком.
        """
        if not self.token:
            return {"ok": False, "error": "MAX_BOT_TOKEN не задан"}
        payload: dict[str, Any] = {"callback_id": callback_id}
        if text:
            payload["notification"] = text
        try:
            self._api_call("POST", "/answers", payload)
        except MaxBotError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "error": ""}

    def send_digest(self, subscription: CareSubscription, payload: DigestPayload) -> dict:
        """Шлёт текст дайджеста с inline-клавиатурой (Сайт / Управление / Отписаться).

        В отличие от Telegram, hero-картинку отдельным сообщением пока не шлём:
        у MAX нужен либо upload через /uploads, либо публичный URL на attachment.
        На MVP укладываемся в одно текстовое сообщение - hero-картинку можно
        добавить отдельной итерацией, когда канал войдёт в стабильную работу.
        """
        chat_id = subscription.max_chat_id
        if not chat_id:
            return {
                "ok": False,
                "message_id": None,
                "error": "subscription.max_chat_id is empty",
            }
        text = render_max(payload)
        footer = payload.footer
        keyboard = {
            "inline_keyboard": [
                [{"text": "Сайт", "url": footer.site_url}],
                [
                    {"text": "Управление", "url": footer.manage_url},
                    {"text": "Отписаться", "callback_data": f"unsub:{subscription.token}"},
                ],
            ]
        }
        return self.send_message(
            chat_id=chat_id,
            text=text,
            format="markdown",
            reply_markup=keyboard,
        )
