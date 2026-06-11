from __future__ import annotations

from typing import Any

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

# Кэш выбора варианта: ключ (static-путь, thumb) -> итоговый static-путь.
# collectstatic на проде подхватывает webp автоматически, состав файлов
# между рестартами не меняется, поэтому кэшируем на весь процесс.
_VARIANT_CACHE: dict[tuple[str, bool], str] = {}


def _pick_variant(path: str, thumb: bool) -> str:
    """Возвращает лучший существующий вариант static-пути.

    Для thumb=True порядок: <stem>.thumb.webp -> <stem>.webp -> оригинал.
    Для thumb=False: <stem>.webp -> оригинал.
    """
    key = (path, thumb)
    cached = _VARIANT_CACHE.get(key)
    if cached is not None:
        return cached

    stem, _, _ = path.rpartition(".")
    candidates = []
    if stem:
        if thumb:
            candidates.append(stem + ".thumb.webp")
        candidates.append(stem + ".webp")

    result = path
    for candidate in candidates:
        if finders.find(candidate):
            result = candidate
            break

    _VARIANT_CACHE[key] = result
    return result


def _resolve(plant: dict[str, Any] | None, thumb: bool) -> str:
    """Общая логика: MEDIA-URL как есть, иначе static с предпочтением webp."""
    if not isinstance(plant, dict):
        return ""
    media = (plant.get("image_media_url") or "").strip()
    if media:
        return media
    path = (plant.get("image") or "").strip()
    if path:
        return static(_pick_variant(path, thumb))
    return ""


@register.filter
def plant_image_url(plant: dict[str, Any] | None) -> str:
    """Главное фото: MEDIA (загрузка из админки) или static-путь (webp при наличии)."""
    return _resolve(plant, thumb=False)


@register.filter
def plant_image_thumb_url(plant: dict[str, Any] | None) -> str:
    """Миниатюра для списка: thumb.webp -> webp -> оригинал; MEDIA как есть."""
    return _resolve(plant, thumb=True)
