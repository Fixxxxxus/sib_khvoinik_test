"""Клиент HTTP-сервиса 1С:УНФ для цифровой карты лояльности (задача Б24 #1231).

Прямой коннект сайт → 1С, минуя штатный коннектор Б24↔1С (он требует профтарифа,
которого не будет). Владимир Соколов опубликовал HTTP-сервис УНФ на веб-сервере:

    POST <base>/<pub>/hs/bitrix/getcard/?phone=&first_name=&last_name=&middle_name=

с Basic-авторизацией. Боевая публикация - `unf` (пользователь `bot`), тестовая -
`skid` (пользователь `Администратор`).

Контракт на 2026-06-03: сервис делает upsert клиента+карты по телефону (телефон =
идентификатор карты) и отвечает `200` с ПУСТЫМ телом. Номер карты обратно не
возвращается, поэтому на success-экране сайта его не показываем. Повторная отправка
тех же данных дубля не плодит - ретраи безопасны.

Конфиг берём из окружения (в `.env` на VDS, в гит не коммитим):

    ONEC_GETCARD_URL   полный URL метода, напр.
                       http://<onec-host>/<pub>/hs/bitrix/getcard/
    ONEC_USER          сервисный пользователь 1С (боевой - `bot`)
    ONEC_PASSWORD      пароль сервисного пользователя

Если ONEC_GETCARD_URL/USER/PASSWORD не заданы - клиент считается выключенным
(`is_configured()` == False), вызывающий код это учитывает и не шлёт.

Телефон шлём в каноническом виде `+7XXXXXXXXXX` с ЛИТЕРАЛЬНЫМ плюсом в query-строке
(именно так Владимир проверял в Postman); кириллицу в ФИО кодируем по UTF-8.

Безопасность: коннект идёт по голому HTTP. HTTPS на стороне 1С не будет (решение
от 2026-06-03), работаем по HTTP осознанно. Значит креды `bot` и ПДн клиента летят
по сети незашифрованными - минимизация риска: отдельный сервисный пользователь
`bot` (не админ) и желательный IP-allowlist на наш VDS 72.56.8.107. При подозрении
на компрометацию пароль ротировать на стороне 1С.
"""

from __future__ import annotations

import base64
import logging
import os
from urllib.parse import urlencode

import requests


logger = logging.getLogger(__name__)


class OneCError(Exception):
    """Любой сбой обращения к HTTP-сервису 1С: сеть, таймаут, HTTP не 200."""


def canonicalize_phone(raw: str) -> str:
    """Приводит телефон к каноническому `+7XXXXXXXXXX` (идентификатор карты).

    Возвращает пустую строку, если номер не похож на российский (тогда в 1С не шлём,
    чтобы не плодить карты с мусорным идентификатором).
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return ""


def mask_phone(raw: str) -> str:
    """Маскирует телефон для логов: показываем только последние 4 цифры.

    В логи/журнал не должен попадать полный номер клиента (ПДн). Возвращает вид
    `+7****1234`; на мусоре - `***`.
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return "+7****" + digits[-4:]


class OneCClient:
    DEFAULT_TIMEOUT = 10  # секунд на один вызов 1С

    def __init__(
        self,
        url: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.url = (url if url is not None else os.environ.get("ONEC_GETCARD_URL", "")).strip()
        self.user = user if user is not None else os.environ.get("ONEC_USER", "")
        self.password = password if password is not None else os.environ.get("ONEC_PASSWORD", "")
        if not self.is_configured():
            logger.info("OneCClient: ONEC_GETCARD_URL/USER/PASSWORD не заданы - 1С-синхронизация выключена")

    def is_configured(self) -> bool:
        return bool(self.url and self.user and self.password)

    def _basic_auth_header(self) -> str:
        """Basic-заголовок с UTF-8 кодированием кредов.

        Стандартный `auth=(user, pass)` в requests кодирует логин/пароль в latin-1
        и падает на кириллическом пользователе тестовой базы (`Администратор`). 1С и
        curl ожидают UTF-8, поэтому собираем заголовок вручную - работает и для `bot`,
        и для `Администратор`.
        """
        token = base64.b64encode(f"{self.user}:{self.password}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def register_card(
        self,
        *,
        phone: str,
        first_name: str = "",
        last_name: str = "",
        middle_name: str = "",
    ) -> None:
        """Заводит/обновляет клиента и карту в 1С по телефону. Кидает OneCError при сбое."""
        if not self.is_configured():
            raise OneCError("ONEC_GETCARD_URL/USER/PASSWORD не заданы в окружении")
        if not phone:
            raise OneCError("register_card: пустой телефон")

        params = {"phone": phone}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if middle_name:
            params["middle_name"] = middle_name
        # safe="+" сохраняет литеральный плюс в значении телефона (как в Postman),
        # кириллица в ФИО при этом кодируется в %XX по UTF-8.
        query = urlencode(params, safe="+")

        try:
            resp = requests.post(
                f"{self.url}?{query}",
                headers={"Authorization": self._basic_auth_header()},
                timeout=self.DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise OneCError(f"1С getcard network error: {e}") from e
        if resp.status_code != 200:
            raise OneCError(f"1С getcard HTTP {resp.status_code}: {resp.text[:300]}")
        # По текущему контракту тело пустое - возвращать нечего.
