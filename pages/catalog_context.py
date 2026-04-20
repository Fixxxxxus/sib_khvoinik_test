"""Единая точка контекста каталога: data.py или БД (USE_DATABASE_CATALOG)."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from pages.data import CATALOG_PAGE


def get_catalog_page_for_template() -> dict[str, Any]:
    """
    Словарь как CATALOG_PAGE для render / export: title, categories, …
    Список plants в режиме БД пустой здесь — витрина берёт merged из get_merged_catalog_plants().
    """
    base: dict[str, Any] = dict(CATALOG_PAGE)
    if getattr(settings, "USE_DATABASE_CATALOG", False):
        from pages.catalog_orm import categories_for_site

        base["categories"] = categories_for_site()
        base["plants"] = []
    return base
