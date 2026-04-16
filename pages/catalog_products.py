"""Показ карточек растений на страницах категорий каталога."""

from __future__ import annotations

from typing import Any

from pages.catalog_subcategories import plant_matches_subcategory


def similar_plants_for_detail(
    plant: dict[str, Any],
    plants: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Небольшой список для блока «Похожие» на карточке товара (без полного каталога на странице)."""
    active_slug = plant.get("slug")
    cat = (plant.get("category_slug") or "").strip()
    if not cat:
        return []
    out: list[dict[str, Any]] = []
    for p in plants:
        if p.get("slug") == active_slug:
            continue
        if (p.get("category_slug") or "").strip() == cat:
            out.append(p)
            if len(out) >= limit:
                break
    return out


def plant_belongs_to_category(plant: dict[str, Any], category_slug: str) -> bool:
    """Основная категория, явные доп. slug или подраздел по legacy_paths (см. catalog_subcategories)."""
    if (plant.get("category_slug") or "") == category_slug:
        return True
    if category_slug in (plant.get("also_in_category_slugs") or []):
        return True
    return plant_matches_subcategory(plant, category_slug)
