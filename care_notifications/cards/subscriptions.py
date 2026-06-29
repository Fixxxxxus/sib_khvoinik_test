"""Маппинг групп подписки Службы заботы в slug'и категорий календаря."""
from __future__ import annotations


def category_slugs_for_groups(groups: list[str]) -> list[str]:
    from pages.data import CARE_SUBSCRIPTION_GROUPS
    by_slug = {g["slug"]: g.get("category_slugs", []) for g in CARE_SUBSCRIPTION_GROUPS}
    out: list[str] = []
    for g in groups or []:
        for cat in by_slug.get(g, []):
            if cat not in out:
                out.append(cat)
    return out
