"""Клиент Telegram Bot API для рассылки дайджеста Службы заботы.

Минимальная обёртка над `https://api.telegram.org/bot<TOKEN>/<method>`.
Используем только requests, без python-telegram-bot и прочих SDK.

Контракт:
    bot = TelegramBotClient()                  # token берётся из env TELEGRAM_BOT_TOKEN
    payload = build_payload(subscription)
    res = bot.send_digest(subscription, payload)
    # res = {'ok': bool, 'message_id': int | None, 'error': str}

Если токен не задан в env, конструктор не падает: ошибка возникает только
при попытке реально дёрнуть API (см. `_require_token`).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import requests

from .digest import DigestPayload, render_telegram
from .models import CareSubscription


logger = logging.getLogger(__name__)


TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 8


class TelegramBotError(Exception):
    """Ошибка обращения к Telegram Bot API."""


class TelegramBotClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "") or ""

    def _require_token(self) -> str:
        if not self.token:
            raise TelegramBotError(
                "TELEGRAM_BOT_TOKEN не задан: выставь переменную окружения или передай token в конструктор."
            )
        return self.token

    def _api_call(
        self,
        method: str,
        payload: dict | None = None,
        files: dict | None = None,
    ) -> Any:
        token = self._require_token()
        url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
        try:
            if files is not None:
                resp = requests.post(url, data=payload or {}, files=files, timeout=DEFAULT_TIMEOUT)
            else:
                resp = requests.post(url, json=payload or {}, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise TelegramBotError(f"HTTP error on {method}: {e}") from e

        try:
            data = resp.json()
        except ValueError as e:
            raise TelegramBotError(
                f"Не JSON в ответе {method} (status={resp.status_code}): {resp.text[:200]}"
            ) from e

        if not data.get("ok"):
            desc = data.get("description") or f"status={resp.status_code}"
            raise TelegramBotError(f"Telegram API {method} failed: {desc}")

        return data.get("result")

    def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
        disable_web_page_preview: bool = True,
    ) -> dict:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            result = self._api_call("sendMessage", payload)
        except TelegramBotError as e:
            return {"ok": False, "message_id": None, "error": str(e)}
        return {"ok": True, "message_id": result.get("message_id"), "error": ""}

    def send_photo(
        self,
        chat_id: int,
        photo_path: str,
        caption: str | None = None,
        parse_mode: str = "Markdown",
    ) -> dict:
        path = Path(photo_path)
        if not path.exists():
            return {"ok": False, "message_id": None, "error": f"photo not found: {photo_path}"}

        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption is not None:
            data["caption"] = caption
            data["parse_mode"] = parse_mode

        try:
            with open(path, "rb") as fh:
                files = {"photo": (path.name, fh, "image/jpeg")}
                result = self._api_call("sendPhoto", data, files=files)
        except TelegramBotError as e:
            return {"ok": False, "message_id": None, "error": str(e)}
        except OSError as e:
            return {"ok": False, "message_id": None, "error": f"file error: {e}"}
        return {"ok": True, "message_id": result.get("message_id"), "error": ""}

    def answer_callback_query(self, callback_id: str, text: str | None = None) -> dict:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            self._api_call("answerCallbackQuery", payload)
        except TelegramBotError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "error": ""}

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
    ) -> dict:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        try:
            self._api_call("editMessageText", payload)
        except TelegramBotError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "error": ""}

    def send_digest(self, subscription: CareSubscription, payload: DigestPayload) -> dict:
        """Шлёт hero-картинку (если есть) + текст дайджеста с inline-клавиатурой.

        Возвращает результат последнего sendMessage: его message_id логируем
        в DigestDelivery.external_id оркестратором.
        """
        chat_id = subscription.telegram_chat_id
        if not chat_id:
            return {"ok": False, "message_id": None, "error": "subscription.telegram_chat_id is empty"}

        # 1. Hero-картинка без подписи (caption ограничен 1024 символами, дайджест длиннее).
        if payload.hero_image_path and Path(payload.hero_image_path).exists():
            photo_res = self.send_photo(chat_id=chat_id, photo_path=payload.hero_image_path, caption=None)
            if not photo_res["ok"]:
                logger.warning(
                    "send_digest: photo failed for sub=%s: %s",
                    subscription.id,
                    photo_res["error"],
                )

        # 2. Текст + inline-клавиатура. MAX-кнопка показывается только если URL задан.
        text = render_telegram(payload)
        footer = payload.footer
        top_row = [{"text": "Сайт", "url": footer.site_url}]
        if footer.max_url:
            top_row.append({"text": "MAX", "url": footer.max_url})
        keyboard = {
            "inline_keyboard": [
                top_row,
                [
                    {"text": "Управление", "url": footer.manage_url},
                    {"text": "Отписаться", "callback_data": f"unsub:{subscription.token}"},
                ],
            ]
        }
        return self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
