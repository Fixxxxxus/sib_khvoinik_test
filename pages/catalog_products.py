"""Показ карточек растений на страницах категорий каталога."""

from __future__ import annotations

from typing import Any


def plant_belongs_to_category(plant: dict[str, Any], category_slug: str) -> bool:
    """Основная категория или явные доп. slug (например род внутри «Кустарники»)."""
    if (plant.get("category_slug") or "") == category_slug:
        return True
    return category_slug in (plant.get("also_in_category_slugs") or [])
