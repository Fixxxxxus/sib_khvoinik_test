"""Клиент Битрикс24 для подписки на «Службу заботы».

Использует входящий webhook (REST API). URL живёт в окружении BITRIX24_WEBHOOK_URL,
формат `https://<portal>.bitrix24.ru/rest/<user_id>/<token>` (без хвостового слэша).

Кеширует маппинг «текст значения мульти-селекта → внутренний ID»: поле в Б24
«Служба заботы» создано без XML_ID, у элементов справочника есть только числовые ID.
Чтобы при каждой подписке не дёргать `crm.lead.userfield.get`, кешируем результат
в Django cache на сутки.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from django.core.cache import cache


logger = logging.getLogger(__name__)


class Bitrix24Error(Exception):
    """Любой сбой работы с Б24 REST: HTTP не 2xx, тело без `result`, и т.д."""


class Bitrix24Client:
    DEFAULT_TIMEOUT = 8  # секунд на один REST-запрос

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = (webhook_url or os.environ.get("BITRIX24_WEBHOOK_URL", "")).rstrip("/")
        if not self.webhook_url:
            logger.warning("Bitrix24Client: BITRIX24_WEBHOOK_URL не задан, REST-вызовы будут падать")

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        if not self.webhook_url:
            raise Bitrix24Error("BITRIX24_WEBHOOK_URL не задан в окружении")
        url = f"{self.webhook_url}/{method}.json"
        try:
            resp = requests.post(url, json=payload or {}, timeout=self.DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise Bitrix24Error(f"REST {method} network error: {e}") from e
        if resp.status_code != 200:
            raise Bitrix24Error(f"REST {method} HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as e:
            raise Bitrix24Error(f"REST {method} non-JSON response: {resp.text[:300]}") from e
        if "error" in data:
            raise Bitrix24Error(f"REST {method} error: {data.get('error')} {data.get('error_description')}")
        return data.get("result")

    def get_multiselect_value_ids(
        self,
        userfield_code: str,
        labels: list[str],
        *,
        entity: str = "lead",
        cache_ttl: int = 24 * 3600,
    ) -> list[int]:
        """Преобразует список текстовых значений multiselect-поля в список ID элементов.

        userfield_code: технический код UF-поля Б24, например 'UF_CRM_1779072919' для лида.
        entity: 'lead' (использует crm.lead.userfield.get) или 'contact'.
        """
        cache_key = f"b24:userfield:{entity}:{userfield_code}:value_map"
        value_map: dict[str, int] | None = cache.get(cache_key)
        if value_map is None:
            method = f"crm.{entity}.userfield.list"
            # API не поддерживает фильтр по FIELD_NAME напрямую как параметр в .list,
            # передаём filter в payload. crm.<entity>.userfield.list возвращает все UF-поля.
            result = self._call(method, {"filter": {"FIELD_NAME": userfield_code}})
            if not result or not isinstance(result, list):
                raise Bitrix24Error(f"UF-поле {entity}/{userfield_code} не найдено")
            field = result[0]
            items = field.get("LIST") or []
            value_map = {}
            for item in items:
                label = str(item.get("VALUE") or "").strip()
                vid = item.get("ID")
                if label and vid is not None:
                    value_map[label] = int(vid)
            cache.set(cache_key, value_map, cache_ttl)
        labels_set = {label.strip() for label in labels}
        ids = [vid for label, vid in value_map.items() if label in labels_set]
        missing = labels_set - set(value_map.keys())
        if missing:
            logger.warning(
                "b24 multiselect %s/%s: метки не найдены в справочнике: %s",
                entity, userfield_code, ", ".join(sorted(missing)),
            )
        return ids

    def create_lead(
        self,
        *,
        title: str,
        name: str = "",
        phone: str = "",
        email: str = "",
        comments: str = "",
        extra_fields: dict[str, Any] | None = None,
        source_id: str = "WEB",
    ) -> int:
        """Создаёт лид в Б24, возвращает его ID."""
        fields: dict[str, Any] = {
            "TITLE": title,
            "SOURCE_ID": source_id,
        }
        if name:
            fields["NAME"] = name
        if phone:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
        if email:
            fields["EMAIL"] = [{"VALUE": email, "VALUE_TYPE": "WORK"}]
        if comments:
            fields["COMMENTS"] = comments
        if extra_fields:
            fields.update(extra_fields)
        result = self._call("crm.lead.add", {"fields": fields})
        if not isinstance(result, int):
            raise Bitrix24Error(f"crm.lead.add: unexpected result {result!r}")
        return result

    def update_lead(self, lead_id: int, fields: dict[str, Any]) -> bool:
        result = self._call("crm.lead.update", {"id": lead_id, "fields": fields})
        return bool(result)
