"""Клиент Unisender для отправки email-дайджеста Службы заботы.

Используется каналом email в оркестраторе доставки. Не делает рассылочные
кампании (createCampaign), только одиночный sendEmail на конкретного
получателя - наш кейс one-to-one дайджеста по подписке.

Документация Unisender API:
- https://www.unisender.com/ru/support/api/messages/sendemail/
- Общий формат: POST https://api.unisender.com/ru/api/<method>?format=json

Зависимостей не добавляем, используем requests (он уже в проекте).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests


logger = logging.getLogger(__name__)


UNISENDER_API_BASE = "https://api.unisender.com/ru/api"
DEFAULT_TIMEOUT = 12
DEFAULT_FROM_EMAIL = "noreply@gazony.ru"
DEFAULT_FROM_NAME = "Сибирские Газоны"


class UnisenderError(Exception):
    """Ошибка вызова Unisender API (сетевая, формат, бизнес-ошибка от провайдера)."""


class UnisenderClient:
    """Минимальный клиент Unisender для одиночных писем.

    Конструктор НЕ падает если ключ не задан: импорт модуля и DI клиента
    в Django контейнер должен оставаться работоспособным даже без секретов
    (для миграций, тестов, отрисовки превью). Падение - только на send_*.
    """

    def __init__(self, api_key: str | None = None, default_list_id: str | int | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("UNISENDER_API_KEY", "")
        if default_list_id is not None:
            self.default_list_id: str | int | None = default_list_id
        else:
            env_list_id = os.environ.get("UNISENDER_LIST_ID", "").strip()
            self.default_list_id = env_list_id or None

    def _api_call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST на /<method>?format=json. Возвращает поле result, иначе кидает UnisenderError."""
        if not self.api_key:
            raise UnisenderError(
                "UNISENDER_API_KEY не задан. Заполни переменную окружения или передай api_key в конструктор."
            )

        url = f"{UNISENDER_API_BASE}/{method}?format=json"
        data: dict[str, Any] = {"api_key": self.api_key}
        for key, value in params.items():
            if value is None:
                continue
            data[key] = value

        try:
            response = requests.post(url, data=data, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise UnisenderError(f"Сетевая ошибка Unisender: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise UnisenderError(
                f"Unisender вернул не JSON (HTTP {response.status_code}): {response.text[:300]}"
            ) from exc

        if isinstance(body, dict) and body.get("error"):
            code = body.get("code", "")
            raise UnisenderError(f"Unisender error [{code}]: {body['error']}")

        if not isinstance(body, dict) or "result" not in body:
            raise UnisenderError(f"Unisender вернул неожиданный ответ: {body!r}")

        result = body["result"]
        if not isinstance(result, dict):
            return {"value": result}
        return result

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        from_email: str = DEFAULT_FROM_EMAIL,
        from_name: str = DEFAULT_FROM_NAME,
        list_id: str | int | None = None,
        list_unsubscribe_url: str | None = None,
    ) -> dict[str, Any]:
        """Отправить одно письмо через метод sendEmail.

        Параметр list_unsubscribe_url добавляет заголовки RFC 8058 для one-click
        отписки в Gmail/Yahoo/Mail.ru (требование с февраля 2024 для отправителей
        больше 5000 писем в день).
        """
        params: dict[str, Any] = {
            "email": to_email,
            "sender_name": from_name,
            "sender_email": from_email,
            "subject": subject,
            "body": html_body,
            "list_id": list_id if list_id is not None else self.default_list_id,
            "lang": "ru",
        }

        if list_unsubscribe_url and os.environ.get("UNISENDER_SEND_LIST_UNSUBSCRIBE", "").strip() == "1":
            params["headers"] = (
                f"List-Unsubscribe: <{list_unsubscribe_url}>\n"
                "List-Unsubscribe-Post: List-Unsubscribe=One-Click"
            )

        # Отсутствие ключа - это конфигурационная ошибка, её надо явно поднять,
        # чтобы вызывающий код различал "не настроено" и "провайдер вернул фейл".
        if not self.api_key:
            raise UnisenderError(
                "UNISENDER_API_KEY не задан. Заполни переменную окружения или передай api_key в конструктор."
            )

        try:
            result = self._api_call("sendEmail", params)
        except UnisenderError as exc:
            logger.warning(
                "unisender.send_email failed to=%s subject=%r err=%s",
                to_email,
                subject,
                exc,
            )
            return {"ok": False, "email_id": None, "error": str(exc)}

        email_id = result.get("email_id") or result.get("value")
        return {"ok": True, "email_id": email_id, "error": ""}

    def send_digest_email(self, subscription, payload) -> dict[str, Any]:
        """Удобный wrapper: рендерит payload и шлёт через send_email.

        Импорт render_email тут (а не на уровне модуля), чтобы не цеплять
        Django-настройки при простом импорте клиента (например, из management
        command без полной инициализации шаблонов).
        """
        from .digest import render_email

        if not subscription.email:
            return {"ok": False, "email_id": None, "error": "У подписки не указан email"}

        html = render_email(payload)
        return self.send_email(
            to_email=subscription.email,
            subject=payload.subject,
            html_body=html,
            list_unsubscribe_url=payload.footer.unsubscribe_url,
        )
