"""Генерация латинских URL-слагов из русских названий."""

from __future__ import annotations

import re
from typing import Type

from django.db import models
from django.utils.text import slugify as django_slugify

try:
    from unidecode import unidecode
except ImportError:  # pragma: no cover

    def unidecode(s: str) -> str:  # type: ignore[misc]
        return s


def ascii_slugify(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    ascii_ = unidecode(raw)
    s = django_slugify(ascii_.lower().replace("ё", "e"))
    return s or django_slugify(re.sub(r"[^\w\s-]", "", ascii_, flags=re.UNICODE).strip().lower()) or ""


def unique_slug_for_model(
    model: Type[models.Model],
    base_slug: str,
    *,
    instance_pk: int | None = None,
    slug_field: str = "slug",
) -> str:
    slug = base_slug or "item"
    if len(slug) > 180:
        slug = slug[:180].rstrip("-")
    candidate = slug
    n = 2
    while True:
        qs = model.objects.filter(**{slug_field: candidate})
        if instance_pk is not None:
            qs = qs.exclude(pk=instance_pk)
        if not qs.exists():
            return candidate
        candidate = f"{slug}-{n}"
        n += 1
