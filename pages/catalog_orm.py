"""Сериализация моделей каталога в dict-структуру, совместимую с catalog_merge и шаблонами."""

from __future__ import annotations

from typing import Any

from pages.models import CatalogCategory, Plant


def category_to_dict(c: CatalogCategory) -> dict[str, Any]:
    return {
        "slug": c.slug,
        "sort_order": c.sort_order,
        "hidden": bool(c.hidden),
        "label": c.label,
        "card_label": (c.card_label or c.label).strip(),
        "desc": (c.description or "").strip(),
        "image": (c.cover_path or "").strip(),
        "image_alt": (c.image_alt or "").strip(),
        "category_hub_links": list(c.hub_links or []),
        "legacy_paths": list(c.legacy_paths or []),
    }


def _categories_for_site_uncached() -> list[dict[str, Any]]:
    return [category_to_dict(c) for c in CatalogCategory.objects.all()]


def categories_for_site() -> list[dict[str, Any]]:
    """Категории каталога с TTL-кэшем (см. pages/catalog_cache.py).

    Возвращаем неглубокую копию списка: сами dict в request-пути не мутируются.
    """
    from pages.catalog_cache import get_or_build

    return list(get_or_build("categories_for_site", _categories_for_site_uncached))


def _cover_media_url(plant: Plant) -> str | None:
    if plant.cover_upload:
        return plant.cover_upload.url
    return None


def _cover_static_path(plant: Plant) -> str:
    return (plant.cover_path or "").strip()


def _plant_spec_rows_prefetched(plant: Plant) -> list[dict[str, str]]:
    """Как models.plant_specs_as_rows, но через префетч-кэш characteristics.

    Оригинал делает plant.characteristics.order_by(...), что обходит prefetch_related
    и даёт отдельный SQL-запрос на каждое растение. Здесь берём .all() (кэш префетча)
    и сортируем в Python теми же ключами (sort_order, pk).
    """
    chars = sorted(plant.characteristics.all(), key=lambda ch: (ch.sort_order, ch.pk))
    rows: list[dict[str, str]] = [
        {"label": ch.label.strip(), "value": (ch.value or "").strip()}
        for ch in chars
        if ch.label.strip()
    ]
    if not rows and isinstance(plant.specs_json, dict):
        rows = [{"label": str(k), "value": str(v)} for k, v in plant.specs_json.items()]
    return rows


def plant_to_catalog_dict(plant: Plant) -> dict[str, Any]:
    """Один «сырой» товар в формате CATALOG_PAGE['plants'] до merge."""
    variants: list[dict[str, Any]] = []
    for v in plant.variants.all():
        variants.append(
            {
                "height": (v.height or "").strip(),
                "container": (v.container or "").strip(),
                "price": (v.price or "").strip(),
                "in_stock": bool(v.in_stock),
            }
        )

    gallery_urls: list[str] = []
    for g in plant.gallery_images.all():
        try:
            if g.image:
                gallery_urls.append(g.image.url)
        except ValueError:
            continue

    media_url = _cover_media_url(plant)
    static_path = _cover_static_path(plant)

    d: dict[str, Any] = {
        "slug": plant.slug,
        "name": plant.name,
        "category_slug": plant.category.slug,
        "description": plant.description or "",
        "image": static_path,
        "image_alt": (plant.image_alt or plant.name).strip(),
        "height": (plant.height_hint or "выберите формат ниже").strip(),
        "frost": (plant.frost or "").strip(),
        "light": (plant.light or "").strip(),
        "catalog_teaser": (plant.catalog_teaser_override or "").strip(),
        "variants": variants if variants else [{}],
        "legacy_paths": list(plant.legacy_paths or []),
        "also_in_category_slugs": list(plant.also_in_category_slugs or []),
        "is_new": plant.is_new,
    }
    if media_url:
        d["image_media_url"] = media_url
    if gallery_urls:
        d["gallery_media_urls"] = gallery_urls
    spec_rows = _plant_spec_rows_prefetched(plant)
    if spec_rows:
        d["spec_rows"] = spec_rows
    return d


def plants_raw_dicts_from_db() -> list[dict[str, Any]]:
    qs = (
        Plant.queryset_published()
        # select_related("category"): plant_to_catalog_dict читает plant.category.slug,
        # без join это давало N+1 (отдельный SQL-запрос на каждое растение).
        .select_related("category")
        .order_by("category__sort_order", "category__label", "name")
        .prefetch_related("variants", "gallery_images", "characteristics")
    )
    return [plant_to_catalog_dict(p) for p in qs]
