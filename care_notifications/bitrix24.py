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
        im_telegram: str = "",
        im_max: str = "",
    ) -> int:
        """Создаёт лид в Б24, возвращает его ID.

        im_telegram / im_max - значения для стандартного multi-field IM (мессенджеры).
        Для Telegram используется TYPE_ID=TELEGRAM, для MAX - OTHER с префиксом 'MAX:'.
        """
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
        im_entries = _build_im_entries(telegram=im_telegram, max_=im_max)
        if im_entries:
            fields["IM"] = im_entries
        if extra_fields:
            fields.update(extra_fields)
        result = self._call("crm.lead.add", {"fields": fields})
        if not isinstance(result, int):
            raise Bitrix24Error(f"crm.lead.add: unexpected result {result!r}")
        return result

    def update_lead(self, lead_id: int, fields: dict[str, Any]) -> bool:
        result = self._call("crm.lead.update", {"id": lead_id, "fields": fields})
        return bool(result)

    def update_lead_messengers(
        self,
        lead_id: int,
        *,
        telegram: str = "",
        max_: str = "",
    ) -> bool:
        """Дописывает IM-поле лида значениями TG/MAX, не затирая ранее заведённые.

        Б24 при update полностью замещает значение multi-field IM. Поэтому сначала
        читаем текущее, добавляем новые TYPE_ID если их там ещё нет, и записываем
        результат.
        """
        new_entries = _build_im_entries(telegram=telegram, max_=max_)
        if not new_entries:
            return False
        try:
            lead = self._call("crm.lead.get", {"id": lead_id}) or {}
        except Bitrix24Error:
            lead = {}
        current = lead.get("IM") or []
        # Удаляем существующие записи с теми же TYPE_ID/VALUE - они будут переписаны.
        keep = []
        new_keys = {(e.get("TYPE_ID"), e.get("VALUE")) for e in new_entries}
        for entry in current:
            key = (entry.get("TYPE_ID"), entry.get("VALUE"))
            if key in new_keys:
                continue
            keep.append({k: entry[k] for k in ("ID", "VALUE_TYPE", "VALUE", "TYPE_ID") if k in entry})
        merged = keep + new_entries
        return self.update_lead(lead_id, {"IM": merged})


def _build_im_entries(*, telegram: str = "", max_: str = "") -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if telegram:
        tg_value = telegram if telegram.startswith("@") or telegram.startswith("https://") else f"@{telegram}"
        out.append({"VALUE": tg_value, "VALUE_TYPE": "WORK", "TYPE_ID": "TELEGRAM"})
    if max_:
        out.append({"VALUE": f"MAX: {max_}", "VALUE_TYPE": "WORK", "TYPE_ID": "OTHER"})
    return out
