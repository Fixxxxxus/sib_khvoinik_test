"""Источник «сырых» карточек до merge: pages/data.py или модели."""

from __future__ import annotations

import copy
from typing import Any

from django.conf import settings


def get_raw_catalog_plants_unmerged() -> list[dict[str, Any]]:
    if getattr(settings, "USE_DATABASE_CATALOG", False):
        from pages.catalog_orm import plants_raw_dicts_from_db

        return plants_raw_dicts_from_db()
    from pages.data import CATALOG_PAGE

    return [copy.deepcopy(p) for p in (CATALOG_PAGE.get("plants") or [])]
