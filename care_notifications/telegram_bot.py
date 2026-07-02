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

    def send_media_group(self, chat_id: int, image_urls: list[str]) -> dict:
        """Шлёт альбом карточек по публичным URL. Best-effort.

        Telegram принимает URL прямо в поле media у sendMediaGroup - без upload
        файлов, как и MAX с нашими /media/ карточками. Нюанс: sendMediaGroup
        требует 2..10 элементов, поэтому одну картинку шлём как sendPhoto по URL,
        а больше десяти - бьём на чанки. Пустой список/сбой -> ok=False, чтобы это
        не ломало текстовую доставку дайджеста.
        """
        urls = [u for u in (image_urls or []) if u]
        if not urls:
            return {"ok": False, "message_id": None, "error": "нет картинок"}
        try:
            if len(urls) == 1:
                result = self._api_call("sendPhoto", {"chat_id": chat_id, "photo": urls[0]})
                return {"ok": True, "message_id": result.get("message_id"), "error": ""}
            first_msg_id = None
            for i in range(0, len(urls), 10):
                chunk = urls[i:i + 10]
                media = [{"type": "photo", "media": u} for u in chunk]
                result = self._api_call("sendMediaGroup", {"chat_id": chat_id, "media": media})
                if first_msg_id is None and isinstance(result, list) and result:
                    first_msg_id = result[0].get("message_id")
            return {"ok": True, "message_id": first_msg_id, "error": ""}
        except TelegramBotError as e:
            return {"ok": False, "message_id": None, "error": str(e)}

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
        """Шлёт hero-картинку (если есть), альбом карточек недели и текст дайджеста
        с inline-клавиатурой.

        Альбом - те же карточки категорий подписчика плюс промо, что в Email и MAX
        (единый источник URL). Отправка картинок best-effort: любой сбой не мешает
        уйти тексту. Возвращает результат последнего sendMessage: его message_id
        логируем в DigestDelivery.external_id оркестратором.
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

        # 2. Альбом карточек недели (карточки категорий + промо), best-effort.
        album = list(payload.card_image_urls or [])
        if album and payload.promo_image_url:
            album.append(payload.promo_image_url)
        if album:
            try:
                album_res = self.send_media_group(chat_id=chat_id, image_urls=album)
                if not album_res["ok"]:
                    logger.warning(
                        "send_digest: album failed for sub=%s: %s",
                        subscription.id,
                        album_res["error"],
                    )
            except Exception as exc:
                logger.warning(
                    "send_digest: album unexpected error for sub=%s: %s",
                    subscription.id,
                    exc,
                )

        # 3. Текст + inline-клавиатура: Сайт / Управление подпиской.
        # Отписку убрали - она доступна на странице управления подпиской.
        text = render_telegram(payload)
        footer = payload.footer
        keyboard = {
            "inline_keyboard": [
                [{"text": "Сайт", "url": footer.site_url}],
                [{"text": "Управление подпиской", "url": footer.manage_url}],
            ]
        }
        return self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
