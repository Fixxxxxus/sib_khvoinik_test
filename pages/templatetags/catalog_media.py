from __future__ import annotations

from typing import Any

from django import template
from django.templatetags.static import static

register = template.Library()


@register.filter
def plant_image_url(plant: dict[str, Any] | None) -> str:
    """Главное фото: MEDIA (загрузка из админки) или static-путь из каталога."""
    if not isinstance(plant, dict):
        return ""
    media = (plant.get("image_media_url") or "").strip()
    if media:
        return media
    path = (plant.get("image") or "").strip()
    if path:
        return static(path)
    return ""
